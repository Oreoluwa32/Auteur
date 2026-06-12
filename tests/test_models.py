"""Tests for state model serialisation and persistence."""

import json
import tempfile
from pathlib import Path

import pytest

from auteur.models import Character, FilmProject, Shot, ShotStatus, ProjectStatus


def _make_project() -> FilmProject:
    return FilmProject(
        logline="A lone astronaut discovers a garden on Mars",
        treatment="Two-act structure: discovery and wonder.",
        style="Cinematic sci-fi, desaturated reds and greens",
        palette=["#c0392b", "#27ae60", "#2c3e50"],
        shots=[
            Shot(
                index=0,
                prompt="Wide shot of desolate Martian landscape at dawn",
                duration=6.0,
                camera_note="Drone pull-back",
                characters=[],
                continuity_note="",
            ),
            Shot(
                index=1,
                prompt="Astronaut kneels beside a green sprout",
                duration=5.0,
                camera_note="Close-up, handheld",
                characters=["Astronaut"],
                continuity_note="Same red-dust terrain as shot 0",
            ),
        ],
        characters=[
            Character(
                name="Astronaut",
                description="Female astronaut, late 30s, orange suit, visor up",
            )
        ],
    )


def test_shot_defaults():
    shot = Shot(index=0, prompt="Test prompt")
    assert shot.status == ShotStatus.PENDING
    assert shot.attempts == 0
    assert shot.duration == 5.0


def test_project_defaults():
    project = FilmProject(logline="Test logline")
    assert project.status == ProjectStatus.PENDING
    assert project.cost.input_tokens == 0
    assert len(project.shots) == 0


def test_project_serialisation_roundtrip():
    project = _make_project()
    data = json.loads(project.model_dump_json())
    restored = FilmProject.model_validate(data)
    assert restored.logline == project.logline
    assert len(restored.shots) == len(project.shots)
    assert restored.shots[1].characters == ["Astronaut"]


def test_project_save_and_load():
    project = _make_project()
    with tempfile.TemporaryDirectory() as tmp:
        project.save(tmp)
        loaded = FilmProject.load(tmp, project.id)
    assert loaded.id == project.id
    assert loaded.logline == project.logline
    assert len(loaded.characters) == 1
    assert loaded.characters[0].name == "Astronaut"


def test_project_save_idempotent():
    project = _make_project()
    with tempfile.TemporaryDirectory() as tmp:
        project.save(tmp)
        project.treatment = "Updated treatment"
        project.save(tmp)
        loaded = FilmProject.load(tmp, project.id)
    assert loaded.treatment == "Updated treatment"
