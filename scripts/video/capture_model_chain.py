#!/usr/bin/env python3
"""Capture the real four-model, verifier-gated learning proof visual."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

WIDTH = 1920
HEIGHT = 1080
STAGES = ("gemini", "gate", "gemma", "media")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def point(page: Page, selector: str) -> None:
    target = page.locator(selector)
    box = target.bounding_box()
    if box is None:
        raise RuntimeError(f"not visible: {selector}")
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.evaluate("([x,y]) => window.moveContinuumCursor(x,y)", [x, y])
    page.mouse.move(x, y, steps=18)


def main() -> int:
    args = parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    recording_dir = args.output_dir / "playwright-recording"
    recording_dir.mkdir()
    page_path = Path(__file__).with_name("model_chain_visual.html").resolve()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            screen={"width": WIDTH, "height": HEIGHT},
            color_scheme="dark",
            record_video_dir=str(recording_dir),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = context.new_page()
        page.goto(page_path.as_uri(), wait_until="load")
        page.locator("#stage-gemini").wait_for(state="visible")
        video = page.video
        page.wait_for_timeout(700)

        holds = {"gemini": 3200, "gate": 3500, "gemma": 3900, "media": 4700}
        for stage in STAGES:
            selector = f"#stage-{stage}"
            point(page, selector)
            page.wait_for_timeout(450)
            page.evaluate("stage => window.showContinuumStage(stage)", stage)
            page.wait_for_timeout(holds[stage])

        point(page, ".truth")
        page.wait_for_timeout(900)
        context.close()
        if video is None:
            raise RuntimeError("Playwright did not create a video recorder")
        output = args.output_dir / "four-model-chain.webm"
        video.save_as(output)
        browser.close()

    manifest = {
        "schema": "continuum/four-model-video-segment/0.1",
        "captured_at": datetime.now(UTC).isoformat(),
        "source": str(page_path),
        "models": [
            "gemini-3.6-flash",
            "google/gemma-4-26b-a4b-it-maas",
            "veo-3.1-lite-generate-001",
            "lyria-3-clip-preview",
        ],
        "truth_boundary": "DERIVED_NOT_AUTHORITY_OR_EVIDENCE",
        "request_digest": "8c1e8e14c5b26e23ae67980067152385ce00dfc16bbd5bbaf845710626e74c32",
        "video": output.name,
        "video_sha256": digest(output),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
