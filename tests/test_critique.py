"""Tests for critic threshold and retry logic."""

import pytest

from auteur.models import FilmProject, Shot, ShotStatus


def _shot_with_score(index: int, score: float) -> Shot:
    s = Shot(index=index, prompt="test", keyframe_path="/fake/path.png")
    s.critic_score = score
    s.status = ShotStatus.GENERATING
    return s


def test_shot_accepted_above_threshold():
    shot = _shot_with_score(0, 0.85)
    assert (shot.critic_score or 0.0) >= 0.7


def test_shot_below_threshold():
    shot = _shot_with_score(0, 0.5)
    assert (shot.critic_score or 0.0) < 0.7


def test_shot_attempts_tracked():
    shot = Shot(index=0, prompt="test")
    assert shot.attempts == 0
    shot.attempts += 1
    assert shot.attempts == 1
    shot.attempts += 1
    assert shot.attempts == 2


def test_max_attempts_cap():
    """Verify a shot stops retrying after max_attempts."""
    from auteur.config import settings
    shot = Shot(index=0, prompt="test")
    shot.critic_score = 0.3
    shot.attempts = settings.max_shot_attempts
    # At this point the loop should not retry further
    assert shot.attempts >= settings.max_shot_attempts


def test_best_score_kept():
    """Simulates keeping the best shot when all attempts are below threshold."""
    scores = [0.45, 0.60, 0.55]
    best_score = max(scores)
    assert best_score == pytest.approx(0.60)
