# Continuum proof-first production runbook

## Source lock

Do not overwrite or rename the accepted submission master or canonical capture.

- Accepted submission master:
  `artifacts/video/proof-first-candidate-v2-20260828T150000Z/continuum-proof-first-candidate.mp4`
- Accepted narration/music mix:
  `artifacts/video/proof-first-audio-v2-20260828/continuum-proof-first-narration-music.wav`

- Live source:
  `artifacts/video/capture/final-v19-20260828T015202Z/live-workflow-master.webm`
- Live manifest:
  `artifacts/video/capture/final-v19-20260828T015202Z/manifest.json`
- Model-chain source:
  `artifacts/video/model-chain-final-v19-20260828T015647Z/four-model-chain.webm`
- Architecture source: `docs/diagrams/architecture-video.svg`
- Release truth: `docs/submission/current-release.json`

The visual renderer validates `VERIFIED`, v19, run ID, trace ID, and canonical
release counts before recording.

## Production sequence

1. Render a timecoded visual-only review master from the proof-first scaffold.
2. Inspect frames at every cut and at the click, selection, context, effect,
   verifier, cloud-proof, architecture, and end-card holds.
3. Use the accepted ten-take Gemini TTS mix, or record replacement creator
   narration as short mono WAV takes in a quiet room.
4. Edit only pauses, breaths that obscure words, and obvious mistakes. Preserve
   the accepted approximately 118–133 WPM delivery range.
5. Fit picture to the accepted voice within 3:58; never speed the live click or
   first deadline transition.
6. Validate the manually checked sidecar `.srt` file against the final master.
7. Mix narration to roughly -16 LUFS integrated with true peak below -1 dBTP.
   Keep any Lyria cue at least 20 dB below narration.
8. Render H.264 High Profile, 1920×1080, 25 fps, mono AAC, with fast
   start enabled by the final host/transcoder if available.
9. Upload as a public YouTube or Vimeo video. Confirm the public player reports
   less than four minutes and captions are correct.
10. Update the existing Devpost project only after the public URL and playback
    have been verified. Re-read the project afterward.

## Frame review checklist

- [ ] Frame 1 is the four-second submission identification slate.
- [ ] The working product appears by 0:04 and the start click is visible by 0:09.
- [ ] `.run.app`, run ID, and trace correlation remain readable where claimed.
- [ ] Every temporal jump is visibly disclosed.
- [ ] No obsolete v18 handoff label appears in the accepted crop.
- [ ] v19 selection and v20 rejection are simultaneously understandable.
- [ ] The minimum-context frame shows both included and excluded counts.
- [ ] The supplier scene names GLEIF, VIES, Gemini, deterministic admission,
      and `SANDBOX_ONLY` without implying a real procurement decision.
- [ ] The effect scene shows two deliveries, one effect, and zero duplicates.
- [ ] The verifier scene does not make the executor appear to attest itself.
- [ ] Exact-release proof says 17 objects, 174 spans, offline PASS, commit
      d4d7d52.
- [ ] Released multimodal evidence is never labelled same-run.
- [ ] No secrets, private URLs, tokens, personal notifications, or unrelated
      tabs are visible.
- [ ] Final duration is at most 3:58.00 and remains below the four-minute rule.
- [ ] The 2:04 and 2:25 same-run disclosures never obscure the evidence.
- [ ] The released learning proof visibly reaches step 4 before the closing card.

## Publication copy

**Title**

`Continuum — The Promise Survives | Safe Agent Succession on Google Cloud`

**First description line**

`Created for the All Things Agentic Hackathon: Continuum detects silent agent failure, transfers one governed obligation to an eligible successor, completes one bounded external effect, and proves the outcome independently.`

The description must link the repository, hosted showcase, exact cloud-proof
release, and hackathon page. Publish publicly rather than unlisted.
