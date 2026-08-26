# Continuum demo video — production log

This log records generated media provenance, subjective acceptance decisions,
and any production constraint that changes the canonical script.

## Voice decision

- Service: DaVinci AI Voice.
- Model reported by creation details: ElevenLabs TTS V3.
- Voice: Brian; English; American.
- Selection process: catalog previews of Bella, Ryan, and Brian; Brian selected
  after direct comparison by the project owner.
- Desired delivery: calm, technically authoritative, conversational, with
  restrained dry wit.

## Scene 01 — silent failure

### Take 1

- Generated: August 26, 2026.
- Source text: the original 52-word Scene 01 draft beginning with
  `[calm and assured]`.
- DaVinci-reported duration: 00:26.
- Saved locally as `artifacts/video/voice/scene01_hook_take1.mp3`.
- SHA-256:
  `891f0c9c03b5a6ef4a907ad8ee97bc245b354d8fd3c443dc8c23218ec2afdd8e`.
- Owner review: instructions were not spoken; amount and product name were
  pronounced correctly; delivery was slightly slow; overall 8/10.
- Disposition: preserve as fallback, not the preferred final take.

### Preferred take 2 text

The canonical script was shortened to 45 words, changed `No crash. No error.`
to a single rhythmic clause, and uses `[calm and assured, slightly brisk]`.
Generation was not completed: DaVinci displayed a purchase gate before the
second generation.

## Commercial boundary encountered

After the first free generation, DaVinci offered a seven-day full-access trial
for USD 1.99 followed by USD 29.99 per month unless cancelled. No purchase was
made. Further DaVinci generations require explicit owner approval or a selected
alternative voice-production route.

## Final voice route

- Service: Google AI Studio Speech Generation.
- Model: Gemini 3.1 Flash TTS Preview.
- Voice: Orus.
- Controls: Natural pace, Newscaster style, American (General) accent.
- Raw Scene 01 duration: 26.04 seconds.
- Post-process: pitch-preserving 1.15x tempo pass using GStreamer `pitch`.
- Accepted duration: 22.64 seconds.
- Accepted local file:
  `artifacts/video/voice/scene01_hook_orus_115.wav`.
- Owner review: accepted as excellent on August 26, 2026.
- Decision: this voice and processing chain are locked for the remaining
  narration unless a later scene exposes a specific intelligibility problem.

## Final narration masters

All durations below are after the locked pitch-preserving 1.15x tempo pass.
Raw Gemini exports are preserved beside the processed masters.

| Scene | Subject | Raw | Master |
|---:|---|---:|---:|
| 1 | Silent failure | 26.04 s | 22.64 s |
| 2 | One click, then autonomy | 22.40 s | 19.48 s |
| 3 | Failure handling and bounded Gemini | 21.12 s | 18.37 s |
| 4 | Dynamic successor selection | 27.64 s | 24.03 s |
| 5 | Fence and minimum context | 29.08 s | 25.29 s |
| 6 | One consequential effect | 21.44 s | 18.64 s |
| 7 | Independent proof | 27.72 s | 24.10 s |
| 8 | Architecture as evidence | 24.84 s | 21.60 s |
| 9 | Personal standard | 15.08 s | 13.11 s |

Total processed narration: 187.26 seconds (3:07.26), leaving approximately
50 seconds of visual breathing room within the 3:58 maximum edit target.

Scene 04's first master was later superseded because its narration said the
model cited a Cloud Run revision. The same-run choice evidence directly cites
the deployed endpoint, workload identity, and immutable image; the exact
serving revision is independently supplied by `/build-info` in Scene 08. The
corrected master preserves this trust-boundary distinction.
