"""Stage 5 — Voice: narrator TTS and music bed."""

from __future__ import annotations

import logging
from pathlib import Path

from openai import AsyncOpenAI

from auteur.config import settings
from auteur.models import FilmProject

logger = logging.getLogger(__name__)


async def generate_narrator(project: FilmProject, output_dir: Path) -> FilmProject:
    """Synthesise narrator voiceover from project.narrator_script via CosyVoice."""
    if project.narrator_audio_path and Path(project.narrator_audio_path).exists():
        logger.info("narrator audio already exists, skipping")
        return project

    if not project.narrator_script:
        logger.info("no narrator script, skipping TTS")
        return project

    audio_dir = output_dir / project.id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    dest = audio_dir / "narrator.wav"

    client = AsyncOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )

    logger.info("synthesising narrator voiceover (%d chars)", len(project.narrator_script))

    # CosyVoice via DashScope TTS endpoint
    response = await client.audio.speech.create(
        model="cosyvoice-v1",
        voice="longxiaochun",
        input=project.narrator_script,
        response_format="wav",
    )

    dest.write_bytes(response.content)
    project.narrator_audio_path = str(dest)
    logger.info("narrator audio saved to %s", dest)
    return project
