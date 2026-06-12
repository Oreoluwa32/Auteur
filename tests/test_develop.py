"""Tests for the develop stage: shot-list parsing and schema validation."""

import json

import pytest

from auteur.pipeline.develop import _parse_shot_list
from auteur.models import Shot


_VALID_PLAN = {
    "treatment": "A lone astronaut finds life on Mars.",
    "style": "Cinematic sci-fi, desaturated",
    "palette": ["#c0392b", "#27ae60"],
    "narrator_script": "On a silent red world, one woman changed everything.",
    "shots": [
        {
            "index": i,
            "prompt": f"Shot {i} visual description",
            "duration": 6.0,
            "camera_note": "Wide",
            "characters": [],
            "continuity_note": "",
        }
        for i in range(6)
    ],
}


def test_parse_plain_json():
    raw = json.dumps(_VALID_PLAN)
    data = _parse_shot_list(raw)
    assert data["treatment"] == _VALID_PLAN["treatment"]
    assert len(data["shots"]) == 6


def test_parse_markdown_fenced_json():
    raw = f"```json\n{json.dumps(_VALID_PLAN)}\n```"
    data = _parse_shot_list(raw)
    assert len(data["shots"]) == 6


def test_parse_fenced_no_language_tag():
    raw = f"```\n{json.dumps(_VALID_PLAN)}\n```"
    data = _parse_shot_list(raw)
    assert data["style"] == _VALID_PLAN["style"]


def test_shots_deserialise_to_model():
    raw = json.dumps(_VALID_PLAN)
    data = _parse_shot_list(raw)
    shots = [Shot(**s) for s in data["shots"]]
    assert len(shots) == 6
    assert all(s.duration == 6.0 for s in shots)


def test_parse_invalid_json_raises():
    with pytest.raises(json.JSONDecodeError):
        _parse_shot_list("not valid json {{{")
