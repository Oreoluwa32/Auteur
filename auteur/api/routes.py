"""HTTP API routes for Auteur."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from auteur.config import settings
from auteur.models import FilmProject

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory registry of running/completed projects (process-local)
_projects: dict[str, FilmProject] = {}


class CreateProjectRequest(BaseModel):
    logline: str
    seed: int | None = None


class ProjectResponse(BaseModel):
    id: str
    logline: str
    status: str
    shot_count: int
    final_film_path: str | None
    cost: dict


@router.post("/projects", response_model=ProjectResponse, status_code=202)
async def create_project(req: CreateProjectRequest, background_tasks: BackgroundTasks) -> ProjectResponse:
    """Start a new film project. Returns immediately; pipeline runs in background."""
    project = FilmProject(logline=req.logline, seed=req.seed)
    _projects[project.id] = project
    background_tasks.add_task(_run_pipeline, project)
    return _to_response(project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str) -> ProjectResponse:
    """Get current status of a project. Loads from disk if not in memory."""
    project = _get_or_load(project_id)
    return _to_response(project)


@router.get("/projects/{project_id}/shots")
async def list_shots(project_id: str) -> list[dict]:
    """List all shots with their current generation status."""
    project = _get_or_load(project_id)
    return [s.model_dump() for s in project.shots]


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


async def _run_pipeline(project: FilmProject) -> None:
    from auteur.runner import run
    try:
        updated = await run(project)
        _projects[updated.id] = updated
    except Exception as exc:
        logger.error("pipeline failed for project %s: %s", project.id, exc)
        project.status = project.status  # keep last known status


def _get_or_load(project_id: str) -> FilmProject:
    if project_id in _projects:
        return _projects[project_id]
    try:
        p = FilmProject.load(settings.project_dir, project_id)
        _projects[project_id] = p
        return p
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


def _to_response(project: FilmProject) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        logline=project.logline,
        status=project.status.value,
        shot_count=len(project.shots),
        final_film_path=project.final_film_path,
        cost=project.cost.model_dump(),
    )
