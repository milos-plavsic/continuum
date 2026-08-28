#!/usr/bin/env python3
"""Build the 3:56 Algenib narration and restrained Lyria transition mix."""

from __future__ import annotations

import argparse
import math
import subprocess
import tempfile
import wave
from array import array
from pathlib import Path

RATE = 24_000
SCENES = (
    (0.8, "01_expensive_silence_algenib_108.wav"),
    (16.0, "02_negative_space_algenib_108.wav"),
    (40.2, "03_successor_selection_algenib_108.wav"),
    (72.0, "04_signature_handoff_algenib_108.wav"),
    (103.0, "05_supplier_work_algenib_108.wav"),
    (143.0, "06_one_effect_algenib_108.wav"),
    (162.0, "07_independent_verifier_algenib_108.wav"),
    (186.0, "08_cloud_proof_algenib_112.wav"),
    (211.0, "09_portable_close_algenib_108.wav"),
)
MUSIC_WINDOWS = (
    (14.8, 16.0, 0.050),
    (34.0, 40.2, 0.055),
    (64.0, 72.0, 0.050),
    (99.0, 103.0, 0.045),
    (129.0, 143.0, 0.050),
    (159.0, 162.0, 0.045),
    (210.9, 211.3, 0.035),
)
TOTAL_SECONDS = 236.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice-dir", required=True, type=Path)
    parser.add_argument("--music", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def read_mono(path: Path) -> array[int]:
    with wave.open(str(path), "rb") as stream:
        actual = (stream.getnchannels(), stream.getsampwidth(), stream.getframerate())
        if actual != (1, 2, RATE):
            raise RuntimeError(f"unexpected WAV format {actual}: {path}")
        samples = array("h")
        samples.frombytes(stream.readframes(stream.getnframes()))
        return samples


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    mix = [0.0] * round(TOTAL_SECONDS * RATE)
    for start, name in SCENES:
        voice = read_mono(args.voice_dir / name)
        offset = round(start * RATE)
        for index, sample in enumerate(voice):
            mix[offset + index] += sample * 0.94

    with tempfile.TemporaryDirectory(prefix="continuum-remarkable-lyria-") as temp:
        decoded = Path(temp) / "lyria.wav"
        subprocess.run(
            ["gst-launch-1.0", "-q", "filesrc", f"location={args.music}", "!",
             "decodebin", "!", "audioconvert", "!", "audioresample", "!",
             "audio/x-raw,format=S16LE,channels=1,rate=24000", "!", "wavenc", "!",
             "filesink", f"location={decoded}"], check=True,
        )
        music = read_mono(decoded)

    fade = round(0.75 * RATE)
    for start, end, level in MUSIC_WINDOWS:
        begin, finish = round(start * RATE), round(end * RATE)
        for position in range(begin, finish):
            edge = min(position - begin, finish - position)
            envelope = min(1.0, max(0.0, edge / fade))
            mix[position] += music[(position - begin) % len(music)] * level * envelope

    raw_peak = max(abs(value) for value in mix)
    target_peak = 32767 * (10 ** (-1.5 / 20))
    gain = min(1.0, target_peak / raw_peak) if raw_peak else 1.0
    output = array("h", (max(-32768, min(32767, round(value * gain))) for value in mix))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes(output.tobytes())
    peak = max(abs(value) for value in output) / 32768
    print(f"duration={TOTAL_SECONDS:.3f}s peak_dbfs={20 * math.log10(peak):.2f} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
