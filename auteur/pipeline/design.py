"""Stage 2 — Design: generate the story bible (character refs + style frame)."""

from __future__ import annotations

import logging
from pathlib import Path

from auteur.config import settings
from auteur.models import Character, FilmProject

logger = logging.getLogger(__name__)


def _character_image_prompt(character: Character, style: str, palette: list[str]) -> str:
    palette_str = ", ".join(palette) if palette else "cinematic"
    return (
        f"Character reference sheet. {character.description}. "
        f"Style: {style}. Color palette: {palette_str}. "
        "Full-body portrait, neutral pose, white background, high detail."
    )


def _style_frame_prompt(style: str, palette: list[str], treatment: str) -> str:
    palette_str = ", ".join(palette) if palette else "cinematic"
    return (
        f"Establishing shot. {treatment[:200]}. "
        f"Visual style: {style}. Color palette: {palette_str}. "
        "Cinematic composition, 16:9 aspect ratio."
    )


async def design(project: FilmProject, output_dir: Path) -> FilmProject:
    """Generate character reference images and a style frame, persist paths to project.

    Uses wan2.7-image via the DashScope async task API.
    Mutates and returns the project; caller persists state.
    """
    from auteur.jobs.polling import poll_until_done
    from auteur.client import dashscope_client  # lazy import to avoid circular deps

    bible_dir = output_dir / project.id / "bible"
    bible_dir.mkdir(parents=True, exist_ok=True)

    client = dashscope_client()

    for character in project.characters:
        if character.reference_image_paths:
            logger.info("skipping %s — reference images already exist", character.name)
            continue

        prompt = _character_image_prompt(character, project.style, project.palette)
        logger.info("generating reference image for character: %s", character.name)

        task = await client.images.generate(
            model=settings.model_image,
            prompt=prompt,
            n=1,
            size="1024x1024",
            seed=character.locked_seed,
        )

        image_url = task.data[0].url if task.data else None
        if image_url:
            dest = bible_dir / f"{character.name.lower().replace(' ', '_')}_ref.png"
            await _download(image_url, dest)
            character.reference_image_paths = [str(dest)]
            project.cost.image_count += 1

    # Style frame (world reference)
    style_path = bible_dir / "style_frame.png"
    if not style_path.exists():
        prompt = _style_frame_prompt(project.style, project.palette, project.treatment)
        logger.info("generating style frame")
        task = await client.images.generate(
            model=settings.model_image,
            prompt=prompt,
            n=1,
            size="1920x1080",
            seed=project.seed,
        )
        url = task.data[0].url if task.data else None
        if url:
            await _download(url, style_path)
            project.cost.image_count += 1

    return project


async def _download(url: str, dest: Path) -> None:
    """Download a URL to a local path."""
    import httpx

    async with httpx.AsyncClient() as http:
        resp = await http.get(url, follow_redirects=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    logger.debug("saved %s", dest)
