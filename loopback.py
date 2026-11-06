"""WASAPI loopback：抓"电脑正在播放的声音"，不需要启用立体声混音。

为什么不用立体声混音：这台机器的 Realtek(SST) 驱动只在 WDM-KS 层暴露它，
PortAudio 打不开（实测 6 种采样率/声道组合都是 `Invalid device`）。
`soundcard` 走的是 WASAPI loopback —— 直接从"扬声器"端点环形抓取，不需要虚拟声卡。

接口与 `voxdesk_audio.MicStream` 对齐（`__enter__` / `frames(limit)` / `__exit__`），
所以 `cli.py` 里只要换一个类，录音逻辑不动。
"""

from __future__ import annotations

import numpy as np
import soundcard as sc

from voxdesk_audio.vad import FRAME_SAMPLES


class LoopbackStream:
    def __init__(
        self,
        speaker: str | None = None,
        sample_rate: int = 16000,
        block: int = FRAME_SAMPLES,
    ) -> None:
        self.speaker_name = speaker
        self.sample_rate = sample_rate
        self.block = block
        self._rec = None
        self._name = ""

    @property
    def name(self) -> str:
        return self._name

    def __enter__(self) -> "LoopbackStream":
        spk = sc.get_speaker(self.speaker_name) if self.speaker_name else sc.default_speaker()
        self._name = str(spk.name)
        mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
        self._rec = mic.recorder(
            samplerate=self.sample_rate,
            channels=2,
            blocksize=self.block,
        )
        self._rec.__enter__()
        return self

    def frames(self, limit: int | None = None):
        if self._rec is None:
            raise RuntimeError("LoopbackStream 必须在 with 里用")
        count = 0
        while limit is None or count < limit:
            data = self._rec.record(numframes=self.block)
            mono = data.mean(axis=1) if data.ndim > 1 else data
            yield np.clip(mono, -1.0, 1.0).astype(np.float32)
            count += 1

    def __exit__(self, *exc: object) -> None:
        if self._rec is not None:
            self._rec.__exit__(None, None, None)
            self._rec = None


def list_speakers() -> list[str]:
    return [str(s.name) for s in sc.all_speakers()]
