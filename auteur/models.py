"""Persistent state models for a film project run."""

from __future__ import annotations

import uuid
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    PENDING = "pending"
    DEVELOPING = "developing"
    DESIGNING = "designing"
    GENERATING = "generating"
    CRITIQUING = "critiquing"
    VOICING = "voicing"
    ASSEMBLING = "assembling"
    DONE = "done"
    FAILED = "failed"


class ShotStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    CRITIQUING = "critiquing"
    ACCEPTED = "accepted"
    FAILED = "failed"


class Character(BaseModel):
    name: str
    description: str
    reference_image_paths: list[str] = Field(default_factory=list)
    locked_seed: Optional[int] = None


class Shot(BaseModel):
    index: int
    prompt: str
    duration: float = 5.0          # seconds
    camera_note: str = ""
    characters: list[str] = Field(default_factory=list)
    continuity_note: str = ""

    keyframe_path: Optional[str] = None
    clip_path: Optional[str] = None
    critic_score: Optional[float] = None
    attempts: int = 0
    status: ShotStatus = ShotStatus.PENDING

    # Reproducibility — record params used for each generation attempt
    generation_params: dict = Field(default_factory=dict)


class CostRecord(BaseModel):
    """Accumulated cost for a project run."""
    input_tokens: int = 0
    output_tokens: int = 0
    image_count: int = 0
    video_seconds: float = 0.0


class FilmProject(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    logline: str

    treatment: str = ""
    script: str = ""
    style: str = ""
    palette: list[str] = Field(default_factory=list)
    seed: Optional[int] = None

    characters: list[Character] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)

    narrator_script: str = ""
    narrator_audio_path: Optional[str] = None
    music_path: Optional[str] = None
    final_film_path: Optional[str] = None

    status: ProjectStatus = ProjectStatus.PENDING
    cost: CostRecord = Field(default_factory=CostRecord)

    def save(self, project_dir: str | Path) -> Path:
        """Persist project state to <project_dir>/<id>/project.json."""
        path = Path(project_dir) / self.id
        path.mkdir(parents=True, exist_ok=True)
        state_file = path / "project.json"
        state_file.write_text(self.model_dump_json(indent=2))
        return state_file

    @classmethod
    def load(cls, project_dir: str | Path, project_id: str) -> "FilmProject":
        """Load a previously saved project by id."""
        state_file = Path(project_dir) / project_id / "project.json"
        return cls.model_validate_json(state_file.read_text())
