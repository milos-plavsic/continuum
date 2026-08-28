#!/usr/bin/env python3
"""Build the proof-first narration timeline from individually approved WAV clips."""

from __future__ import annotations

import argparse
import math
import subprocess
import tempfile
import wave
from array import array
from pathlib import Path

RATE = 24_000
TOTAL_SECONDS = 234.0
SCENES = (
    (4.2, "01_start_failure.wav"),
    (17.2, "02_detect_missing.wav"),
    (36.0, "03_bound_gemini.wav"),
    (64.0, "04_transfer_context.wav"),
    (93.0, "05_finish_job.wav"),
    (128.0, "06_one_effect.wav"),
    (149.0, "07_independent_truth.wav"),
    (179.0, "08_cloud_binding.wav"),
    (200.0, "09_portable_learning.wav"),
    (224.0, "10_close.wav"),
)
MUSIC_WINDOWS = (
    (0.0, 4.1, 0.050),
    (33.95, 35.95, 0.036),
    (62.35, 63.95, 0.032),
    (89.25, 92.95, 0.038),
    (118.45, 127.95, 0.042),
    (145.90, 148.95, 0.035),
    (171.00, 178.95, 0.040),
    (198.10, 199.95, 0.032),
    (217.45, 223.95, 0.044),
)


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
    for index, (start, name) in enumerate(SCENES):
        voice = read_mono(args.voice_dir / name)
        end = start + len(voice) / RATE
        next_start = SCENES[index + 1][0] if index + 1 < len(SCENES) else TOTAL_SECONDS
        if end > next_start - 0.15:
            raise RuntimeError(
                f"{name} ends at {end:.3f}s and collides with the next scene at "
                f"{next_start:.3f}s"
            )
        offset = round(start * RATE)
        for sample_index, sample in enumerate(voice):
            mix[offset + sample_index] += sample * 0.94

    with tempfile.TemporaryDirectory(prefix="continuum-proof-first-lyria-") as temp:
        decoded = Path(temp) / "lyria.wav"
        subprocess.run(
            [
                "gst-launch-1.0", "-q", "filesrc", f"location={args.music}", "!",
                "decodebin", "!", "audioconvert", "!", "audioresample", "!",
                "audio/x-raw,format=S16LE,channels=1,rate=24000", "!", "wavenc", "!",
                "filesink", f"location={decoded}",
            ],
            check=True,
        )
        music = read_mono(decoded)

    fade = round(0.9 * RATE)
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
    print(
        f"duration={TOTAL_SECONDS:.3f}s peak_dbfs={20 * math.log10(peak):.2f} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
