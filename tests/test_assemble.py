"""Tests for assembly timeline math: duration totals and shot ordering."""

import pytest

from auteur.models import FilmProject, Shot, ShotStatus
from auteur.pipeline.assemble import _total_duration


def _accepted_shot(index: int, duration: float) -> Shot:
    s = Shot(index=index, prompt=f"Shot {index}", duration=duration)
    s.status = ShotStatus.ACCEPTED
    return s


def _pending_shot(index: int, duration: float) -> Shot:
    return Shot(index=index, prompt=f"Shot {index}", duration=duration)


def test_total_duration_all_accepted():
    project = FilmProject(logline="test")
    project.shots = [_accepted_shot(i, 5.0) for i in range(6)]
    assert _total_duration(project) == pytest.approx(30.0)


def test_total_duration_excludes_pending():
    project = FilmProject(logline="test")
    project.shots = [
        _accepted_shot(0, 6.0),
        _pending_shot(1, 5.0),
        _accepted_shot(2, 7.0),
    ]
    assert _total_duration(project) == pytest.approx(13.0)


def test_total_duration_empty():
    project = FilmProject(logline="test")
    assert _total_duration(project) == pytest.approx(0.0)


def test_total_duration_mixed_lengths():
    project = FilmProject(logline="test")
    durations = [5.0, 6.5, 8.0, 5.5, 7.0, 6.0]
    project.shots = [_accepted_shot(i, d) for i, d in enumerate(durations)]
    assert _total_duration(project) == pytest.approx(sum(durations))
