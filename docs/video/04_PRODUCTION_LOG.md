# Continuum demo video — production log

This log records generated media provenance, subjective acceptance decisions,
and any production constraint that changes the canonical script.

## Proof-first replacement production — August 28, 2026

- Final cleanup retained only the accepted 3:54 master, its mixed WAV, the
  canonical live capture and manifest/proof frame, the final model-chain source
  and manifest, and the decode poster. Superseded renders, timecoded reviews,
  one-frame-per-second review exports, duplicate Playwright recordings,
  seekable transcodes, rough cuts, and video caches were moved to the system
  trash. Historical paths below remain as append-only provenance and are not
  expected to exist in the cleaned workspace.

- A wholly new 3:42 judge-first production was started after re-reading the live
  submission guidance. It opens on the working Cloud Run cockpit, places the
  start click at roughly five seconds, and uses six operational questions as its
  chapter grammar.
- New sources are `docs/video/07_PROOF_FIRST_PRODUCTION.md`,
  `docs/video/08_PROOF_FIRST_SCRIPT.md`, and
  `docs/video/09_PROOF_FIRST_RUNBOOK.md`; the visual scaffold is
  `scripts/video/proof_first_visual.html` with the fail-closed renderer
  `scripts/video/capture_proof_first_edit.py`.
- First timecoded review artifact:
  `artifacts/video/proof-first-review-20260828T131500Z/continuum-proof-first-review.webm`;
  1920×1080, 25 fps, 3:42.96. It is rejected as a final candidate because the
  first decoded frame was blank, the handoff crop exposed the obsolete v18
  presentation label, and the old cockpit cloud-proof footer conflicted with the
  accepted 17-object/174-span release truth.
- Corrections use a frame extracted directly from the canonical source as the
  decode poster, exclude the obsolete label region through an editorial crop,
  and replace the stale cockpit proof frame with an exact-release evidence panel
  derived from `docs/submission/current-release.json`. No runtime value is
  overwritten or relabelled.
- Corrected timecoded visual review:
  `artifacts/video/proof-first-review-20260828T133000Z/continuum-proof-first-review.webm`;
  1920×1080, 25 fps, 3:43.04. Checkpoint review accepted the frame-one product,
  click at five seconds, supplier pack, one-effect result, verifier boundary,
  exact-release panel, architecture, model chain, and close. A final 210 px
  handoff crop adjustment removes the remaining edge of the obsolete avatar;
  this affects only framing and does not replace a runtime value.
- First complete clean candidate, now superseded by the revision below:
  `artifacts/video/proof-first-candidate-20260828T140000Z/continuum-proof-first-candidate.mp4`;
  1920×1080, 25 fps, H.264 High Profile with mono AAC, 3:42.12; SHA-256
  `c11da6f44cf0f2c594fa985c096023f69c54dda2fd0fd4b268d9da69f2f426e8`.
- Narration was generated as ten independently replaceable takes with Vertex AI
  `gemini-3.1-flash-tts-preview`, Algenib voice. The standard tempo pass is
  1.08x; the opening is 1.20x and the cloud-proof passage is 1.25x so neither
  collides with its evidence window. The 222-second narration mix peaks at
  -1.50 dBFS; SHA-256
  `e550d5b8f9c1d339c7a178e0c280775e8dabad5bdd8c2dd8cc56af91a7efd7ab`.
- Captions are locked at `docs/video/10_PROOF_FIRST_CAPTIONS.srt`. They match
  the spoken text but are intentionally sidecar captions rather than burned-in
  graphics, preserving the native evidence surface.
- Encoded-frame review sampled all 223 seconds at one frame per second and
  inspected the opening, click, successor gate, corrected handoff, supplier
  pack, idempotent effect, independent verdict, exact-release receipt,
  architecture, derivative proof, and close. All passed visual review. Public
  playback and human listening approval remain publication gates.
- Revised preferred local candidate:
  `artifacts/video/proof-first-candidate-v2-20260828T150000Z/continuum-proof-first-candidate.mp4`;
  1920×1080, 25 fps, H.264 High Profile with mono AAC, 3:54.04; SHA-256
  `fb8795fdddf7bc5bac7314c94a5564e737bd761f5e947db08954e26d08395617`.
- The opening and closing slates now identify Continuum, its motto, Milos
  Plavsic, the All Things Agentic Hackathon, and August 28, 2026. The product
  appears at second four and the single start click remains visible at second
  nine.
- Full-screen time-cut cards were rejected after review. Same-run jumps at
  2:04 and 2:25 now use a small 1.4-second disclosure badge while the evidence
  remains visible. The creator accepted this final cut and its audio on August
  28, 2026.
- The released learning proof now runs from 3:24 to 3:40. Encoded frames prove
  that it progresses through Gemini, independent verification, Gemma, and the
  active Veo 3.1 + Lyria 3 step before the closing slate.
- Narration tempos are now assigned per take: 1.00x for naturally paced scenes,
  1.08x for scenes 1 and 8, 1.10x for scene 7, and 1.15x for the deliberately
  slower scene 6. This narrows delivery to approximately 118–133 words per
  minute. The earlier 1.20x and 1.25x fast takes are superseded.
- The verifier-gated Lyria 3 cue is mixed only into nine narration-free
  transition windows at restrained gain with 0.9-second fade-in and fade-out.
  The 234-second narration/music master peaks at -1.50 dBFS; SHA-256
  `071b042ae4824558fd30ac49054fe73bde6d04302f58795a021c9736833ce10e`.
- All 234 encoded seconds were decoded at one frame per second. The metadata
  slates, click, cut badges, core workflow evidence, exact-release proof,
  learning steps 2–4, and final hold passed visual review. Creator listening
  approval is complete. The master was published publicly on YouTube at
  https://youtu.be/bvrgXMApekk; signed-out playback, duration, chapters,
  English captions, title, visibility and opening-slate thumbnail passed the
  final publication gate.

## Superseded remarkable production — August 28, 2026

- This section records the earlier remarkable production. It is superseded by
  the proof-first master above and its local media was removed during cleanup.
- Source: a fresh private IAM-authenticated `continuum-control` Cloud Run run
  recorded from deployed commit
  `d4d7d52cde010dd3e07be5ad06cf8ee858cb3a4f`, image
  `sha256:4c4b1559d00aa12d66a4f7be253d6893524759e661291446732325543747249f`,
  revision `continuum-control-00062-s6x`.
- Fresh run: `demo-1787881932263`; trace
  `c29c7692b9fc405acaaeca1dfb60d891`; terminal state `VERIFIED`; selected
  successor `v19`; proof manifest all 17 required evidence objects and 174
  correlated spans.
- Raw live capture:
  `artifacts/video/capture/final-v19-20260828T015202Z/live-workflow-master.webm`;
  SHA-256
  `459a35f99e606e44c2b29238fbb4b08443074d8685e0f1459b5a5b83541b3e8f`.
- Narration: `gemini-3.1-flash-tts-preview`, Algenib voice; 1.08x
  pitch-preserving masters except Scene 08 at 1.12x. The 236-second mono WAV
  mix peaks at -1.50 dBFS; SHA-256
  `f9e96dbd51a427eb270df4bc81ac69f63375588199b90a0d8f5eab8938dcb67c`.
- Final master:
  `artifacts/video/remarkable-v2/final-20260828T044500Z/continuum-remarkable-final.mp4`.
  Runtime 3:59.88; 1920x1080, 25 fps, H.264 High Profile; 48 kHz mono AAC;
  SHA-256
  `d236cd9a8001f27764f1e7b48f0eaa3710e006d701989cfeec74da7f9afe1950`.
- Visual acceptance sampled the opening, selection, handoff, supplier, effect,
  verifier, cloud-proof, architecture, model-chain, and closing segments. The
  accepted cut shows v19, 2/4 context, one effect with zero duplicates, the
  independent `VERIFIED` verdict, and 17/17 objects with 174 spans at their
  intended narration windows.
- Two stale labels in the deployed d4 cockpit were presentation defects, not
  run-state values: the handoff avatar said v18 while adjacent state said v19,
  and the proof footer retained an older count. The edit masks only those two
  labels with the authoritative same-run/release values. The repository cockpit
  now renders the successor dynamically and carries the canonical proof count.
- Earlier `final-20260828T015721Z`, `final-20260828T040700Z`, and
  `final-20260828T042000Z` renders are rejected: frame review found a stale
  avatar and then source-timestamp drift. They must not be uploaded.

## Historical live workflow screen master — August 27, 2026

- Source: private IAM-authenticated `continuum-control` Cloud Run cockpit.
- Exact deployment: commit `b4a8163bfb74da583b01885fad106523ce65a1c6`,
  image `sha256:120daa9e80db83733fd700877778300b567b9a3b5802a10fd6d7f225f5397c29`.
- Fresh run: `demo-1787788603354`; trace
  `51e492899892545e9fd706d7abdf16cb`.
- Outcome: `VERIFIED`; selected successor `v18`; eleven persisted
  observations; one provider effect; independent attestation
  `cf3e4d28c2a6bd0380bbb771f84e31511cc3bac375df51361f20ea133f9d5aaa`.
- Raw master: 83.52 seconds, 1920x1080 VP8/WebM, visible purposeful cursor,
  one lifecycle-mutating click, real scrolling, and a read-only proof-focus
  interaction.
- File: `artifacts/video/capture/live-flow-20260826T235633Z/live-workflow-master.webm`.
- SHA-256: `37933c197ef048e6000ac69467d4532d0f29857e71b0dd514262816849fdc4a6`.
- The recorder completed the workflow but initially attempted `save_as` after
  closing the browser. The untouched Playwright artifact was recovered and
  verified; `capture_live_workflow.py` now saves before browser shutdown.

## Transition music source

- Source: the verifier-gated Lyria 3 output already generated by Continuum's
  admitted learning branch.
- Model: `lyria-3-clip-preview`.
- Prompt: `Calm, minimalist instrumental ambient music with soft synthesizer
  pads and a steady, unobtrusive rhythm.`
- File: `artifacts/learning/public-multimodal-proof-8bec862/continuum-lyria-3.mp3`.
- Duration: 30.772 seconds; SHA-256:
  `d95f8220d35b805328191d205f51cd01071ded38e8be2654b576bc62d51242ab`.
- Intended use: short low-level stage transitions with gentle fades, never as
  authority or runtime evidence.

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

## Revised Scene 08 — four-model learning chain

- Generated: August 27, 2026 through Vertex AI using local Google ADC after the
  AI Studio playground reported no linked API key.
- Model: `gemini-3.1-flash-tts-preview`.
- Voice: Orus.
- Exact source: `scripts/video/scene08_architecture_learning.txt`.
- Raw master: `artifacts/video/voice/scene08_architecture_learning_orus_raw.wav`
  (30.96 s; SHA-256 `2a3617641d93ab730f1ac9d27455b071b6aff176a15c0eeecadabc4acaa1267b`).
- Locked 1.15x pitch-preserving candidate:
  `artifacts/video/voice/scene08_architecture_learning_orus_115.wav`
  (26.92 s; SHA-256 `b33bfc941a0527a6a483fa9423d4a387666a62343a0614815a02dc09fd585f0e`).
- Picture candidate:
  `artifacts/video/model-chain-20260827T004930Z/four-model-chain.webm`
  (23.00 s; SHA-256 `b5c4cbee5b719982f197879c8debbb33fa696a2e0853ce3e494da1c71a1e838b`).
- Truth boundary: the model-chain picture uses the separately released
  `multimodal-proof-8bec862` receipt and is labelled
  `DERIVED · NOT AUTHORITY OR EVIDENCE`; it is not presented as evidence from
  the fresh on-camera run.

## Final integrated candidate

- Candidate: `artifacts/video/final-edit-20260827T010327Z/continuum-final-candidate-v2.mp4`.
- Runtime: 3:23.76.
- Video: 1920×1080, 25 fps, H.264 High Profile.
- Audio: 48 kHz stereo AAC at 128 kb/s; locked narration and restrained Lyria
  transition mix; PCM mix peak normalized to -1.50 dBFS before AAC encoding.
- SHA-256: `ed3d21fcc007d3020cbd43b6280e7f8bb548b75cf8ee2a4447fad6ec476bb1d4`.
- Review correction: trust-boundary slugs now update even when successive scenes
  reuse the live source layer. Highlight geometry no longer travels between
  panels; it fades at the old target and appears at the new target, eliminating
  the previously observed misplaced square.
- Integrity review: decoded checkpoints were inspected at ten-second intervals,
  with focused checks on the stale-predecessor denial, minimum context, one
  effect, verifier-only artifact, architecture, four-model proof, and end card.

## Corrected same-run framing

- User review identified two picture defects in candidate v2: an oversized
  selection highlight near `01:08` and later live-browser framing that cropped
  the page headline after the original operator scroll.
- The correction is a new read-only browser capture of the already persisted
  canonical run `demo-1787788603354`; it performs no workflow start, tick, or
  other cloud mutation. The source remains the same trace
  `51e492899892545e9fd706d7abdf16cb` and terminal `VERIFIED` state.
- Cutaway master:
  `artifacts/video/cutaway-20260827T020000Z/same-run-cutaway.webm` (SHA-256
  `fff66ddf496f428c8ef4bbc6cbf1b1b0de3fd73410d80602bf329140159bff29`).
- Editorial bounds were measured from the live DOM at 1920×1080 instead of
  estimated by eye: successor selection `373×271`, minimum context `373×205`,
  and continuity proof `478×243`.
- Corrected candidate:
  `artifacts/video/final-edit-20260827T013500Z/continuum-final-candidate-v3.mp4`.
- Runtime: 3:23.80. Video: 1920×1080 H.264 High Profile at 25 fps. Audio:
  48 kHz stereo AAC. SHA-256
  `d458744741f35b0f3e7872b9f471e5839f17b255545cfb86c43c27a6ec944688`.
- Focused one-frame-per-second inspection covered `01:08`, the corrected
  successor cut, minimum-context framing, and one-effect framing. The headline
  remains fully visible and each highlight now follows the measured content.
