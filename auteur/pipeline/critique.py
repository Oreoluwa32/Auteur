"""Stage 4 — Critique: vision-score each shot and retry below threshold."""

from __future__ import annotations

import logging
from pathlib import Path

from openai import AsyncOpenAI

from auteur.config import settings
from auteur.models import FilmProject, Shot, ShotStatus

logger = logging.getLogger(__name__)

_CRITIC_SYSTEM = """\
You are a film quality critic. Score a video frame against its intended shot description.

Respond with JSON only:
{
  "score": <float 0.0–1.0>,
  "action_match": <float 0.0–1.0>,
  "character_consistency": <float 0.0–1.0>,
  "artifact_penalty": <float 0.0–1.0>,
  "rationale": "<one sentence>"
}

Scoring rubric:
- action_match: does the frame match the intended action and framing?
- character_consistency: are present characters consistent with their reference descriptions?
- artifact_penalty: 1.0 = no artifacts, 0.0 = severe artifacts.
- score: weighted average (0.4 * action_match + 0.3 * character_consistency + 0.3 * artifact_penalty).
"""


async def critique_shot(
    shot: Shot,
    project: FilmProject,
) -> Shot:
    """Score the shot's keyframe with Qwen-VL. Updates shot.critic_score."""
    if not shot.keyframe_path or not Path(shot.keyframe_path).exists():
        logger.warning("shot %d: no keyframe to critique", shot.index)
        return shot

    client = AsyncOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )

    import base64, json as _json
    image_data = base64.b64encode(Path(shot.keyframe_path).read_bytes()).decode()

    character_context = ""
    if shot.characters:
        descs = {c.name: c.description for c in project.characters if c.name in shot.characters}
        character_context = "\n".join(f"- {n}: {d}" for n, d in descs.items())

    user_content = [
        {
            "type": "text",
            "text": (
                f"Intended shot: {shot.prompt}\n"
                f"Camera note: {shot.camera_note}\n"
                f"Characters expected:\n{character_context or 'none'}\n\n"
                "Score this keyframe."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_data}"},
        },
    ]

    response = await client.chat.completions.create(
        model=settings.model_critic,
        messages=[
            {"role": "system", "content": _CRITIC_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
    )

    project.cost.input_tokens += response.usage.prompt_tokens if response.usage else 0
    project.cost.output_tokens += response.usage.completion_tokens if response.usage else 0

    raw = response.choices[0].message.content or "{}"
    try:
        data = _json.loads(raw)
        shot.critic_score = float(data.get("score", 0.0))
        logger.info("shot %d score=%.2f: %s", shot.index, shot.critic_score, data.get("rationale", ""))
    except (ValueError, KeyError) as exc:
        logger.error("shot %d: failed to parse critic response: %s", shot.index, exc)
        shot.critic_score = 0.0

    return shot


async def critique_and_retry(project: FilmProject, output_dir: Path) -> FilmProject:
    """Score all shots; re-generate those below threshold up to max_attempts."""
    from auteur.pipeline.generate import generate_shot
    from auteur.jobs.queue import JobQueue

    queue = JobQueue()
    threshold = settings.critic_threshold
    max_attempts = settings.max_shot_attempts

    for shot in project.shots:
        if shot.status == ShotStatus.FAILED:
            continue

        shot = await critique_shot(shot, project)

        while (shot.critic_score or 0.0) < threshold and shot.attempts < max_attempts:
            logger.info(
                "shot %d below threshold (%.2f < %.2f), retrying (attempt %d/%d)",
                shot.index, shot.critic_score, threshold, shot.attempts, max_attempts,
            )
            # Reset clip path to force re-generation
            shot.clip_path = None
            shot.status = ShotStatus.PENDING
            shot = await generate_shot(shot, project, output_dir, queue)
            shot = await critique_shot(shot, project)

        if (shot.critic_score or 0.0) >= threshold:
            shot.status = ShotStatus.ACCEPTED
        else:
            # Keep the best attempt even if below threshold
            logger.warning("shot %d accepted below threshold after %d attempts", shot.index, shot.attempts)
            shot.status = ShotStatus.ACCEPTED

    return project
