"""Stage 3 — Generate: keyframe render + image-to-video animation per shot."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from auteur.config import settings
from auteur.dashscope import BASE, _auth, fetch_task
from auteur.jobs.polling import poll_until_done
from auteur.jobs.queue import JobQueue
from auteur.models import FilmProject, Shot, ShotStatus
from auteur.pipeline.design import _download, generate_image

logger = logging.getLogger(__name__)

_I2V_PATH = "/api/v1/services/aigc/video-generation/video-synthesis"


async def _create_video_task(
    image_path: Path,
    prompt: str,
    duration: int,
    seed: int | None,
) -> str:
    """Submit an image-to-video task to DashScope; return task_id."""
    import base64

    image_b64 = base64.b64encode(image_path.read_bytes()).decode()
    image_data_uri = f"data:image/png;base64,{image_b64}"

    params: dict = {"duration": duration}
    if seed is not None:
        params["seed"] = seed

    payload = {
        "model": settings.model_i2v,
        "input": {"image": image_data_uri, "prompt": prompt},
        "parameters": params,
    }
    headers = {**_auth(), "X-DashScope-Async": "enable"}

    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        resp = await client.post(_I2V_PATH, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()

    task_id = body.get("output", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"No task_id in i2v creation response: {body}")
    return task_id


async def generate_shot(
    shot: Shot,
    project: FilmProject,
    output_dir: Path,
    queue: JobQueue,
) -> Shot:
    """Render one shot: keyframe image then animated clip.

    Skips shots already in ACCEPTED state (idempotent).
    """
    if shot.status == ShotStatus.ACCEPTED:
        return shot

    shot_dir = output_dir / project.id / "shots" / str(shot.index)
    shot_dir.mkdir(parents=True, exist_ok=True)

    shot.status = ShotStatus.GENERATING
    shot.attempts += 1

    # --- Keyframe ---
    keyframe_path = shot_dir / "keyframe.png"
    if not keyframe_path.exists():
        kf_prompt = _keyframe_prompt(shot, project)
        logger.info("shot %d: generating keyframe", shot.index)

        async def _gen_keyframe() -> None:
            await generate_image(kf_prompt, keyframe_path, size="1280*720", seed=project.seed)
            project.cost.image_count += 1

        await queue.run(_gen_keyframe())

    shot.keyframe_path = str(keyframe_path)

    # --- Animate keyframe → clip ---
    clip_path = shot_dir / f"clip_attempt{shot.attempts}.mp4"
    if not clip_path.exists():
        logger.info("shot %d: animating keyframe (attempt %d)", shot.index, shot.attempts)

        async def _animate() -> None:
            task_id = await _create_video_task(
                keyframe_path,
                shot.prompt,
                int(shot.duration),
                project.seed,
            )
            shot.generation_params = {"model": settings.model_i2v, "task_id": task_id}

            result = await poll_until_done(task_id, fetch_task)
            video_url = result.get("output", {}).get("video_url")
            if not video_url:
                raise RuntimeError(f"No video_url in i2v result: {result}")

            await _download(video_url, clip_path)
            project.cost.video_seconds += shot.duration

        await queue.run(_animate())

    shot.clip_path = str(clip_path)
    return shot


async def generate_all(project: FilmProject, output_dir: Path) -> FilmProject:
    """Generate all pending shots concurrently, bounded by the job queue."""
    queue = JobQueue()

    async def _process(shot: Shot) -> Shot:
        try:
            return await generate_shot(shot, project, output_dir, queue)
        except Exception as exc:
            logger.error("shot %d generation failed: %s", shot.index, exc)
            shot.status = ShotStatus.FAILED
            return shot

    tasks = [lambda s=shot: _process(s) for shot in project.shots]
    results = await queue.run_all(tasks)

    project.shots = [r if isinstance(r, Shot) else project.shots[i] for i, r in enumerate(results)]
    return project


def _keyframe_prompt(shot: Shot, project: FilmProject) -> str:
    refs = ""
    if shot.characters:
        names = ", ".join(shot.characters)
        refs = f" Characters present: {names}."
    return f"{shot.prompt}{refs} Style: {project.style}. {shot.continuity_note}"
