"""音色分析：复刻 CosyVoice 音色链路的前端 + 统计，输出一个可画图的颜色。

CosyVoice（QwenAudio/CosyVoice，`cosyvoice/cli/frontend.py::_extract_spk_embedding`）的
零样本音色分析是：

    16k 单声道
      → torchaudio.compliance.kaldi.fbank(num_mel_bins=80, dither=0)
      → feat - feat.mean(dim=0)          # 按帧去均值
      → campplus.onnx (CAM++ 说话人模型) → 192 维 speaker embedding
      → 作为 llm_embedding / flow_embedding 送进 TTS

也就是说：**音色与文本、ASR 无关**，只看 80 维 log-mel 的说话人嵌入。

本仓库没有 campplus.onnx（约 27MB，硬约束不复制模型），所以这里复刻它的前端部分：
80 维 log-mel（25ms 窗 / 10ms 步）→ 帧均值归一化 → 频带占比、频谱质心、带宽、
平坦度、帧通量 + 基频 → HSL 颜色。等接入 CAM++ 后，把 `_descriptor()` 换成 192 维
嵌入的固定投影即可，`analyze()` 的返回结构不变。

用法：

    from timbre import analyze_wav, analyze_pcm16
    info = analyze_wav("out/xxx.wav")       # 任意采样率 WAV → dict
    info = analyze_pcm16(raw_bytes)          # 16k 单声道 int16 → dict
"""

from __future__ import annotations

import math
import time
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 16000          # 与 CosyVoice / VoxDesk 音频边界一致
N_FFT = 512
WIN = 400           # 25ms @16k
HOP = 160           # 10ms @16k
N_MELS = 80
FMIN = 20.0

_SOURCE = "fbank80(25ms/10ms) + CAM++ 前端统计（未加载 campplus.onnx）"

# 音色亮度 → 色相的调色板（设计值，不是物理映射）：暖橙 → 品红 → 蓝 → 青。
_HUE_STOPS = ((0.12, 36.0), (0.45, 330.0), (0.72, 196.0), (1.0, 165.0))


# ---------------------------------------------------------------- mel 前端


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * math.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: float) -> float:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


@lru_cache(maxsize=1)
def _mel_filterbank() -> tuple[np.ndarray, np.ndarray]:
    """HTK mel 三角滤波器组（80 带，20Hz–8kHz）与每个带的中心频率。"""
    mel_pts = np.linspace(_hz_to_mel(FMIN), _hz_to_mel(SR / 2), N_MELS + 2)
    hz_pts = _mel_to_hz(mel_pts)
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / SR)
    fb = np.zeros((N_MELS, freqs.size), dtype=np.float32)
    for i in range(N_MELS):
        lo, mid, hi = hz_pts[i], hz_pts[i + 1], hz_pts[i + 2]
        left = (freqs - lo) / max(mid - lo, 1e-9)
        right = (hi - freqs) / max(hi - mid, 1e-9)
        fb[i] = np.clip(np.minimum(left, right), 0.0, None)
    centers = hz_pts[1:-1].astype(np.float32)
    return fb, centers


def _resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    """优先复用原框架的线性插值重采样；没有 sys.path 时等价回退。"""
    if src == dst or x.size == 0:
        return x.astype(np.float32, copy=False)
    try:  # server.py 已经把 D:\\VoxDesk\\audio\\src 加进 sys.path
        from voxdesk_audio.capture import resample

        return resample(x, src, dst)
    except Exception:
        n = int(round(x.size * dst / src))
        if n <= 0:
            return x.astype(np.float32, copy=False)
        idx = np.linspace(0.0, x.size - 1, n, dtype=np.float64)
        i0 = np.floor(idx).astype(np.int64)
        i1 = np.minimum(i0 + 1, x.size - 1)
        frac = (idx - i0).astype(np.float32)
        return (x[i0] * (1.0 - frac) + x[i1] * frac).astype(np.float32)


def _frame(x: np.ndarray) -> np.ndarray:
    """预加重 + 分帧 + Hamming 窗，返回 (T, WIN)。

    注：Kaldi fbank 默认用 Povey 窗并先去直流；这里用 Hamming 近似。
    颜色映射不需要 bit-level 一致，参数（80 带 / 25ms / 10ms / preemph 0.97）保持一致。
    """
    if x.size < WIN:
        x = np.pad(x, (0, WIN - x.size))
    pre = np.empty_like(x, dtype=np.float32)
    pre[0] = x[0]
    pre[1:] = x[1:] - 0.97 * x[:-1]
    n = 1 + (pre.size - WIN) // HOP
    idx = np.arange(WIN, dtype=np.int64)[None, :] + HOP * np.arange(n, dtype=np.int64)[:, None]
    return pre[idx] * np.hamming(WIN).astype(np.float32)


def _logmel(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(T, 80) 的 log-mel 能量，以及每帧 RMS（用于剔除静音帧）。"""
    frames = _frame(x)
    power = np.abs(np.fft.rfft(frames, n=N_FFT, axis=1)) ** 2
    fb, _ = _mel_filterbank()
    mel = power @ fb.T
    rms = np.sqrt(np.mean(frames**2, axis=1))
    return np.log(np.maximum(mel, 1e-10)), rms


# ---------------------------------------------------------------- 统计量


def _midi_note_name(f0: float) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    midi = int(round(69 + 12 * math.log2(f0 / 440.0)))
    return f"{names[midi % 12]}{midi // 12 - 1}"


def _estimate_f0(x: np.ndarray) -> float | None:
    """在能量最高的 3 个 40ms 窗上做自相关，取中位数。只用于展示，不参与颜色。"""
    n = int(0.04 * SR)
    if x.size < n * 2:
        return None
    hop = max(n // 2, 1)
    starts = list(range(0, x.size - n, hop))
    if not starts:
        return None
    energy = [float(np.mean(x[s : s + n] ** 2)) for s in starts]
    picks = sorted(range(len(starts)), key=energy.__getitem__, reverse=True)[:3]
    found: list[float] = []
    lo, hi = int(SR / 400), int(SR / 60)  # 60–400 Hz
    for p in picks:
        seg = x[starts[p] : starts[p] + n].astype(np.float64)
        seg = seg - seg.mean()
        if np.sqrt(np.mean(seg**2)) < 1e-4:
            continue
        corr = np.correlate(seg, seg, mode="full")[seg.size - 1 :]
        if corr[0] <= 0:
            continue
        corr = corr / corr[0]
        lag = int(np.argmax(corr[lo:hi])) + lo
        if corr[lag] > 0.3:
            found.append(SR / lag)
    return float(np.median(found)) if found else None


def _descriptor(x: np.ndarray, sr: int = SR) -> dict:
    """核心：80 维 log-mel 统计 → 音色描述 + HSL 颜色。"""
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    if sr != SR:
        x = _resample(x, sr, SR)
    if x.size == 0:
        return _silent()

    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(x)))
    if rms < 1e-4:
        return _silent(duration=x.size / SR)

    logmel, frame_rms = _logmel(x)
    # 以自身响度的 p95 为基准取"发声帧"，避免整段音量不同导致音色漂移。
    speech_floor = max(1e-4, 0.30 * float(np.percentile(frame_rms, 95)))
    keep = frame_rms >= speech_floor
    if int(keep.sum()) < 5:  # 太安静/太短：退回全部帧
        keep = frame_rms > 1e-5
    if int(keep.sum()) < 2:
        return _silent(duration=x.size / SR)
    active = logmel[keep]

    mean_db = active.mean(axis=0).astype(np.float64)
    rel_nat = mean_db - float(mean_db.max())  # log-mel 是自然对数：1 nat ≈ 4.34 dB
    weights = np.exp(rel_nat)  # 线性频带能量，最大值为 1
    total = float(weights.sum()) or 1.0

    idx = np.arange(N_MELS, dtype=np.float64)
    centroid_band = float((weights * idx).sum() / total)
    bandwidth_band = float(np.sqrt((weights * (idx - centroid_band) ** 2).sum() / total))
    low = float(weights[:20].sum() / total)
    mid = float(weights[20:50].sum() / total)
    high = float(weights[50:].sum() / total)
    cumulative = np.cumsum(weights) / total
    rolloff_band = int(np.searchsorted(cumulative, 0.85))

    # 时间维：CosyVoice 是 feat - feat.mean(dim=0)，这里用去均值后的波动量。
    norm = active - active.mean(axis=0, keepdims=True)
    temporal_std = float(norm.std())
    flux_db = float(np.mean(np.abs(np.diff(active, axis=0)))) if active.shape[0] > 1 else 0.0
    flatness = float(np.exp(np.mean(np.log(weights + 1e-9))) / max(float(weights.mean()), 1e-9))

    brightness = centroid_band / (N_MELS - 1)  # 0..1
    spread = bandwidth_band / (N_MELS - 1)     # 0..1
    tilt = high - low                          # -1..1，高频越多越大
    f0 = _estimate_f0(x)

    # ---- 音色 → 颜色 -------------------------------------------------
    # 深黑底上，音色只决定色相/饱和度，音量不参与颜色（音量只控制波形振幅，
    # 见 static/voice.html）。色相走一条设计好的暖→品红→蓝→青的路径：
    #   低沉/浑厚 0.1→橙红，0.45→品红，0.72→蓝，明亮/清脆 0.9→青
    # 避免直接线性映射时中间段一片绿。
    hue = _hue_for(brightness, tilt)
    saturation = float(np.clip(0.80 + 0.12 * min(1.0, spread * 2.5), 0.62, 0.94))
    lightness = float(np.clip(0.56 + 0.12 * (brightness - 0.5), 0.50, 0.64))

    centroid_hz = int(round(float(_mel_filterbank()[1][int(round(centroid_band))])))
    rolloff_hz = int(round(float(_mel_filterbank()[1][rolloff_band])))
    vector = [
        round(low, 4), round(mid, 4), round(high, 4),
        round(brightness, 4), round(spread, 4), round(flatness, 4),
        round(min(flux_db / 6.0, 1.0), 4), round(temporal_std / 8.0, 4),
    ]
    return {
        "ok": True,
        "duration_ms": int(round(x.size / SR * 1000)),
        "sample_rate": SR,
        "rms": round(rms, 4),
        "peak": round(peak, 3),
        "active_ratio": round(float(keep.mean()), 3),
        "f0_hz": int(round(f0)) if f0 else None,
        "note": _midi_note_name(f0) if f0 else None,
        "centroid_hz": centroid_hz,
        "rolloff_hz": rolloff_hz,
        "centroid_band": round(centroid_band, 2),
        "bandwidth": round(spread, 3),
        "flatness": round(flatness, 3),
        "flux_db": round(flux_db, 2),
        "temporal_std": round(temporal_std, 2),
        "bands": {"low": round(low, 3), "mid": round(mid, 3), "high": round(high, 3)},
        "vector": vector,
        "hue": round(hue, 1),
        "saturation": round(saturation, 3),
        "lightness": round(lightness, 3),
        "color": _hsl_hex(hue, saturation, lightness),
        "accent": _hsl_hex((hue + 24) % 360, saturation, min(lightness + 0.07, 0.76)),
        "label": _label(centroid_hz, f0, flatness),
        "source": _SOURCE,
    }


def _hue_for(brightness: float, tilt: float) -> float:
    """音色亮度 → 色相（暖橙 → 品红 → 蓝 → 青，取最短弧插值，避开中间一片绿）。"""
    b = float(np.clip(brightness - 0.06 * tilt, 0.0, 1.0))
    for (p0, h0), (p1, h1) in zip(_HUE_STOPS, _HUE_STOPS[1:]):
        if b <= p1:
            t = float(np.clip((b - p0) / (p1 - p0), 0.0, 1.0)) if p1 > p0 else 0.0
            delta = ((h1 - h0 + 180.0) % 360.0) - 180.0
            return (h0 + delta * t) % 360.0
    return _HUE_STOPS[-1][1]


def _label(centroid_hz: int, f0: float | None, flatness: float) -> str:
    if centroid_hz < 350:
        tone = "浑厚"
    elif centroid_hz < 900:
        tone = "温润"
    elif centroid_hz < 2200:
        tone = "明亮"
    else:
        tone = "清脆"
    if f0:
        tone += f" · 约 {int(round(f0))}Hz"
    if flatness > 0.60:
        tone += " · 气声"
    return tone


def _silent(duration: float = 0.0) -> dict:
    return {
        "ok": True,
        "silent": True,
        "duration_ms": int(round(duration * 1000)),
        "sample_rate": SR,
        "rms": 0.0,
        "peak": 0.0,
        "active_ratio": 0.0,
        "f0_hz": None,
        "note": None,
        "centroid_hz": 0,
        "rolloff_hz": 0,
        "centroid_band": 0.0,
        "bandwidth": 0.0,
        "flatness": 0.0,
        "flux_db": 0.0,
        "temporal_std": 0.0,
        "bands": {"low": 0.0, "mid": 0.0, "high": 0.0},
        "vector": [0.0] * 8,
        "hue": 200.0,
        "saturation": 0.25,
        "lightness": 0.5,
        "color": "#4a6273",
        "accent": "#5c7a8c",
        "label": "静音",
        "source": _SOURCE,
    }


def _hsl_hex(h: float, s: float, light: float) -> str:
    c = (1.0 - abs(2.0 * light - 1.0)) * s
    hp = (h % 360.0) / 60.0
    x = c * (1.0 - abs(hp % 2.0 - 1.0))
    rgb = [(c, x, 0.0), (x, c, 0.0), (0.0, c, x), (0.0, x, c), (x, 0.0, c), (c, 0.0, x)][
        int(hp) % 6
    ]
    m = light - c / 2.0
    return "#" + "".join(f"{int(round((v + m) * 255)):02x}" for v in rgb)


# ---------------------------------------------------------------- 对外接口


def analyze(x: np.ndarray, sr: int = SR) -> dict:
    """float32/float64 波形（任意采样率）→ 音色描述。"""
    t0 = time.perf_counter()
    info = _descriptor(x, sr)
    info["analyze_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return info


def analyze_pcm16(raw: bytes, sample_rate: int = SR) -> dict:
    """16-bit 单声道 PCM 原始字节 → 音色描述。"""
    raw = raw[: len(raw) // 2 * 2]  # 上行万一多出半个样本，直接丢掉
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return analyze(samples, sample_rate)


def analyze_wav(path: str | Path) -> dict:
    """WAV 文件（任意采样率/声道）→ 音色描述。优先复用 voxdesk_audio.read_wav。"""
    path = Path(path)
    try:
        from voxdesk_audio.capture import read_wav

        return analyze(read_wav(path, SR), SR)
    except Exception:
        with wave.open(str(path), "rb") as w:
            channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if width != 2:
            raise ValueError(f"只支持 16-bit PCM WAV，当前 {width * 8}-bit")
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)
        return analyze(samples, rate)


def warmup(wav_path: str | Path | None = None) -> dict:
    """启动时跑一次：预热 mel 滤波器、voxdesk_audio 导入与 numpy FFT。

    不预热时，第一次 /api/chat 的 timbre_ms 会包含约 150ms 的模块导入开销。
    """
    if wav_path and Path(wav_path).exists():
        return analyze_wav(wav_path)
    tone = (0.2 * np.sin(2 * np.pi * 220 * np.arange(int(0.25 * SR)) / SR)).astype(np.float32)
    return analyze(tone)


if __name__ == "__main__":  # 快速自测：python timbre.py out/xxx.wav
    import json
    import sys

    for arg in sys.argv[1:] or ["out/_warm.wav"]:
        print(arg, json.dumps(analyze_wav(arg), ensure_ascii=False, indent=2))
