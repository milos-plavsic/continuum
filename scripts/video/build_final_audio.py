#!/usr/bin/env python3
"""Build the locked narration timeline and restrained Lyria transition mix."""

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
    (2.500, "scene01_hook_orus_115.wav"),
    (25.793, "scene02_autonomy_orus_115.wav"),
    (45.921, "scene03_failure_handling_orus_115.wav"),
    (64.936, "scene04_successor_selection_orus_115.wav"),
    (89.621, "scene05_fence_context_orus_115.wav"),
    (115.558, "scene06_one_effect_orus_115.wav"),
    (134.851, "scene07_independent_proof_orus_115.wav"),
    (159.605, "scene08_architecture_learning_orus_115.wav"),
    (187.177, "scene09_personal_standard_orus_115.wav"),
)
MUSIC_WINDOWS = (
    (24.7, 27.1, 0.075),
    (44.9, 47.0, 0.065),
    (63.9, 66.0, 0.065),
    (158.8, 187.0, 0.075),
)
TOTAL_SECONDS = 203.300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice-dir", required=True, type=Path)
    parser.add_argument("--music", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def read_mono(path: Path) -> array[int]:
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, RATE):
            raise RuntimeError(f"unexpected WAV format: {path}")
        samples = array("h")
        samples.frombytes(stream.readframes(stream.getnframes()))
        return samples


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    total = round(TOTAL_SECONDS * RATE)
    mix = [0.0] * total

    for start, name in SCENES:
        voice = read_mono(args.voice_dir / name)
        offset = round(start * RATE)
        for index, sample in enumerate(voice):
            if offset + index < total:
                mix[offset + index] += sample * 0.94

    with tempfile.TemporaryDirectory(prefix="continuum-lyria-") as temp_dir:
        decoded = Path(temp_dir) / "lyria.wav"
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

    fade = round(0.75 * RATE)
    for start, end, level in MUSIC_WINDOWS:
        begin = round(start * RATE); finish = min(total, round(end * RATE))
        for position in range(begin, finish):
            local = position - begin
            remaining = finish - position
            envelope = min(1.0, local / fade, remaining / fade)
            source = music[local % len(music)]
            mix[position] += source * level * max(0.0, envelope)

    raw_peak = max(abs(value) for value in mix)
    target_peak = 32767 * (10 ** (-1.5 / 20))
    gain = min(1.0, target_peak / raw_peak) if raw_peak else 1.0
    output = array(
        "h",
        (max(-32768, min(32767, round(value * gain))) for value in mix),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.output), "wb") as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(RATE)
        stream.writeframes(output.tobytes())
    peak = max(abs(value) for value in output) / 32768
    print(f"duration={TOTAL_SECONDS:.3f}s peak_dbfs={20 * math.log10(peak):.2f} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
