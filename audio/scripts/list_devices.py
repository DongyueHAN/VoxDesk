"""列出本机音频设备，并标出默认输入。"""

from __future__ import annotations

import argparse

import sounddevice as sd

from voxdesk_audio import enable_utf8


def main() -> int:
    enable_utf8()
    ap = argparse.ArgumentParser(description="列出音频设备")
    ap.add_argument("--all", action="store_true", help="含输出设备")
    args = ap.parse_args()

    devices = sd.query_devices()
    apis = sd.query_hostapis()
    default_in, default_out = sd.default.device

    print(f"默认输入 #{default_in} / 默认输出 #{default_out}")
    print(f"{'#':>3}  {'in':>3} {'out':>3}  {'采样率':>6}  {'host':<12} 名称")
    for idx, dev in enumerate(devices):
        if not args.all and dev["max_input_channels"] < 1:
            continue
        mark = "  ← 默认输入" if idx == default_in else ""
        print(
            f"{idx:>3}  {dev['max_input_channels']:>3} {dev['max_output_channels']:>3}"
            f"  {int(dev['default_samplerate']):>6}  {apis[dev['hostapi']]['name']:<12} {dev['name']}{mark}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
