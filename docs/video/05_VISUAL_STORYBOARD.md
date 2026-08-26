# Continuum demo video — visual storyboard

## Locked format

- Canvas: 1920×1080, 30 fps, 16:9.
- Maximum runtime: 3:58; no content may touch the four-minute boundary.
- The canonical run is started exactly once on camera.
- Cockpit polling is observational. No cursor action advances lifecycle state.
- A proof cutaway may magnify evidence from that same run, but may not replace
  it with historical evidence or visually imply that an old run is fresh.
- Use hard cuts for trust-boundary changes and gentle 250–350 ms crops for
  attention. Avoid decorative transitions, kinetic captions, and fake terminal
  typing.
- Cursor stays parked after **Start recovery**. A small click ring appears only
  for that one authorized interaction.

## Screen grammar

The viewer should always know which kind of evidence is on screen:

- **LIVE RUN** — cyan top-left slug; current cockpit and fresh identifiers.
- **SAME-RUN PROOF** — green top-left slug; magnified raw evidence from the
  current run.
- **REFERENCE ARCHITECTURE** — violet top-left slug; explanatory diagram, not
  runtime evidence.

Never use a simulated console. Exact identifiers remain selectable text or
native Cloud Console content. Sensitive tokens, browser chrome, unrelated tabs,
notifications, and account avatars are excluded from capture.

## Master timeline

### 1 · The silent failure — 00:00–00:23

- **00:00–00:03** — dark Continuum mark; thesis appears in two beats:
  `Agents can fail.` then `Their obligations must not.`
- **00:03–00:12** — full live cockpit hero, no cursor movement. Hold the
  `€250,000` obligation card at readable scale.
- **00:12–00:20** — 112% crop toward the obligation description and READY state.
- **00:20–00:23** — ease back to reveal **Start recovery**. Do not click early.

Acceptance: the problem is understandable before any cloud service is named.

### 2 · One click, then autonomy — 00:23–00:47

- **00:23** — click **Start recovery** exactly once; subtle click ring, no sound
  effect.
- **00:24–00:29** — hold fresh run and correlation IDs. Add a restrained lower
  third: `server-owned run · browser observes only`.
- **00:29–00:38** — crop to the autonomous-chain panel as Promise Ledger and
  deadline observations arrive.
- **00:38–00:47** — remain parked. Let the missing-event observation arrive
  without further input.

Acceptance: the video itself proves that lifecycle progress was not driven by
repeated browser actions.

### 3 · Failure handling and bounded Gemini — 00:47–01:13

- **00:47–00:56** — same-run chain; emphasize the Pub/Sub observation.
- **00:56–01:03** — compact proof chip beside the chain:
  `delivery attempt 1 → deliberate failure` / `attempt 2 → resumed`.
- **01:03–01:10** — show ADK/Gemini observation with model name and bounded
  proposed action; full trace ID stays visible but is not narrated.
- **01:10–01:13** — remove proof chip before moving to candidate selection.

Acceptance: redelivery and the real model call are visibly evidenced, not
merely stated by narration.

### 4 · Dynamic successor selection — 01:13–01:46

- **01:13–01:19** — 130% crop on the succession-decision panel.
- **01:19–01:29** — reveal v18 and v19 as eligible, then v20 as rejected with
  `HEALTH_UNVERIFIED · JURISDICTION_MISMATCH` legible.
- **01:29–01:39** — hold `v18 selected by Gemini`; show its deployed endpoint,
  workload identity, and image digest in a same-run proof drawer. Reserve the
  exact serving revision for the independently read `/build-info` cutaway.
- **01:39–01:46** — highlight the independent deterministic-policy admission.

Acceptance: the judge can distinguish deterministic eligibility, model choice,
and authoritative policy validation.

### 5 · Fence and minimum context — 01:46–02:19

- **01:46–01:57** — same-run denial pair side by side:
  `v17 ACTION → DENIED · STALE_EPOCH` and
  `v17 MEMORY → DENIED · 0 candidates examined`.
- **01:57–02:08** — crop to minimum context: `2 included · 4 excluded`.
- **02:08–02:15** — item-level receipt: two green verified facts, followed by
  four red exclusion classes. Do not reveal secret values or raw injection.
- **02:15–02:19** — return briefly to the denial pair for “Continuum can say
  no.”

Acceptance: negative evidence is readable, and excluded data is represented by
class and digest only.

### 6 · One consequential effect — 02:19–02:46

- **02:19–02:29** — action-gateway checklist fills once: identity, epoch,
  policy, compliance, context receipt, idempotency.
- **02:29–02:37** — show `Pub/Sub deliveries · 2` beside the stable provider
  resource identity.
- **02:37–02:43** — hold `1 provider effect · 0 duplicates` for at least five
  seconds.
- **02:43–02:46** — no visual gag; let the dry line land over the proof.

Acceptance: the claim remains scoped to this gateway/provider model and the
same deterministic idempotency key.

### 7 · Independent proof — 02:46–03:16

- **02:46–02:55** — five control-authored artifacts appear as compact digest
  cards: obligation, grant, manifest, revocation, receipt.
- **02:55–03:05** — clear trust-boundary cut to the verifier identity and its
  read-only Firestore role.
- **03:05–03:12** — artifact six enters from the verifier side only; show the
  three-valued vocabulary, then settle on `VERIFIED`.
- **03:12–03:16** — hold attestation digest, fresh run ID, and exact trace ID.

Acceptance: the executor never appears to attest to its own success.

### 8 · Architecture as evidence — 03:16–03:43

- **03:16–03:27** — full 16:9 reference architecture. Illuminate its three
  horizontal bands in sequence: OBSERVE, GOVERN, PROVE.
- **03:27–03:36** — same-run Cloud proof strip: five Cloud Run revisions and
  distinct service identities, Firestore, Cloud Tasks, Pub/Sub, Gemini 3.6.
- **03:36–03:41** — native Cloud Trace view filtered to the exact trace ID;
  highlight the Gemini span and verifier span, plus total correlated span count.
- **03:41–03:43** — cut back to the verified cockpit for the signature line.

Acceptance: cloud services explain already-observed behavior; they are not a
technology-logo tour.

### 9 · Personal standard — 03:43–03:58

- **03:43–03:47** — verified cockpit fades to the Continuum end card.
- **03:47–03:55** — title: `Continuity Contract` with compact subtitle:
  `Portable contract · Google Cloud reference binding`.
- **03:55–03:58** — repository URL and `C0–C6 PASS`; hold the final frame.

Acceptance: no new claim appears after the narration ends, and the end card
remains visible long enough to read.

## Capture order

1. Record a short clean hero hold before starting.
2. Record one fresh canonical run continuously from the single click through
   `VERIFIED`; preserve the untouched recording as the evidentiary master.
3. While the same run still exists, capture its proof drawer, exact Cloud Trace,
   Cloud Run revision identities, and final cockpit as separate cutaways.
4. Capture the architecture and end card losslessly.
5. Edit picture to the approved scene masters; do not time-stretch the live run.
6. Export a draft with burnt-in timecode for technical review, then a clean
   submission master after every visual claim is checked against the run.

## Visual quality gate

- Every critical label is readable at 100% playback on a 13-inch 1080p screen.
- A viewer can freeze any proof frame and correlate run ID and trace ID.
- No identifier from a historical run is visible during the fresh-run sequence.
- No secrets, authorization headers, private URLs, unrelated browser tabs, or
  personal notifications are visible.
- No animation obscures a state transition.
- The final runtime is at most 3:58.00.
