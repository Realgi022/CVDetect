import json
from copy import deepcopy
from pathlib import Path

import pytest

from ml.manifest_audit import audit_manifest, duplicate_report, plan_splits, text_hash, validate_manifest


@pytest.fixture
def records():
    path = Path(__file__).parents[1] / "ml" / "fixtures" / "fictional_manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_normalization_and_hash():
    assert text_hash("ＦＯＯ, bar!") == text_hash("foo BAR")
    assert text_hash("foo bar") != text_hash("foo baz")


def test_example_and_all_labels(records):
    stats = audit_manifest(records)
    assert stats["labels"] == {"ai": 1, "human": 1, "mixed": 1, "unknown": 1}
    assert stats["records"] == stats["components"] == 4
    assert stats["duplicates"] == []


@pytest.mark.parametrize("field,value", [
    ("dataset_id", ""), ("original_record_id", None), ("provenance_group", "  "),
    ("source_domain", ""), ("source_url", "http://example.org"), ("source_url", "https://u:p@example.org"),
    ("license_status", "yes"), ("label", "machine"), ("model_id", ""),
    ("related_groups", [""]), ("transformations", "edited"), ("split", "dev"), ("text_hash", "0" * 64),
])
def test_invalid_metadata(records, field, value):
    records[0][field] = value
    with pytest.raises(ValueError):
        validate_manifest(records)


def test_missing_and_duplicate_ids(records):
    del records[0]["model_id"]
    with pytest.raises(ValueError, match="model_id"):
        validate_manifest(records)
    records[0]["model_id"] = None
    records[1]["original_record_id"] = records[0]["original_record_id"].upper()
    with pytest.raises(ValueError, match="duplicate dataset"):
        validate_manifest(records)


def test_conflicting_exact_labels_fail(records):
    records[1]["text"] = records[0]["text"].upper()
    records[1]["text_hash"] = text_hash(records[1]["text"])
    with pytest.raises(ValueError, match="inconsistent labels"):
        audit_manifest(records)


def test_exact_and_near_duplicates_and_cross_split(records):
    records[1]["label"] = records[0]["label"]
    records[1]["text"] = records[0]["text"].upper()
    records[1]["text_hash"] = text_hash(records[1]["text"])
    assert duplicate_report(records)[0]["kind"] == "exact"
    for row, split in zip(records, ["train", "test", "validation", "train"]):
        row["split"] = split
    assert duplicate_report(records)[0]["cross_split"]
    with pytest.raises(ValueError, match="cross-split"):
        audit_manifest(records)
    records[1]["text"] = records[0]["text"] + " Additional details."
    records[1]["text_hash"] = text_hash(records[1]["text"])
    assert duplicate_report(records)[0]["kind"] == "near"
    with pytest.raises(ValueError, match="cross-split"):
        audit_manifest(records)


def test_transitive_grouping_and_reproducibility(records):
    extra = deepcopy(records[0])
    extra.update(original_record_id="demo-5", provenance_group="another-family", related_groups=["shared-author"])
    extra["text"] = "Invented museum hosted a ceramics workshop."
    extra["text_hash"] = text_hash(extra["text"])
    records[0]["related_groups"] = ["shared-author"]
    records.append(extra)
    planned = plan_splits(records)
    assert records[0]["split"] is None
    assert planned[0]["split"] == planned[-1]["split"]
    reversed_plan = plan_splits(list(reversed(records)))
    assert {r["original_record_id"]: r["split"] for r in planned} == {r["original_record_id"]: r["split"] for r in reversed_plan}
    assert {r["split"] for r in planned} == {"train", "validation", "test"}
    planned[-1]["split"] = next(s for s in ("train", "test", "validation") if s != planned[0]["split"])
    with pytest.raises(ValueError, match="provenance"):
        audit_manifest(planned)


def test_unsafe_plans(records):
    records[0]["split"] = "train"
    with pytest.raises(ValueError, match="every record"):
        plan_splits(records)
    for row in records:
        row["split"] = None
        row["provenance_group"] = "same-family"
    with pytest.raises(ValueError, match="three independent"):
        plan_splits(records)


def test_duplicate_components_stay_together(records):
    records[1]["label"] = records[0]["label"]
    records[1]["text"] = records[0]["text"]
    records[1]["text_hash"] = records[0]["text_hash"]
    planned = plan_splits(records)
    assert planned[0]["split"] == planned[1]["split"]
    assert audit_manifest(planned)["duplicates"][0]["kind"] == "exact"
