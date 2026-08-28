#!/usr/bin/env python3
"""Render the proof-first Continuum visual review master."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

WIDTH, HEIGHT = 1920, 1080


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--review", action="store_true")
    return parser.parse_args()


def make_seekable(source: Path, destination: Path) -> None:
    subprocess.run(
        [
            "gst-launch-1.0", "-q", "filesrc", f"location={source}", "!",
            "decodebin", "!", "videoconvert", "!", "x264enc",
            "speed-preset=medium", "bitrate=8000", "key-int-max=25", "!",
            "h264parse", "!", "mp4mux", "!", "filesink",
            f"location={destination}",
        ],
        check=True,
    )


def main() -> int:
    args = parse_args()
    sources = (args.live, args.models) + ((args.audio,) if args.audio else ())
    for source in sources:
        if not source.is_file():
            raise SystemExit(f"missing input: {source}")
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")

    manifest_path = args.live.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("final_phase") != "VERIFIED" or manifest.get("final_result") != "VERIFIED":
        raise SystemExit("live capture is not verifier-complete")
    if manifest.get("run_id") != "demo-1787881932263":
        raise SystemExit("unexpected live-capture run")

    args.output_dir.mkdir(parents=True)
    recording = args.output_dir / "playwright-recording"
    recording.mkdir()
    seekable_live = args.output_dir / "seekable-live.mp4"
    seekable_models = args.output_dir / "seekable-models.mp4"
    make_seekable(args.live, seekable_live)
    make_seekable(args.models, seekable_models)

    source = Path(__file__).with_name("proof_first_visual.html").resolve()
    query = urlencode(
        {
            "live": seekable_live.resolve().as_uri(),
            "models": seekable_models.resolve().as_uri(),
            "review": "1" if args.review else "0",
        }
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--allow-file-access-from-files"])
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            screen={"width": WIDTH, "height": HEIGHT},
            color_scheme="dark",
            record_video_dir=str(recording),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = context.new_page()
        page.goto(f"{source.as_uri()}?{query}", wait_until="load")
        video = page.video
        page.evaluate("review => window.startContinuumProofFirst(review)", args.review)
        page.wait_for_function("window.__continuumProofFirstDone === true", timeout=240_000)
        context.close()
        if video is None:
            raise RuntimeError("Playwright video recorder unavailable")
        visual = args.output_dir / "continuum-proof-first-visual.webm"
        video.save_as(visual)
        browser.close()
    if args.audio:
        output = args.output_dir / "continuum-proof-first-candidate.mp4"
        subprocess.run(
            [
                "gst-launch-1.0", "-q",
                "filesrc", f"location={visual}", "!", "matroskademux", "!",
                "queue", "!", "vp8dec", "!", "videoconvert", "!",
                "x264enc", "speed-preset=medium", "bitrate=8000", "key-int-max=50", "!",
                "h264parse", "!", "queue", "!", "mux.",
                "filesrc", f"location={args.audio}", "!", "wavparse", "!",
                "audioconvert", "!", "audioresample", "!", "avenc_aac", "bitrate=192000", "!",
                "queue", "!", "mux.", "mp4mux", "name=mux", "!",
                "filesink", f"location={output}",
            ],
            check=True,
        )
    else:
        output = visual
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
