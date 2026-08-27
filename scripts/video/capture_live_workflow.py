#!/usr/bin/env python3
"""Capture one real Cloud Run succession workflow with an observable cursor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page, sync_playwright

WIDTH = 1920
HEIGHT = 1080


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--token-env", default="CONTINUUM_VIDEO_ID_TOKEN")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser.parse_args()


def add_cursor(page: Page) -> None:
    page.evaluate(
        """
        () => {
          const style = document.createElement('style');
          style.textContent = `
            #continuum-demo-cursor {
              position: fixed; left: 0; top: 0; z-index: 2147483647;
              width: 28px; height: 36px; pointer-events: none;
              transform: translate3d(1750px, 940px, 0);
              transition: transform 700ms cubic-bezier(.22,.78,.25,1), opacity 180ms;
              filter: drop-shadow(0 2px 3px rgba(0,0,0,.75));
            }
            #continuum-demo-cursor svg { width: 100%; height: 100%; display: block; }
            .continuum-click-ring {
              position: fixed; z-index: 2147483646; pointer-events: none;
              width: 18px; height: 18px; margin: -9px 0 0 -9px;
              border: 3px solid #83bbff; border-radius: 50%;
              animation: continuum-click 620ms ease-out forwards;
            }
            @keyframes continuum-click {
              from { transform: scale(.45); opacity: 1; }
              to { transform: scale(3.2); opacity: 0; }
            }
          `;
          document.head.appendChild(style);
          const cursor = document.createElement('div');
          cursor.id = 'continuum-demo-cursor';
          cursor.innerHTML = `<svg viewBox="0 0 28 36" aria-hidden="true">
            <path d="M2 2 L2 29 L9.3 22.8 L14.2 34 L19.2 31.8 L14.1 20.7 L24 20 Z"
              fill="#f8ffff" stroke="#071018" stroke-width="2" stroke-linejoin="round"/>
          </svg>`;
          document.body.appendChild(cursor);
          window.__continuumCursorMove = (x, y) => {
            cursor.style.transform = `translate3d(${x}px, ${y}px, 0)`;
          };
          window.__continuumCursorClick = (x, y) => {
            const ring = document.createElement('div');
            ring.className = 'continuum-click-ring';
            ring.style.left = `${x}px`; ring.style.top = `${y}px`;
            document.body.appendChild(ring);
            setTimeout(() => ring.remove(), 700);
          };
        }
        """
    )


def center(locator: Locator) -> tuple[float, float]:
    box = locator.bounding_box()
    if box is None:
        raise RuntimeError("target is not visible")
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def reveal(page: Page, selector: str, *, hold: float = 0.8) -> None:
    target = page.locator(selector).first
    target.scroll_into_view_if_needed()
    page.wait_for_timeout(450)
    x, y = center(target)
    page.evaluate("([x,y]) => window.__continuumCursorMove(x,y)", [x, y])
    page.mouse.move(x, y, steps=16)
    page.wait_for_timeout(int(hold * 1000))


def click(page: Page, selector: str) -> None:
    target = page.locator(selector).first
    reveal(page, selector, hold=0.45)
    x, y = center(target)
    page.evaluate("([x,y]) => window.__continuumCursorClick(x,y)", [x, y])
    page.mouse.click(x, y)


def snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => ({
          phase: document.querySelector('#phase')?.textContent?.trim(),
          run: document.querySelector('#runHeader')?.textContent?.trim(),
          trace: document.querySelector('#traceHeader')?.textContent?.trim(),
          completed_stages: document.querySelectorAll('.stage.done').length,
          active_stage: [...document.querySelectorAll('.stage')].findIndex(
            item => item.classList.contains('active')),
          selected: document.querySelector('#selectionStatus')?.textContent?.trim(),
          context: `${document.querySelector('#includedCount')?.textContent?.trim()} / ${document.querySelector('#excludedCount')?.textContent?.trim()}`,
          effect: document.querySelector('#effectStatus')?.textContent?.trim(),
          result: document.querySelector('#finalVerdict')?.textContent?.trim(),
        })
        """
    )


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    args = parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"{args.token_env} is required")
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    recording_dir = args.output_dir / "playwright-recording"
    recording_dir.mkdir()
    timeline: list[dict[str, Any]] = []
    started = time.monotonic()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            screen={"width": WIDTH, "height": HEIGHT},
            color_scheme="dark",
            extra_http_headers={"Authorization": f"Bearer {token}"},
            record_video_dir=str(recording_dir),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = context.new_page()
        page.goto(args.url, wait_until="networkidle", timeout=45_000)
        page.locator("#start").wait_for(state="visible", timeout=15_000)
        add_cursor(page)
        video = page.video

        page.wait_for_timeout(1200)
        reveal(page, "h1", hold=1.0)
        reveal(page, ".scene.active .metric", hold=1.0)
        reveal(page, "#start", hold=0.8)
        click(page, "#start")
        click_at = round(time.monotonic() - started, 3)
        page.wait_for_timeout(800)
        reveal(page, "#runHeader", hold=1.0)
        reveal(page, "#deadline", hold=1.0)

        previous: dict[str, Any] = {}
        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline:
            current = snapshot(page)
            if current != previous:
                timeline.append(
                    {"t": round(time.monotonic() - started, 3), **current}
                )
                previous = current
            if current.get("phase") == "VERIFIED":
                break
            reveal(page, "#promiseState", hold=0.45)
            page.wait_for_timeout(500)
        else:
            raise RuntimeError("live workflow did not reach VERIFIED before timeout")

        # The browser now contains only the persisted observations from this
        # exact run. Tour them in causal order with a real, visible cursor.
        click(page, ".stage[data-i='1']")
        reveal(page, "#missingStatus", hold=1.0)
        reveal(page, "#missingEvent", hold=1.2)
        click(page, ".stage[data-i='2']")
        reveal(page, "#candidates .candidate.rejected", hold=1.2)
        reveal(page, "#candidates .candidate.selected", hold=1.2)
        reveal(page, "#selectionStatus", hold=1.0)
        click(page, ".stage[data-i='3']")
        reveal(page, "#denials", hold=1.2)
        reveal(page, "#contextChips", hold=1.4)
        reveal(page, "#activation", hold=1.1)
        click(page, ".stage[data-i='4']")
        reveal(page, "#sourceReceipts .receipt:first-child", hold=1.1)
        reveal(page, "#sourceReceipts .receipt:last-child", hold=1.1)
        reveal(page, "#recommendation", hold=1.0)
        reveal(page, "#decisionScope", hold=1.0)
        click(page, ".stage[data-i='5']")
        reveal(page, ".deliveries", hold=1.2)
        reveal(page, "#effectCount", hold=1.4)
        click(page, ".stage[data-i='6']")
        reveal(page, "#artifacts", hold=1.0)
        reveal(page, "#verifierIdentity", hold=1.1)
        reveal(page, "#verdict", hold=1.4)
        click(page, ".stage[data-i='7']")
        reveal(page, "#runHeader", hold=1.0)
        reveal(page, "#traceHeader", hold=1.0)
        reveal(page, "#observationCount", hold=1.0)
        click(page, ".stage[data-i='8']")
        reveal(page, "#finalVerdict", hold=1.3)
        reveal(page, "#finalEffect", hold=1.3)
        page.screenshot(path=args.output_dir / "final-proof.png", full_page=False)
        final = snapshot(page)
        page.wait_for_timeout(1800)
        context.close()

        output_video = args.output_dir / "live-workflow-master.webm"
        if video is None:
            raise RuntimeError("Playwright did not create a video recorder")
        video.save_as(output_video)
        browser.close()

    run_id = str(final.get("run") or "")
    trace_id = str(final.get("trace") or "").removeprefix("trace ")
    manifest = {
        "schema": "continuum/live-screen-capture/0.2",
        "captured_at": datetime.now(UTC).isoformat(),
        "source_url": args.url,
        "viewport": {"width": WIDTH, "height": HEIGHT},
        "fresh_start_click_at_seconds": click_at,
        "duration_seconds": round(time.monotonic() - started, 3),
        "run_id": run_id,
        "trace_id": trace_id,
        "final_phase": final.get("phase"),
        "final_result": final.get("result"),
        "video": output_video.name,
        "video_sha256": digest(output_video),
        "timeline": timeline,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
