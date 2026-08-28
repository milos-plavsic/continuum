#!/usr/bin/env python3
"""Capture the sub-four-minute same-run edit and mux the locked narration."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

WIDTH, HEIGHT = 1920, 1080


def make_seekable(source: Path, destination: Path) -> None:
    """Create a densely keyed edit intermediate so browser seeks finish on time."""
    subprocess.run([
        "gst-launch-1.0", "-q", "filesrc", f"location={source}", "!", "decodebin", "!",
        "videoconvert", "!", "x264enc", "speed-preset=medium", "bitrate=8000",
        "key-int-max=25", "!", "h264parse", "!", "mp4mux", "!", "filesink",
        f"location={destination}",
    ], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--review", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for source in (args.live, args.models, args.audio):
        if not source.is_file():
            raise SystemExit(f"missing input: {source}")
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    recording = args.output_dir / "playwright-recording"
    recording.mkdir()
    seekable_live = args.output_dir / "seekable-live.mp4"
    seekable_models = args.output_dir / "seekable-models.mp4"
    make_seekable(args.live, seekable_live)
    make_seekable(args.models, seekable_models)
    page_source = Path(__file__).with_name("remarkable_edit_visual.html").resolve()
    manifest_path = args.live.parent / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"missing live capture manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("final_phase") != "VERIFIED" or manifest.get("final_result") != "VERIFIED":
        raise SystemExit("live capture did not finish VERIFIED")
    query = urlencode({
        "live": seekable_live.resolve().as_uri(),
        "models": seekable_models.resolve().as_uri(),
        "review": "1" if args.review else "0",
        "run": str(manifest.get("run_id", "")),
        "trace": str(manifest.get("trace_id", "")),
    })
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, args=["--allow-file-access-from-files"]
        )
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT}, screen={"width": WIDTH, "height": HEIGHT},
            color_scheme="dark", record_video_dir=str(recording),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = context.new_page()
        page.goto(f"{page_source.as_uri()}?{query}", wait_until="load")
        video = page.video
        page.evaluate("review => window.startContinuumRemarkable(review)", args.review)
        page.wait_for_function("window.__continuumRemarkableDone === true", timeout=250_000)
        context.close()
        if video is None:
            raise RuntimeError("Playwright video recorder unavailable")
        visual = args.output_dir / "continuum-remarkable-visual.webm"
        video.save_as(visual)
        browser.close()

    final = args.output_dir / "continuum-remarkable-final.mp4"
    padded_audio = args.output_dir / "continuum-remarkable-audio-with-intro.wav"
    subprocess.run([
        "gst-launch-1.0", "-q", "concat", "name=join", "!", "audioconvert", "!",
        "wavenc", "!", "filesink", f"location={padded_audio}",
        "audiotestsrc", "wave=silence", "samplesperbuffer=48000", "num-buffers=3", "!",
        "audio/x-raw,format=S16LE,channels=1,rate=48000", "!", "join.",
        "filesrc", f"location={args.audio}", "!", "wavparse", "!", "audioconvert", "!",
        "audioresample", "!", "audio/x-raw,format=S16LE,channels=1,rate=48000", "!", "join."
    ], check=True)
    subprocess.run([
        "gst-launch-1.0", "-q", "mp4mux", "name=mux", "!", "filesink", f"location={final}",
        "filesrc", f"location={visual}", "!", "matroskademux", "!", "queue", "!", "decodebin", "!",
        "videoconvert", "!", "x264enc", "speed-preset=medium", "bitrate=8000", "key-int-max=50", "!",
        "h264parse", "!", "queue", "!", "mux.", "filesrc", f"location={padded_audio}", "!", "wavparse", "!",
        "audioconvert", "!", "audioresample", "!",
        "audio/x-raw,format=S16LE,channels=1,rate=48000", "!",
        "voaacenc", "bitrate=160000", "!", "aacparse", "!", "queue", "!", "mux."
    ], check=True)
    print(final)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
