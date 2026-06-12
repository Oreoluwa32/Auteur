"""Stage 1 — Develop: logline → treatment → script → structured shot list."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from auteur.config import settings
from auteur.models import FilmProject, Shot

logger = logging.getLogger(__name__)

_SHOT_LIST_SCHEMA = {
    "type": "object",
    "required": ["treatment", "style", "palette", "narrator_script", "shots"],
    "properties": {
        "treatment": {"type": "string"},
        "style": {"type": "string"},
        "palette": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "narrator_script": {"type": "string"},
        "shots": {
            "type": "array",
            "minItems": 6,
            "maxItems": 8,
            "items": {
                "type": "object",
                "required": ["index", "prompt", "duration", "camera_note", "characters", "continuity_note"],
                "properties": {
                    "index": {"type": "integer"},
                    "prompt": {"type": "string"},
                    "duration": {"type": "number"},
                    "camera_note": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "continuity_note": {"type": "string"},
                },
            },
        },
    },
}

_SYSTEM_PROMPT = """\
You are a professional film director and screenwriter. Given a logline, produce a
structured production plan in JSON format exactly matching the provided schema.

Guidelines:
- 6–8 shots totalling 45–60 seconds (each shot 5–10s).
- Each shot prompt is a single, vivid visual description suitable for a text-to-video model.
- Style and palette define the visual language for the entire film.
- Continuity notes describe what must persist from the previous shot (costume, lighting, position).
- Narrator script is a single flowing paragraph read over the assembled film.
"""


def _build_user_prompt(logline: str) -> str:
    return (
        f'Logline: "{logline}"\n\n'
        f"Respond with valid JSON matching this schema:\n{json.dumps(_SHOT_LIST_SCHEMA, indent=2)}"
    )


def _parse_shot_list(raw: str) -> dict[str, Any]:
    """Extract JSON from the model response, tolerating markdown code fences."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(raw)


async def develop(project: FilmProject) -> FilmProject:
    """Populate project with treatment, shot list, and style from the logline.

    Mutates and returns the project; caller is responsible for persisting state.
    """
    client = AsyncOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )

    logger.info("developing shot list for project %s", project.id)

    response = await client.chat.completions.create(
        model=settings.model_director,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(project.logline)},
        ],
        temperature=0.8,
        response_format={"type": "json_object"},
    )

    project.cost.input_tokens += response.usage.prompt_tokens if response.usage else 0
    project.cost.output_tokens += response.usage.completion_tokens if response.usage else 0

    raw = response.choices[0].message.content or ""
    data = _parse_shot_list(raw)

    project.treatment = data["treatment"]
    project.style = data["style"]
    project.palette = data.get("palette", [])
    project.narrator_script = data.get("narrator_script", "")
    project.shots = [Shot(**s) for s in data["shots"]]

    logger.info("developed %d shots", len(project.shots))
    return project
