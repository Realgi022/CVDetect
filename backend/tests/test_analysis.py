import pytest

from app.analysis import analyze_text, sections_from_text
from test_extract import client, docx, pdf, MAX_FILE_SIZE


def test_heading_variations_and_student_projects():
    text = "Academic Background\nDegree coursework\nAcademic Projects\n- Built a useful website for local volunteers\nTechnical Skills: Python, HTML\nCareer Objective\nLearn and contribute"
    sections = sections_from_text(text)
    assert set(sections) == {"education", "projects", "skills", "summary"}
    result = analyze_text(text)
    assert result["categories"]["structure"]["score"] == 100
    assert result["categories"]["experience"]["score"] == 100


def test_missing_sections_and_empty_text():
    report = analyze_text("Unrecognized content")
    assert report["overall_score"] == 0
    assert report["weaknesses"]
    assert analyze_text("")["overall_score"] == 0


def test_bullets_metrics_do_not_change_score():
    base = "Projects\n- Built a website for local community volunteers"
    measured = base + " serving 20 users"
    a, b = analyze_text(base), analyze_text(measured)
    assert a["categories"]["experience"]["score"] == b["categories"]["experience"]["score"] == 100
    assert "1 include a recognizable numerical outcome" in b["categories"]["experience"]["explanation"]
    assert analyze_text("Experience\n- Responsible for tasks")["categories"]["experience"]["score"] == 20


def test_readability_and_contact_exclusion():
    text = "Skills\nPython, SQL\n" + "word " * 41
    report = analyze_text(text)
    assert report["categories"]["readability"]["score"] == 50
    assert analyze_text("Skills\nPython, SQL\nme@example.com")["categories"] == analyze_text("Skills\nPython, SQL")["categories"]


@pytest.mark.parametrize("text", ["", "Skills\nPython", "Education\nStudy\nProjects\n- Built a tool for community library volunteers\nSkills\nPython, SQL\nSummary\nStudent"])
def test_score_boundaries_and_weighting(text):
    result = analyze_text(text)
    scores = result["categories"]
    assert all(0 <= item["score"] <= 100 for item in scores.values())
    assert 0 <= result["overall_score"] <= 100
    assert result["overall_score"] == round(scores["structure"]["score"] * .3 + scores["experience"]["score"] * .3 + scores["skills"]["score"] * .2 + scores["readability"]["score"] * .2)


@pytest.mark.parametrize("name,data", [("cv.pdf", pdf()), ("cv.docx", docx())])
def test_analysis_api(name, data):
    response = client.post("/api/cv/analyze", files={"file": (name, data)})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()["categories"]) == {"structure", "experience", "skills", "readability"}
    assert "extracted_text" not in response.json()


@pytest.mark.parametrize("name,data", [("cv.txt", b"text"), ("cv.pdf", b""), ("cv.pdf", b"corrupt"), ("cv.docx", b"corrupt"), ("cv.pdf", pdf(text="")), ("cv.pdf", b"x" * (MAX_FILE_SIZE + 1))])
def test_invalid_uploads_match_extraction(name, data):
    files = {"file": (name, data)}
    extraction = client.post("/api/cv/extract", files=files)
    analysis = client.post("/api/cv/analyze", files=files)
    assert analysis.status_code == extraction.status_code
    assert analysis.json() == extraction.json()


def test_invalid_multipart():
    assert client.post("/api/cv/analyze", json={}).status_code == 400
