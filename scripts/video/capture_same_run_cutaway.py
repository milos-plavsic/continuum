#!/usr/bin/env python3
"""Capture a read-only, cursor-led view of one persisted Cloud Run workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

WIDTH = 1920
HEIGHT = 1080


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--token-env", default="CONTINUUM_VIDEO_ID_TOKEN")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_cursor(page: Page) -> None:
    page.evaluate(
        """
        () => {
          const style = document.createElement('style');
          style.textContent = `
            #continuum-cutaway-cursor {
              position: fixed; left: 0; top: 0; z-index: 2147483647;
              width: 28px; height: 36px; pointer-events: none;
              transform: translate3d(1735px, 944px, 0);
              transition: transform 720ms cubic-bezier(.22,.78,.25,1);
              filter: drop-shadow(0 2px 3px rgba(0,0,0,.75));
            }
            #continuum-read-only {
              position: fixed; right: 22px; bottom: 20px; z-index: 2147483646;
              padding: 7px 10px; border: 1px solid rgba(131,187,255,.52);
              border-radius: 7px; color: #bddcff; background: rgba(3,13,20,.84);
              font: 750 11px/1 system-ui,sans-serif; letter-spacing: .09em;
            }
          `;
          document.head.appendChild(style);
          const cursor = document.createElement('div');
          cursor.id = 'continuum-cutaway-cursor';
          cursor.innerHTML = `<svg viewBox="0 0 28 36" aria-hidden="true">
            <path d="M2 2 L2 29 L9.3 22.8 L14.2 34 L19.2 31.8 L14.1 20.7 L24 20 Z"
              fill="#f8ffff" stroke="#071018" stroke-width="2" stroke-linejoin="round"/>
          </svg>`;
          document.body.appendChild(cursor);
          const badge = document.createElement('div');
          badge.id = 'continuum-read-only';
          badge.textContent = 'READ-ONLY · SAME PERSISTED RUN';
          document.body.appendChild(badge);
          window.__continuumCutawayMove = (x, y) => {
            cursor.style.transform = `translate3d(${x}px, ${y}px, 0)`;
          };
        }
        """
    )


def move_to(page: Page, selector: str, hold_ms: int) -> None:
    locator = page.locator(selector).first
    box = locator.bounding_box()
    if box is None:
        raise RuntimeError(f"cutaway target is not visible: {selector}")
    x = box["x"] + box["width"] / 2
    y = box["y"] + min(box["height"] / 2, 150)
    page.evaluate("([x,y]) => window.__continuumCutawayMove(x,y)", [x, y])
    page.mouse.move(x, y, steps=18)
    page.wait_for_timeout(hold_ms)


def editorial_boxes(page: Page) -> dict[str, dict[str, float]]:
    return page.evaluate(
        """
        () => {
          const box = (start, end, pad = 10) => {
            const a = document.querySelector(start).getBoundingClientRect();
            const b = document.querySelector(end).getBoundingClientRect();
            const article = document.querySelector(start).closest('article').getBoundingClientRect();
            const bottom = Math.min(b.bottom + pad, innerHeight - 18);
            return {
              x: Math.round(article.left - 5), y: Math.round(a.top - pad),
              width: Math.round(article.width + 10), height: Math.round(bottom - a.top + pad)
            };
          };
          const hero = document.querySelector('#result').closest('article').getBoundingClientRect();
          return {
            candidate: box('#selected', '#candidates', 12),
            context: box('#context', '#excluded', 12),
            effect: {
              x: Math.round(hero.left - 5), y: Math.round(hero.top - 5),
              width: Math.round(hero.width + 10), height: Math.round(hero.height + 10)
            }
          };
        }
        """
    )


def main() -> int:
    args = parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"{args.token_env} is required")
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    recording = args.output_dir / "playwright-recording"
    recording.mkdir()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            screen={"width": WIDTH, "height": HEIGHT},
            color_scheme="dark",
            extra_http_headers={"Authorization": f"Bearer {token}"},
            record_video_dir=str(recording),
            record_video_size={"width": WIDTH, "height": HEIGHT},
        )
        page = context.new_page()
        page.goto(args.url, wait_until="networkidle", timeout=45_000)
        state: dict[str, Any] = page.evaluate(
            """
            async runId => {
              const response = await fetch('/cloud-smoke/' + encodeURIComponent(runId));
              if (!response.ok) throw new Error(await response.text());
              const state = await response.json();
              render(state);
              scrollTo({top: 0, behavior: 'instant'});
              return state;
            }
            """,
            args.run_id,
        )
        if state.get("phase") != "VERIFIED":
            raise RuntimeError(f"expected VERIFIED state, got {state.get('phase')!r}")
        install_cursor(page)
        boxes = editorial_boxes(page)
        page.screenshot(path=args.output_dir / "full-top.png", full_page=False)
        video = page.video
        page.wait_for_timeout(900)
        move_to(page, "h1", 1300)
        move_to(page, "#selected", 900)
        move_to(page, "#candidates", 2500)
        move_to(page, "#context", 900)
        move_to(page, "#excluded", 2600)
        move_to(page, "#result", 900)
        move_to(page, "#effect", 2600)
        move_to(page, "#digest", 2200)
        context.close()
        if video is None:
            raise RuntimeError("Playwright did not create a video recorder")
        output = args.output_dir / "same-run-cutaway.webm"
        video.save_as(output)
        browser.close()

    manifest = {
        "schema": "continuum/read-only-same-run-cutaway/0.1",
        "captured_at": datetime.now(UTC).isoformat(),
        "source_url": args.url,
        "run_id": args.run_id,
        "trace_id": state.get("correlation_id"),
        "phase": state.get("phase"),
        "viewport": {"width": WIDTH, "height": HEIGHT},
        "editorial_boxes": boxes,
        "video": output.name,
        "video_sha256": sha256(output),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
