"""Top-level pipeline runner — executes all stages for a FilmProject."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from auteur.config import settings
from auteur.models import FilmProject, ProjectStatus
from auteur.pipeline import develop, design, generate, critique, voice, assemble

logger = logging.getLogger(__name__)


async def run(project: FilmProject) -> FilmProject:
    """Execute all pipeline stages in order, persisting state after each stage."""
    output_dir = Path(settings.output_dir)
    project_dir = Path(settings.project_dir)

    stages = [
        (ProjectStatus.DEVELOPING, _stage_develop),
        (ProjectStatus.DESIGNING, _stage_design),
        (ProjectStatus.GENERATING, _stage_generate),
        (ProjectStatus.CRITIQUING, _stage_critique),
        (ProjectStatus.VOICING, _stage_voice),
        (ProjectStatus.ASSEMBLING, _stage_assemble),
    ]

    for status, fn in stages:
        if _already_past(project.status, status):
            continue
        project.status = status
        project.save(project_dir)
        project = await fn(project, output_dir)
        project.save(project_dir)

    project.status = ProjectStatus.DONE
    project.save(project_dir)
    logger.info("project %s complete — film at %s", project.id, project.final_film_path)
    return project


async def _stage_develop(project: FilmProject, output_dir: Path) -> FilmProject:
    return await develop.develop(project)


async def _stage_design(project: FilmProject, output_dir: Path) -> FilmProject:
    return await design.design(project, output_dir)


async def _stage_generate(project: FilmProject, output_dir: Path) -> FilmProject:
    return await generate.generate_all(project, output_dir)


async def _stage_critique(project: FilmProject, output_dir: Path) -> FilmProject:
    return await critique.critique_and_retry(project, output_dir)


async def _stage_voice(project: FilmProject, output_dir: Path) -> FilmProject:
    return await voice.generate_narrator(project, output_dir)


async def _stage_assemble(project: FilmProject, output_dir: Path) -> FilmProject:
    return await asyncio.to_thread(assemble.assemble, project, output_dir)


_STATUS_ORDER = list(ProjectStatus)


def _already_past(current: ProjectStatus, target: ProjectStatus) -> bool:
    try:
        return _STATUS_ORDER.index(current) > _STATUS_ORDER.index(target)
    except ValueError:
        return False
