import json
from pathlib import Path

import pytest

from app.analysis import analyze_text, sections_from_text

PROFILES = json.loads((Path(__file__).parent / "fixtures" / "synthetic_cvs.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("profile", PROFILES, ids=lambda profile: profile["profile"])
def test_synthetic_profiles(profile):
    text = profile["text"]
    result = analyze_text(text)
    assert result == analyze_text(text)
    assert set(sections_from_text(text)) == set(profile["sections"])
    scores = result["categories"]
    assert all(0 <= value["score"] <= 100 for value in scores.values())
    assert result["overall_score"] == round(sum(scores[key]["score"] * weight for key, weight in [("structure", .3), ("experience", .3), ("skills", .2), ("readability", .2)]))
    assert 0 <= result["overall_score"] <= 100
    assert not result["recommendations"] or result["weaknesses"]
    if profile["profile"] == "sparse":
        assert result["recommendations"] and result["categories"]["experience"]["score"] == 0
    else:
        assert result["categories"]["experience"]["score"] == 100


def test_projects_and_work_are_equivalent():
    content = "\n- Built a tool for community library volunteers"
    projects = analyze_text("Projects" + content)["categories"]
    work = analyze_text("Experience" + content)["categories"]
    assert all(projects[key]["score"] == work[key]["score"] for key in projects)
