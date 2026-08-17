#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
result_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/latest/result.json"
result = json.loads(result_path.read_text())
rows = "\n".join(
    f"<tr><td>{html.escape(e['occurred_at'])}</td><td>{html.escape(e['event_type'])}</td>"
    f"<td>{html.escape(e['actor'])}</td><td><code>{html.escape(e['event_id'][:12])}</code></td></tr>"
    for e in result["timeline"]
)
page = f"""<!doctype html><meta charset=utf-8><title>Continuum incident evidence</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:40px auto;background:#0b1020;color:#edf2ff}}.cards{{display:flex;gap:16px}}.card{{background:#17203b;padding:18px;border-radius:12px;flex:1}}table{{width:100%;border-collapse:collapse;margin-top:24px}}td,th{{padding:9px;border-bottom:1px solid #33405f;text-align:left}}code{{color:#8ee3cf}}.denied{{color:#ff9d9d}}.ok{{color:#8ee3cf}}</style>
<h1>Succession verified</h1><p>Evidence → policy → fencing → manifest → execution → verification</p>
<div class=cards><div class=card><b>v17</b><h2 class=denied>{html.escape(result['predecessor_status'])}</h2><p>STALE_FENCE · GRANT_REVOKED</p></div>
<div class=card><b>v18</b><h2 class=ok>{html.escape(result['successor_status'])}</h2><p>Owner · vendor.create</p></div>
<div class=card><b>Observed result</b><h2>{result['vendor_count']} vendor</h2><p>duplicate effects: {result['vendor_count'] - 1}</p></div></div>
<table><thead><tr><th>Virtual time</th><th>Event</th><th>Actor</th><th>Evidence ID</th></tr></thead><tbody>{rows}</tbody></table>"""
destination = result_path.with_name("incident.html")
destination.write_text(page)
print(destination)

