# Continuum demo video — voice production

## Selected approach

Generate the English voice-over with Gemini 3.1 Flash TTS Preview in Google AI
Studio. Produce the narration as nine scene-aligned clips rather than one
four-minute file. Apply a 1.15x pitch-preserving tempo pass to approved raw
clips. This permits exact timing, clean regeneration, and deliberate pauses
without changing the delivery of already approved scenes.

## Model and voice

- Model: `gemini-3.1-flash-tts-preview`.
- Selected voice: Orus.
- AI Studio controls: Natural pace, Newscaster style, American (General)
  accent.
- Voice character: neutral international English; warm, mature, articulate,
  technically authoritative; restrained rather than theatrical.
- Avoid voices described as trailer, epic, announcer, high-energy, dramatic,
  whimsical, or sales.
- Prefer a voice with clear consonants and low vocal fry over a particularly
  distinctive character voice.

If the UI offers only voice selection and script input, voice character is a
selection criterion rather than a separate prompt.

## Paste-ready voice-design prompt

Use this only if DaVinci presents a dedicated voice-description or voice-design
field. Do not paste it into the spoken transcript field.

> A warm, mature, technically authoritative English-speaking narrator with a
> neutral international accent. Calm confidence, crisp consonants, natural
> conversational cadence, restrained enthusiasm, and subtle dry wit. Sounds
> like an experienced systems architect demonstrating a real production system,
> never like a commercial announcer, cinematic trailer, or synthetic assistant.
> Able to pronounce cloud engineering terminology clearly and make serious
> safety claims without melodrama.

## Delivery direction

Use the following as a project-level direction field if one exists. Otherwise,
encode the direction scene by scene with sparse ElevenLabs V3 audio tags.

> Narrate in clear international English with a warm, calm, technically
> authoritative delivery. Speak at a measured conversational pace. Pause briefly
> after important claims. Articulate technical terms clearly without reading
> complete hashes or identifiers. Deliver dry humorous lines subtly, as an
> understated observation rather than a joke. Keep the final personal statement
> sincere, thoughtful, and hopeful. Avoid sales energy, melodrama, exaggerated
> emphasis, robotic rhythm, and ominous trailer delivery.

## Inline direction policy

Gemini TTS interprets natural-language delivery direction and bracketed audio
tags. Put the durable direction in Sample Context and use at most one
directional tag at the start of most clips, such as:

- `[calm and assured]`
- `[precise and matter-of-fact]`
- `[with subtle dry humor]`
- `[sincere and thoughtful]`

Do not add laughs, sound effects, whispers, shouting, or stage reactions. Do not
use SSML break tags. Use sentences, em dashes, and ellipses sparingly to
establish rhythm.

## Locked Sample Context

> Professional technical product narration. Calm authority with warm human
> clarity. Maintain a brisk natural cadence, with no dead air. Pause briefly
> only after the opening thesis. Deliver every other sentence continuously and
> decisively. Use subtle dry wit, with no advertising voice and no corporate
> training cadence.

## Pronunciation normalization

The final TTS transcript should favor spoken forms:

| Display text | Voice text |
|---|---|
| EUR 250,000 | two hundred and fifty thousand euro |
| ADK | A D K |
| Pub/Sub | Pub Sub |
| v17 / v18 | version seventeen / version eighteen |
| 15/15 | all fifteen required evidence objects |
| 124 spans | one hundred and twenty-four correlated spans |
| SHA-256 | S H A two fifty-six |
| C0–C6 | conformance classes C zero through C six |

Do not ask the voice model to pronounce full run IDs, trace IDs, digests, service
accounts, image hashes, or Cloud Run revisions. Those belong on screen while the
narration describes what they bind.

## Generation and acceptance procedure

For each scene:

1. Generate one take with identical text and settings; generate an alternate
   only when the first take fails an explicit acceptance criterion.
2. Reject any take that invents a sound, drops a word, rushes a technical term,
   or performs the humor too broadly.
3. Select for intelligibility and natural thought grouping, not maximum drama.
4. Export the selected take as WAV if available; otherwise use the highest-
   quality lossless or highest-bitrate download offered.
5. Preserve the untouched exported clip and record its model, voice, settings,
   generation date, and exact transcript in the production log.
6. Apply a pitch-preserving 1.15x tempo pass, then edit silence and level only
   after the picture rehearsal establishes timing.

## Audio target

- Finished narration target: approximately 150–160 spoken words per minute.
- Integrated loudness target for the final web video: approximately -16 LUFS.
- True peak ceiling: -1 dBTP.
- No background music until the narration and live interface sounds work cleanly
  on their own. If music is later justified, it must remain unobtrusive and
  properly licensed and disclosed.
