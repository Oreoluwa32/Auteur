# CLAUDE.md — Auteur

Working name: **Auteur**. A director agent that turns a single
logline into a finished, cinematically coherent short film.

Hackathon: Global AI Hackathon Series with Qwen Cloud — **AI Showrunner** track.
Solo build, ~50 hours, deadline **July 9, 2026**. Public, open-source, MIT.

---

## What "high standard" means here

Map every decision to the judging weights and to one anti-goal.

- Technical Depth & Engineering (30%) — async job orchestration, a closed-loop
  self-critique system, reproducible runs, real error handling. Not a script
  that fires one API call.
- Innovation & AI Creativity (30%) — the consistency engine + the critic/retry
  loop are the novel contributions, not the raw video model.
- Problem Value & Impact (25%) — one-person film production; a clear, demoable
  real use.
- Presentation & Docs (15%) — the demo ENDS by playing the film the agent made.

**Anti-goal:** a thin wrapper around `wan2.7-t2v`. The model makes one clip;
Auteur is the *director* that plans a multi-shot story, keeps characters and
world consistent across many generations, judges each shot, and edits the result
into a coherent film. The orchestration is the product.

---

## Core thesis

Three pillars carry the project. Build them deep; everything else is support.

1. **Consistency engine.** A persisted "story bible": locked character reference
   images, world/style descriptors, and a color palette. Every shot is generated
   against these references (via reference-to-video / image-to-video from a
   locked keyframe) so faces, costumes, and settings stay stable shot-to-shot.

2. **Director agent with self-critique.** A planning loop (Qwen) decomposes the
   logline into treatment → script → shot list with per-shot prompts and
   continuity notes. After each shot is generated, a vision critic (Qwen-VL)
   scores it against the intended shot description and the bible; failures are
   re-rolled (best-of-N, bounded retries). This closed loop is the engineering
   centerpiece.

3. **Assembly layer.** An ffmpeg-based timeline stitches shots with transitions,
   lays a narrator voiceover and music track, adds titles, and renders the final
   MP4. Deterministic and reproducible from saved project state.

---

## Pipeline (stages)

1. **Develop** — logline → treatment → script → shot list. [Qwen text]
   Output is structured JSON: ordered shots, each with prompt, duration, camera
   note, characters present, continuity note.
2. **Design** — generate the story bible: character reference sheets and a style
   frame, with locked seeds + palette. [Wan2.7-Image, up to 9 reference images]
3. **Generate** — per shot: render a keyframe consistent with the bible, then
   animate it. [Wan2.7-Image → wan2.7-i2v; use wan2.7-r2v for character-heavy
   shots to preserve identity/voice]
4. **Critique & retry** — vision-score each shot vs its intended description and
   the bible; re-roll below threshold, up to N attempts; keep the best. [Qwen-VL]
5. **Voice & score** — narrator VO (TTS, e.g. CosyVoice) and a music bed; or use
   wan2.7-t2v native audio where a shot needs diegetic sound.
6. **Assemble** — ffmpeg timeline → transitions, audio mix, titles → final MP4.

---

## State model (persist everything; runs must be reproducible)

- `FilmProject`: id, logline, treatment, style, palette, seed, status, cost.
- `Character`: name, description, reference_image_paths, locked seed.
- `Shot`: index, prompt, duration, characters, continuity_note, keyframe_path,
  clip_path, critic_score, attempts, status.

Persist to disk/DB as the pipeline advances so a run is resumable and a film is
reproducible from saved state + seeds.

---

## Tech stack

- **Director / writer:** Qwen text (`qwen-max` for planning quality; `qwen-plus`
  for cheaper steps). OpenAI-compatible endpoint.
- **Critic:** Qwen-VL (vision) — scores generated frames against intent.
- **Stills / keyframes / bible:** Wan2.7-Image (reference images + palette).
- **Video:** `wan2.7-i2v` (animate keyframes), `wan2.7-r2v` (character/voice
  consistency), `wan2.7-t2v` (shots needing native multi-shot audio). Use
  `wan-std` for drafts, `wan-pro` only for final renders to control cost.
- **Voice:** CosyVoice (or Wan native audio).
- **Assembly:** ffmpeg.
- **Backend:** FastAPI on Alibaba Cloud. Video APIs are ASYNCHRONOUS — create
  task, then poll; clips take 1–5 min. Build a job queue with polling, backoff,
  and retries around this.
- **Region:** model, endpoint, and API key must all be the SAME region
  (Singapore / `-intl`). Cross-region calls fail.

---

## Engineering standards

- Fully typed; small, single-responsibility modules; docstrings on public APIs.
- Async orchestration for all video jobs: task creation, polling, exponential
  backoff, bounded retries, timeouts. No blocking sleeps in request paths.
- Generate shots in parallel where independent; respect rate limits.
- Idempotent, resumable runs keyed by project id; never regenerate completed shots.
- Locked seeds for reproducibility; record every model call's params.
- Cost tracking per run (tokens + video seconds); surface a running total.
- Structured logging; clear error types; graceful degradation (a failed shot
  falls back to its keyframe as a still, never crashes the whole film).
- Config-driven (models, thresholds, retry counts) via env/config, not literals.
- Tests for: shot-list schema parsing, the critic threshold/retry logic, the
  assembly timeline math (durations/offsets), and job-polling state transitions.

---

## Quality gates

- **Critic rubric:** each shot scored on (a) matches intended action/framing,
  (b) character consistency vs bible, (c) no obvious artifacts. Below threshold
  → retry. Cap attempts; keep best-scoring.
- **Consistency metric:** embed character faces/keyframes and measure similarity
  across shots; report it as a headline number.
- **Golden logline:** one fixed test logline used as a regression check that the
  full pipeline still produces a coherent film end-to-end.

---

## Scope (MUST / SHOULD / STRETCH)

MUST:
- Logline → structured shot list (6–8 shots).
- Story bible with 1–2 consistent characters (locked refs).
- Per-shot keyframe → animate; one consistency-preserving path working.
- ffmpeg assembly into a 45–60s film with narrator VO + music + titles.
- Reproducible runs, cost tracking, async job orchestration.

SHOULD:
- Critic + retry loop (start best-of-2 with a simple vision check).
- Lightweight web UI showing the storyboard populate live, then playing the film.
- Consistency metric reported.

STRETCH:
- wan2.7-videoedit polish pass; richer transitions; multiple characters;
  user-editable shot list before render.

---

## Git rules

- Branch `main`: stable only. Merge from master after tests pass.
- Branch `master`: active development. All day-to-day work happens here.
- Commit author: OreoDev01 <adewalepete08@gmail.com> — no AI attribution.
- Conventional imperative commit messages. No TODOs, no dead code.
