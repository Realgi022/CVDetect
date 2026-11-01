import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from ml.cv_collection import prepare, validate_metadata, validate_output_dir
from ml.manifest_audit import audit_manifest

FIXTURES = Path(__file__).parents[1] / "ml" / "fixtures" / "cv_collection"


@pytest.fixture
def rows():
    return json.loads((FIXTURES / "metadata.json").read_text(encoding="utf-8"))


def test_fictional_metadata_and_deterministic_grouping(rows):
    validate_metadata(rows)
    first = prepare(rows, FIXTURES)
    second = prepare(deepcopy(rows), FIXTURES)
    assert first == second
    assert "SYNTHETIC SOFTWARE TEST ONLY" in first["warning"]
    records = {r["record_id"]: r for r in first["records"]}
    assert records["r-00000001"]["split"] == records["r-00000003"]["split"]
    assert {r["label"] for r in records.values()} == {"human", "ai", "mixed", "unknown"}
    assert records["r-00000003"]["parent_record_id"] == "r-00000001"
    assert all(r["license_status"] == "unverified" for r in records.values())
    assert records["r-00000002"]["prompt_family"] in records["r-00000002"]["related_groups"]


@pytest.mark.parametrize("field,value", [
    ("consent_status", "withdrawn"), ("consent_status", None), ("consent_ref", ""),
    ("rights_review", "pending"), ("privacy_review", "rejected"), ("source_status", "web-scraped"),
    ("provenance_group", ""), ("language", ""), ("document_type", "pdf"),
    ("collection_method", "ai-generated"), ("label", "uncertain"),
])
def test_invalid_metadata(rows, field, value):
    rows[0][field] = value
    with pytest.raises(ValueError):
        validate_metadata(rows)


def test_missing_unsupported_and_duplicate_metadata(rows):
    del rows[0]["consent_status"]
    with pytest.raises(ValueError):
        validate_metadata(rows)
    rows = json.loads((FIXTURES / "metadata.json").read_text(encoding="utf-8"))
    rows[1]["record_id"] = rows[0]["record_id"]
    with pytest.raises(ValueError, match="duplicate"):
        validate_metadata(rows)
    rows[1]["record_id"] = "r-00000002"
    rows[1]["email"] = "person@example.test"
    with pytest.raises(ValueError, match="unsupported"):
        validate_metadata(rows)


def test_real_requires_documented_consent_before_read(rows, tmp_path):
    rows[0]["source_status"] = "consented-local"
    with pytest.raises(ValueError, match="consent"):
        prepare(rows, tmp_path)
    rows[0]["consent_status"] = "documented"
    rows[2]["source_status"] = "consented-local"
    rows[2]["consent_status"] = "documented"
    with pytest.raises(ValueError, match="outside"):
        prepare(rows, FIXTURES)


def test_generation_and_parent_requirements(rows):
    rows[1]["prompt_family"] = None
    with pytest.raises(ValueError, match="generation"):
        validate_metadata(rows)
    rows[1]["prompt_family"] = "g-00000102"
    rows[2]["parent_record_id"] = "r-ffffffff"
    with pytest.raises(ValueError, match="human parent"):
        validate_metadata(rows)
    rows[2]["parent_record_id"] = rows[0]["record_id"]
    rows[2]["consent_ref"] = "c-ffffffff"
    with pytest.raises(ValueError, match="human parent"):
        validate_metadata(rows)


def test_cross_split_parent_leakage_detected(rows):
    records = prepare(rows, FIXTURES)["records"]
    records[2]["split"] = next(x for x in ("train", "test", "validation") if x != records[0]["split"])
    with pytest.raises(ValueError, match="provenance|duplicate"):
        audit_manifest(records)


def test_exact_duplicate_is_rejected(rows, tmp_path):
    for row in rows:
        text = (FIXTURES / f"{row['record_id']}.txt").read_text(encoding="utf-8")
        (tmp_path / f"{row['record_id']}.txt").write_text(text, encoding="utf-8")
    (tmp_path / "r-00000005.txt").write_text((tmp_path / "r-00000001.txt").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        prepare(rows, tmp_path)


def test_near_duplicate_is_reported_and_grouped(rows, tmp_path):
    for row in rows:
        text = (FIXTURES / f"{row['record_id']}.txt").read_text(encoding="utf-8")
        (tmp_path / f"{row['record_id']}.txt").write_text(text, encoding="utf-8")
    original = (tmp_path / "r-00000001.txt").read_text(encoding="utf-8")
    (tmp_path / "r-00000005.txt").write_text(original + "More.\n", encoding="utf-8")
    result = prepare(rows, tmp_path)
    assert {"left_index": 0, "right_index": 4} in result["near_duplicate_pairs"]
    assert result["records"][0]["split"] == result["records"][4]["split"]


def test_unsafe_output_paths(tmp_path):
    with pytest.raises(ValueError):
        validate_output_dir("relative")
    with pytest.raises(ValueError):
        validate_output_dir(FIXTURES)
    with pytest.raises(ValueError):
        validate_output_dir(tmp_path)
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")
    assert validate_output_dir(tmp_path) == tmp_path.resolve()
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError):
        validate_output_dir(tmp_path)


def test_cli_writes_only_explicit_external_output_and_never_overwrites(rows, tmp_path):
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")
    command = [sys.executable, "-m", "ml.cv_collection", "--metadata", str(FIXTURES / "metadata.json"),
               "--input-dir", str(FIXTURES), "--output-dir", str(tmp_path)]
    result = subprocess.run(command, cwd=FIXTURES.parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "observatory" not in result.stdout
    data = json.loads((tmp_path / "prepared.json").read_text(encoding="utf-8"))
    assert len(data["records"]) == 5
    again = subprocess.run(command, cwd=FIXTURES.parents[2], capture_output=True, text=True)
    assert again.returncode != 0 and "observatory" not in again.stderr
    assert json.loads((tmp_path / "prepared.json").read_text(encoding="utf-8")) == data


def test_error_messages_do_not_echo_metadata(rows, tmp_path):
    rows[0]["label"] = "private-person@example.test"
    with pytest.raises(ValueError) as error:
        validate_metadata(rows)
    assert "private-person" not in str(error.value)
