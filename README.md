# Auteur

A director agent that turns a single logline into a finished, cinematically coherent short film.

Auteur orchestrates the full production pipeline: story development, visual bible creation,
per-shot generation with consistency checks, critic-driven retries, voice-over, and final
assembly — all from one prompt.

## What it does

1. **Develop** — Decomposes a logline into treatment → script → structured shot list (Qwen text).
2. **Design** — Generates a story bible: locked character reference images and style frame (Wan2.7-Image).
3. **Generate** — Renders a keyframe per shot consistent with the bible, then animates it (Wan2.7-I2V).
4. **Critique & retry** — A vision critic (Qwen-VL) scores each shot against its intent; failures are re-rolled up to N times.
5. **Voice & score** — Narrator voiceover (CosyVoice) and a music bed are added.
6. **Assemble** — ffmpeg stitches shots with transitions, audio mix, and titles into a final MP4.

## Architecture

```
auteur/
├── config.py          # Pydantic settings — all tunables via env vars
├── models.py          # State: FilmProject, Character, Shot
├── pipeline/
│   ├── develop.py     # Logline → shot list (Qwen)
│   ├── design.py      # Story bible generation (Wan image)
│   ├── generate.py    # Keyframe + video generation (Wan I2V/T2V)
│   ├── critique.py    # Vision critic + retry logic (Qwen-VL)
│   ├── voice.py       # TTS + music bed
│   └── assemble.py    # ffmpeg timeline assembly
├── jobs/
│   ├── queue.py       # Async job queue
│   └── polling.py     # Task polling with exponential backoff
└── api/
    ├── app.py         # FastAPI application
    └── routes.py      # HTTP endpoints
```

All video API calls are asynchronous — tasks are created then polled until done.
Runs are fully resumable: every stage persists its output before advancing.

## Quickstart

```bash
cp .env.example .env
# Fill in DASHSCOPE_API_KEY and adjust model/threshold settings

pip install -e ".[dev]"

# Verify your API key + model IDs work before a full run
bash scripts/smoke/run_all.sh

# Run a film
python -m auteur run "A lone astronaut discovers a garden on Mars" --seed 42

# Resume an interrupted run
python -m auteur resume <project-id>

# Check run status
python -m auteur status <project-id>

# Or start the API server
uvicorn auteur.api.app:app --reload
```

## Running tests

```bash
pytest
```

## Configuration

All settings are environment variables (see `.env.example`). Key ones:

| Variable | Default | Description |
|---|---|---|
| `DASHSCOPE_API_KEY` | — | Required. DashScope API key (Singapore region) |
| `CRITIC_THRESHOLD` | `0.7` | Minimum critic score to accept a shot |
| `MAX_SHOT_ATTEMPTS` | `3` | Max re-rolls per shot before keeping the best |
| `PARALLEL_SHOT_LIMIT` | `3` | Max shots generated concurrently |

## Requirements

- Python 3.11+
- ffmpeg installed and on `PATH`
- Alibaba Cloud DashScope account (Singapore / `-intl` region)
