#!/usr/bin/env python3
"""Capture the deterministic final visual edit as a review or clean master."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

WIDTH = 1920
HEIGHT = 1080


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--review", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    recording = args.output_dir / "playwright-recording"
    recording.mkdir()
    source = Path(__file__).with_name("final_edit_visual.html").resolve()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            screen={"width": WIDTH, "height": HEIGHT},
            color_scheme="dark",
            record_video_dir=str(recording),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = context.new_page()
        page.goto(source.as_uri(), wait_until="load")
        page.locator("#opening").wait_for(state="attached")
        video = page.video
        page.evaluate("review => window.startContinuumFinal(review)", args.review)
        page.wait_for_function("window.__continuumFinalDone === true", timeout=215_000)
        page.wait_for_timeout(400)
        context.close()
        if video is None:
            raise RuntimeError("Playwright did not create a video recorder")
        name = "continuum-review-visual.webm" if args.review else "continuum-clean-visual.webm"
        video.save_as(args.output_dir / name)
        browser.close()
    print(args.output_dir / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
