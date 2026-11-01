import pytest

from app.analysis import analyze_text
from app.writing_insights import MAX_INSIGHTS, writing_insights
from test_extract import client, docx, pdf


def ids(text):
    return [insight["id"] for insight in writing_insights(text)]


@pytest.mark.parametrize("text,expected", [
    ("Summary\nHardworking team player.", "generic_team_player"),
    ("Experience\n- Responsible for various tasks", "generic_various_tasks"),
    ("Summary: Excellent communication skills", "generic_excellent_communication"),
    ("Summary\nWorks well under pressure", "generic_work_well_under_pressure"),
    ("Summary\nＨＡＲＤＷＯＲＫＩＮＧ　ＴＥＡＭ　ＰＬＡＹＥＲ。", "generic_team_player"),
])
def test_generic_phrases(text, expected):
    assert expected in ids(text)


@pytest.mark.parametrize("text", [
    "Projects\n- Responsible for tasks",
    "Experience\n• Helped with various tasks.",
    "Experience\n1. Worked on various projects",
])
def test_vague_bullets(text):
    insight = next(x for x in writing_insights(text) if x["id"] == "vague_contribution")
    assert insight["type"] == "vague_description"
    assert "numbers are optional" in insight["recommendation"]


def test_repeated_openings_are_section_specific_and_meaningful():
    text = "Projects\n- Worked with students on a map\n- Worked with volunteers on a catalogue\n- Worked with tutors on a survey"
    assert "repeated_opening_projects" in ids(text)
    assert "repeated_opening_experience" not in ids(text)
    assert not ids("Projects\n- Worked with students on a map\n- Worked with volunteers on a catalogue")
    assert not ids("Projects\n- Worked with students on a map\n- Worked with students on a map\n- Worked with students on a map")
    assert not ids("Projects\n- Worked with students on a map\nExperience\n- Worked with volunteers on a catalogue\n- Worked with tutors on a survey")


@pytest.mark.parametrize("text", [
    "", "\n\t", "Projects\n- Built a CLI\n- Tested SQL\n- Fixed API routes",
    "Projects\n- Built a timetable viewer for a student project\n- Tested Python code",
    "Summary\nHardworking team player who coordinated the library rota.",
    "Experience\n- Responsible for various tasks including inventory reconciliation",
    "Experience\n- Responsible for tasks\n  including repairing equipment",
    "Experience\n- Worked on various projects using Python",
    "Skills\nHardworking team player\nProjects\n-Responsible for tasks",
    "Experience\nAwards\n- Responsible for tasks",
    "Experience\n- Excellent communication skills: clarified safety procedures",
    "Projects\n- Café résumé工具\n- 使用 Python 处理数据",
])
def test_conservative_no_feedback(text):
    assert writing_insights(text) == []


def test_unicode_bullets_and_wrapped_lines():
    text = "PROJECTS\n• Worked with students\n  on a map\n◦ Worked with volunteers on a catalogue\n▪ Worked with tutors on a survey"
    assert ids(text) == ["repeated_opening_projects"]


def test_no_echo_contact_names_or_full_bullets():
    text = "Summary\nHardworking team player\nName: Example Person\nEmail: sample@example.com\nProjects\n- Responsible for tasks\n- Worked with Example Person\n- Worked with volunteers\n- Worked with students"
    result = writing_insights(text)
    assert len(result) == 3
    output = str(result)
    assert "Example Person" not in output and "sample@example.com" not in output
    assert "Hardworking team player" not in output and "Worked with" not in output
    assert all(set(item) == {"id", "type", "priority", "explanation", "recommendation"} for item in result)


def test_limit_stable_ids_and_order():
    text = "Summary\nHardworking team player\nResponsible for various tasks\nWorks well under pressure\nExcellent communication skills\nProjects\n- Responsible for tasks\n- Worked with students\n- Worked with volunteers\n- Worked with tutors"
    result = writing_insights(text)
    assert result == writing_insights(text)
    assert len(result) == MAX_INSIGHTS
    assert len({item["id"] for item in result}) == len(result)
    assert [item["id"] for item in result][-1] == "vague_contribution"


@pytest.mark.parametrize("name,make_document", [("cv.pdf", pdf), ("cv.docx", docx)])
def test_analysis_endpoint_adds_insights_without_changing_score(name, make_document):
    text = "Summary\nHardworking team player\nProjects\n- Responsible for tasks"
    response = client.post("/api/cv/analyze", files={"file": (name, make_document(text))})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert {item["id"] for item in result["writing_insights"]} == {"generic_team_player", "vague_contribution"}
    assert {k: v for k, v in result.items() if k != "writing_insights"} == analyze_text(text + ("\n\nSecond paragraph" if name.endswith("docx") else ""))
    assert "extracted_text" not in result


def test_analysis_endpoint_empty_insights():
    response = client.post("/api/cv/analyze", files={"file": ("cv.docx", docx("Projects\n- Built a CLI"))})
    assert response.status_code == 200
    assert response.json()["writing_insights"] == []
