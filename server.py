"""VoxDesk-Web：浏览器语音对话 + DeepSeek 联网工具 + Piper 播报 + 本地会话存储。

只用标准库。模型、ASR、TTS 源码和模型都在本仓库内，外部目录只读。
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT))

import paths  # noqa: E402
import timbre  # noqa: E402
import voice_app  # noqa: E402
from llm import DeepSeekError  # noqa: E402
from store import StoreError  # noqa: E402

MAX_ASR_BYTES = 2 * 1024 * 1024
MAX_TIMBRE_BYTES = 2 * 1024 * 1024
MAX_JSON_BYTES = 128 * 1024

APP: voice_app.VoiceApp | None = None
_wavs: dict[str, Path] = {}
_wav_lock = threading.Lock()


def app() -> voice_app.VoiceApp:
    global APP
    if APP is None:
        APP = voice_app.VoiceApp()
    return APP


def register_wav(name: str) -> None:
    with _wav_lock:
        _wavs[name] = OUT / name
        while len(_wavs) > 20:
            old = next(iter(_wavs))
            _wavs.pop(old).unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "VoxDeskWeb/0.5"

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path in ("/", "/index.html", "/app", "/app.html"):
            self._file(STATIC / "app.html", "text/html; charset=utf-8")
        elif path in ("/voice", "/voice.html"):
            self._file(STATIC / "voice.html", "text/html; charset=utf-8")
        elif path == "/api/health":
            self._json(app().status())
        elif path == "/api/chats":
            archived = str(query.get("archived", ["0"])[0]) in ("1", "true", "yes")
            self._json(app().store.list(archived=archived))
        elif path.startswith("/api/chats/"):
            chat_id = path.rsplit("/", 1)[-1]
            archived = str(query.get("archived", ["0"])[0]) in ("1", "true", "yes")
            try:
                self._json(app().store.get(chat_id, archived=archived))
            except StoreError as exc:
                self._error(exc)
        elif path.startswith("/api/wav/"):
            name = path.rsplit("/", 1)[-1]
            wav = _wavs.get(name)
            if not wav or not wav.exists():
                self._json({"error": "wav not found"}, 404)
            else:
                self._file(wav, "audio/wav")
        elif path.startswith("/api/timbre/"):
            name = path.rsplit("/", 1)[-1]
            wav = _wavs.get(name)
            if not wav or not wav.exists():
                self._json({"error": "wav not found"}, 404)
                return
            try:
                self._json(timbre.analyze_wav(wav))
            except Exception as exc:  # noqa: BLE001
                self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        elif path.startswith("/static/"):
            self._file(STATIC / path[len("/static/"):])
        elif path in ("/app.css", "/app.js", "/favicon.ico"):
            ctype = "text/css; charset=utf-8" if path.endswith(".css") else (
                "application/javascript; charset=utf-8" if path.endswith(".js") else "image/x-icon"
            )
            self._file(STATIC / path.lstrip("/"), ctype)
        else:
            self._json({"error": "not found"}, 404)

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/asr":
                self._asr_post()
                return
            if path == "/api/chat":
                self._chat_post()
                return
            if path == "/api/timbre":
                self._timbre_post()
                return
            if path == "/api/chats":
                body = self._read_json()
                mode = str(body.get("mode") or "general")
                chat = app().store.create(mode=mode)
                self._json(chat, 201)
                return
            if path.startswith("/api/chats/") and path.endswith("/archive"):
                chat_id = path.split("/")[3]
                self._json(app().store.archive(chat_id))
                return
            if path.startswith("/api/chats/") and path.endswith("/restore"):
                chat_id = path.split("/")[3]
                self._json(app().store.restore(chat_id))
                return
            self._json({"error": "not found"}, 404)
        except StoreError as exc:
            self._error(exc)
        except DeepSeekError as exc:
            self._json({"error": str(exc), "type": "DeepSeekError"}, 502)
        except ValueError as exc:
            self._json({"error": str(exc), "type": "ValueError"}, 400)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    # ------------------------------------------------------------------ PATCH / DELETE
    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not path.startswith("/api/chats/"):
            self._json({"error": "not found"}, 404)
            return
        chat_id = path.rsplit("/", 1)[-1]
        try:
            body = self._read_json()
            chat = app().store.rename(chat_id, str(body.get("title") or ""))
            self._json(chat)
        except StoreError as exc:
            self._error(exc)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": str(exc)}, 500)

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not path.startswith("/api/chats/"):
            self._json({"error": "not found"}, 404)
            return
        chat_id = path.rsplit("/", 1)[-1]
        try:
            self._json(app().store.delete(chat_id))
        except StoreError as exc:
            self._error(exc)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------ API
    def _asr_post(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._json({"error": "没有收到音频数据"}, 400)
            return
        if length > MAX_ASR_BYTES:
            self._json({"error": "音频过大"}, 413)
            return
        raw = self.rfile.read(length)
        result = app().transcribe(raw)
        self._json(result)

    def _chat_post(self) -> None:
        body = self._read_json()
        text = str(body.get("text") or "").strip()
        if not text:
            self._json({"error": "text 为空"}, 400)
            return
        result = app().chat(
            conversation_id=str(body.get("conversation_id") or ""),
            text=text,
            mode=str(body.get("mode") or "general"),
            speak=bool(body.get("speak", True)),
            web=bool(body.get("web", True)),
            source=str(body.get("source") or "text"),
            asr_ms=float(body.get("asr_ms") or 0),
        )
        name = result.get("audio")
        if name:
            register_wav(name)
            result["audio"] = f"/api/wav/{name}"
            try:
                t0 = time.perf_counter()
                result["timbre"] = timbre.analyze_wav(OUT / name)
                result["timbre_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            except Exception as exc:  # noqa: BLE001 - 音色失败不影响聊天
                result["timbre"] = None
                result["timbre_error"] = f"{type(exc).__name__}: {exc}"
        self._json(result)

    def _timbre_post(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._json({"error": "没有收到音频数据"}, 400)
            return
        if length > MAX_TIMBRE_BYTES:
            self._json({"error": "音频过大"}, 413)
            return
        raw = self.rfile.read(length)
        self._json(timbre.analyze_pcm16(raw))

    # ------------------------------------------------------------------ 工具
    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_JSON_BYTES:
            raise ValueError("请求体过大")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"JSON 无效：{exc}") from exc
        if not isinstance(body, dict):
            raise ValueError("JSON 必须是对象")
        return body

    def _json(self, obj: dict, code: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _error(self, exc: StoreError) -> None:
        self._json({"error": str(exc), "type": type(exc).__name__}, int(getattr(exc, "status", 500) or 500))

    def _file(self, path: Path, ctype: str = "application/octet-stream") -> None:
        if not path.exists():
            self._json({"error": f"{path.name} 不存在"}, 404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[web] {self.address_string()} {fmt % args}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8800)
    args = ap.parse_args()

    paths.ensure_dirs()
    print("预热 ASR / TTS 模型…", flush=True)
    t0 = time.perf_counter()
    warm = app().warmup()
    print(
        f"模型就绪：ASR {warm['asr_ms']}ms · TTS {warm['tts_ms']}ms · 总 {(time.perf_counter()-t0)*1000:.0f}ms",
        flush=True,
    )
    # 预热音色分析，避免第一次 /voice 的 timbre 多出 ~80ms
    timbre.warmup(paths.OUT_DIR / "_warm.wav")
    print(f"就绪：http://{args.host}:{args.port}", flush=True)
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
