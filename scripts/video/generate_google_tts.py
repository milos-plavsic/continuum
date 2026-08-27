#!/usr/bin/env python3
"""Render a narration clip with Vertex AI Gemini TTS and local ADC."""

from __future__ import annotations

import argparse
import base64
import json
import wave
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--text-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", default="gemini-3.1-flash-tts-preview")
    parser.add_argument("--voice", default="Orus")
    parser.add_argument("--location", default="global")
    return parser.parse_args()


def write_audio(output: Path, data: bytes, mime_type: str) -> None:
    normalized_mime = mime_type.lower()
    if "audio/wav" in normalized_mime or data.startswith(b"RIFF"):
        output.write_bytes(data)
        return
    if "audio/l16" not in normalized_mime and "audio/pcm" not in normalized_mime:
        raise RuntimeError(f"unsupported audio MIME type: {mime_type}")
    rate = 24_000
    if "rate=" in normalized_mime:
        rate = int(normalized_mime.split("rate=", 1)[1].split(";", 1)[0])
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(data)


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = AuthorizedSession(credentials)
    url = (
        "https://aiplatform.googleapis.com/v1/projects/"
        f"{args.project}/locations/{args.location}/publishers/google/models/"
        f"{args.model}:generateContent"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": args.text_file.read_text(encoding="utf-8")}],
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": args.voice}
                }
            },
        },
    }
    response = session.post(url, json=payload, timeout=180)
    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except json.JSONDecodeError:
            detail = response.text[:300]
        raise RuntimeError(f"Vertex AI returned HTTP {response.status_code}: {detail}")
    result = response.json()
    part = result["candidates"][0]["content"]["parts"][0]["inlineData"]
    audio = base64.b64decode(part["data"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_audio(args.output, audio, part["mimeType"])
    print(
        json.dumps(
            {
                "model": args.model,
                "voice": args.voice,
                "mime_type": part["mimeType"],
                "output": str(args.output),
                "bytes": args.output.stat().st_size,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
