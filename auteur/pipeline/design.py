"""Stage 2 — Design: generate the story bible (character refs + style frame)."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from auteur.config import settings
from auteur.dashscope import BASE, _auth, fetch_task
from auteur.jobs.polling import poll_until_done
from auteur.models import Character, FilmProject

logger = logging.getLogger(__name__)

_T2I_PATH = "/api/v1/services/aigc/text2image/image-synthesis"


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


async def _create_image_task(
    prompt: str,
    *,
    size: str = "1024*1024",
    seed: int | None = None,
) -> str:
    """Submit a text-to-image task to DashScope; return task_id."""
    params: dict = {"size": size, "n": 1}
    if seed is not None:
        params["seed"] = seed

    payload = {
        "model": settings.model_image,
        "input": {"prompt": prompt},
        "parameters": params,
    }
    headers = {**_auth(), "X-DashScope-Async": "enable"}

    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        resp = await client.post(_T2I_PATH, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()

    task_id = body.get("output", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"No task_id in image creation response: {body}")
    return task_id


async def generate_image(
    prompt: str,
    dest: Path,
    *,
    size: str = "1024*1024",
    seed: int | None = None,
) -> None:
    """Generate one image and save it to dest.

    Creates a DashScope async task, polls until SUCCEEDED, downloads the result.
    """
    task_id = await _create_image_task(prompt, size=size, seed=seed)
    logger.debug("image task_id=%s", task_id)
    result = await poll_until_done(task_id, fetch_task)
    results = result.get("output", {}).get("results", [])
    url = results[0].get("url") if results else None
    if not url:
        raise RuntimeError(f"No URL in image task result: {result}")
    await _download(url, dest)


async def design(project: FilmProject, output_dir: Path) -> FilmProject:
    """Generate character reference images and a style frame; persist paths to project.

    Mutates and returns the project; caller persists state.
    """
    bible_dir = output_dir / project.id / "bible"
    bible_dir.mkdir(parents=True, exist_ok=True)

    for character in project.characters:
        if character.reference_image_paths:
            logger.info("skipping %s — reference images already exist", character.name)
            continue

        prompt = _character_image_prompt(character, project.style, project.palette)
        logger.info("generating reference image for character: %s", character.name)
        dest = bible_dir / f"{character.name.lower().replace(' ', '_')}_ref.png"
        await generate_image(prompt, dest, size="1024*1024", seed=character.locked_seed)
        character.reference_image_paths = [str(dest)]
        project.cost.image_count += 1

    style_path = bible_dir / "style_frame.png"
    if not style_path.exists():
        prompt = _style_frame_prompt(project.style, project.palette, project.treatment)
        logger.info("generating style frame")
        await generate_image(prompt, style_path, size="1280*720", seed=project.seed)
        project.cost.image_count += 1

    return project


async def _download(url: str, dest: Path) -> None:
    """Download a URL to a local path."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    logger.debug("saved %s", dest)
