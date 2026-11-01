import pytest

from app.analysis import analyze_text
from app.writing_patterns import writing_patterns
from test_extract import client, docx, pdf


def test_known_bullets_and_denominators():
    text = "Projects\n- Built a map for 20 users.\n- Built a guide for 5 users.\n- Tested a tool with local volunteers.\nSummary\nHardworking team player."
    result = writing_patterns(text)
    assert result["coverage"] == {"total_characters": len(text), "analyzed_characters": len(text), "truncated": False, "nonempty_lines": 6, "included_lines": 4, "units": 4, "words": 21, "minimum_words": 20, "minimum_units": 3}
    assert result["status"] == "sufficient"
    assert [x["count"] for x in result["sentence_length"]["distribution"]] == [1, 3, 0, 0]
    assert result["sentence_length"]["mean_words"] == 5.25
    assert result["repetition"]["repeated_opening_groups"] == 1
    assert result["repetition"]["units_with_repeated_opening"] == 2
    assert result["specificity"] == {"units_with_number": 2, "units_with_measurable_pattern": 2, "units_starting_action_verb": 3}
    assert result["generic_phrases"]["matched"] == [{"phrase": "hardworking team player", "unit_count": 1}]


@pytest.mark.parametrize("text", ["", "  \n", "!?!", "Skills\nPython"])
def test_empty_and_short_text(text):
    result = writing_patterns(text)
    assert result["status"] == "insufficient"
    assert result["coverage"]["words"] < 20
    if result["coverage"]["units"] < 2:
        assert result["sentence_length"]["population_stddev_words"] is None


def test_punctuation_and_sentence_fragments():
    result = writing_patterns("Summary: Built a tool. Tested it! Worked with 3.5 users?\n- Designed an interface")
    assert result["coverage"]["units"] == 4
    assert result["specificity"]["units_with_measurable_pattern"] == 1
    assert sum(b["count"] for b in result["sentence_length"]["distribution"]) == 4


def test_repeated_phrases_require_distinct_units():
    once = writing_patterns("Projects\n- Built a tool built a tool")
    assert once["repetition"]["repeated_two_word_phrases"] == 0
    repeated = writing_patterns("Projects\n- Built a tool\n- Built a map")
    assert repeated["repetition"]["repeated_two_word_phrases"] >= 1
    assert repeated["repetition"]["units_with_repeated_opening"] == 2


def test_contact_lines_excluded_and_no_arbitrary_snippets():
    text = "Name: Fictional Person\nEmail: person@example.test\nProjects\n- Built a secret uniquefictionalmarker project\n- Built a secret uniquefictionalmarker exhibit"
    result = writing_patterns(text)
    assert result["coverage"]["nonempty_lines"] == 5
    assert result["coverage"]["included_lines"] == 2
    assert "uniquefictionalmarker" not in str(result) and "person@example" not in str(result)


def test_different_inputs_change_actual_measurements():
    first = writing_patterns("Projects\n- Built a tool for 20 users\n- Built a map for 10 users")
    second = writing_patterns("Projects\n- Designed an interface\n- Tested a guide")
    assert first["specificity"] != second["specificity"]
    assert first["repetition"] != second["repetition"]


def test_large_text_is_bounded_and_reports_coverage():
    text = "word " * 25000
    result = writing_patterns(text)
    assert result["coverage"]["total_characters"] == len(text)
    assert result["coverage"]["analyzed_characters"] == 100000
    assert result["coverage"]["truncated"] is True


@pytest.mark.parametrize("name,make_document", [("fictional.pdf", pdf), ("fictional.docx", docx)])
def test_api_additive_without_quality_changes(name, make_document):
    text = "Projects\n- Built a tool for 20 users"
    data = make_document(text)
    extracted = client.post("/api/cv/extract", files={"file": (name, data)}).json()["extracted_text"]
    response = client.post("/api/cv/analyze", files={"file": (name, data)})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["writing_patterns"] == writing_patterns(extracted)
    assert {k: v for k, v in result.items() if k not in ("writing_insights", "writing_patterns")} == analyze_text(extracted)
    assert "extracted_text" not in result


def test_public_api_never_registers_research_routes():
    for path in ("/research/vite-analyze", "/research/artifact-analyze", "/api/experimental/writing-diagnostic"):
        assert client.post(path, json={"text": "fictional"}).status_code == 404


def test_two_uploaded_documents_produce_different_patterns():
    first = docx("Projects\n- Built a map for 20 users\n- Built a guide for 5 users")
    second = docx("Skills\n- Designed an interface\n- Tested a catalog")
    a = client.post("/api/cv/analyze", files={"file": ("fictional-a.docx", first)}).json()["writing_patterns"]
    b = client.post("/api/cv/analyze", files={"file": ("fictional-b.docx", second)}).json()["writing_patterns"]
    assert a["specificity"]["units_with_measurable_pattern"] == 2
    assert b["specificity"]["units_with_measurable_pattern"] == 0
    assert a["repetition"]["repeated_opening_groups"] > b["repetition"]["repeated_opening_groups"]
