"""Stage 3 — Generate: keyframe render + image-to-video animation per shot."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from auteur.config import settings
from auteur.jobs.queue import JobQueue
from auteur.models import FilmProject, Shot, ShotStatus

logger = logging.getLogger(__name__)


async def generate_shot(
    shot: Shot,
    project: FilmProject,
    output_dir: Path,
    queue: JobQueue,
) -> Shot:
    """Render one shot: keyframe image then animated clip.

    Skips shots already in ACCEPTED or GENERATING state (idempotent).
    """
    from auteur.client import dashscope_client
    from auteur.jobs.polling import poll_until_done, JobFailedError

    if shot.status == ShotStatus.ACCEPTED:
        return shot

    shot_dir = output_dir / project.id / "shots" / str(shot.index)
    shot_dir.mkdir(parents=True, exist_ok=True)

    client = dashscope_client()
    shot.status = ShotStatus.GENERATING
    shot.attempts += 1

    # --- Keyframe ---
    keyframe_path = shot_dir / "keyframe.png"
    if not keyframe_path.exists():
        kf_prompt = _keyframe_prompt(shot, project)
        logger.info("shot %d: generating keyframe", shot.index)

        async def _gen_keyframe() -> None:
            result = await client.images.generate(
                model=settings.model_image,
                prompt=kf_prompt,
                n=1,
                size="1920x1080",
                seed=project.seed,
            )
            url = result.data[0].url if result.data else None
            if url:
                from auteur.pipeline.design import _download
                await _download(url, keyframe_path)
                project.cost.image_count += 1

        await queue.run(_gen_keyframe())

    shot.keyframe_path = str(keyframe_path)

    # --- Animate keyframe → clip ---
    clip_path = shot_dir / f"clip_attempt{shot.attempts}.mp4"
    if not clip_path.exists():
        logger.info("shot %d: animating keyframe (attempt %d)", shot.index, shot.attempts)

        async def _animate() -> None:
            # DashScope i2v: create task, poll until done
            task_resp = await client.post(
                "/video/generations",
                body={
                    "model": settings.model_i2v,
                    "input": {
                        "image_url": _file_to_data_uri(keyframe_path),
                        "prompt": shot.prompt,
                    },
                    "parameters": {
                        "duration": int(shot.duration),
                        "seed": project.seed,
                    },
                },
                cast_to=dict,
            )
            task_id = task_resp["output"]["task_id"]
            shot.generation_params = {"model": settings.model_i2v, "task_id": task_id}

            async def _fetch(tid: str) -> dict:
                return await client.get(f"/video/generations/{tid}", cast_to=dict)

            final = await poll_until_done(task_id, _fetch)
            video_url = final["output"]["video_url"]

            from auteur.pipeline.design import _download
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


def _file_to_data_uri(path: Path) -> str:
    import base64
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{data}"
