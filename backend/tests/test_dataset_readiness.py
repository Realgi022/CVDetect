import json
from copy import deepcopy
from pathlib import Path

import pytest

from ml.cv_collection import prepare
from ml.dataset_readiness import readiness
from ml.manifest_audit import text_hash
from ml.research_training import fictional_records


@pytest.fixture
def records():
    return fictional_records()


def test_fictional_inventory_is_not_approval(records):
    result = readiness(records)
    assert result["manifest_valid"] and result["collection_metadata_valid"]
    assert result["pipeline_minimum_checks_passed"]
    assert result["eligible_binary_attested_counts"] == {"human": 0, "ai": 0}
    assert result["class_counts"] == {"human": 8, "ai": 8, "mixed": 0, "unknown": 0}
    assert result["external_cv_holdout"] == "not_established"
    assert result["public_release"] == "blocked" and "SYNTHETIC SOFTWARE TEST ONLY" in result["warning"]
    assert records[0]["text"] not in json.dumps(result)


@pytest.mark.parametrize("field,value", [("consent_status", "withdrawn"), ("consent_status", None),
                                       ("rights_review", "pending"), ("privacy_review", "pending"),
                                       ("provenance_group", ""), ("split", "test-only")])
def test_missing_or_invalid_review_blocks(records, field, value):
    records[0][field] = value
    result = readiness(records)
    assert result["training"] == "blocked_pending_independent_review"
    assert not result["pipeline_minimum_checks_passed"]
    assert result["public_release"] == "blocked"
    assert result["blockers"]


def test_conflicting_provenance_and_leakage(records):
    records[-1]["related_groups"].append(records[0]["provenance_group"])
    result = readiness(records)
    assert not result["known_split_checks_passed"]
    assert result["external_cv_holdout"] == "not_established"
    assert result["blockers"]


def test_cross_split_duplicate_report(records):
    records[-1]["text"] = records[0]["text"]
    records[-1]["text_hash"] = text_hash(records[0]["text"])
    records[-1]["label"] = records[0]["label"]
    result = readiness(records)
    assert result["duplicates"]["cross_split_pairs"] >= 1
    assert not result["pipeline_minimum_checks_passed"]


def test_invalid_manifest_has_no_eligible_examples(records):
    for row in records:
        row.update(source_status="consented-local", consent_status="documented", license_status="approved", label_verification="verified")
    records[0]["provenance_group"] = ""
    result = readiness(records, evidence="unvalidated_research")
    assert result["eligible_binary_attested_counts"] == {"human": 0, "ai": 0}


def test_missing_metadata_and_empty(records):
    del records[0]["consent_ref"]
    result = readiness(records)
    assert not result["collection_metadata_valid"] and result["independent_provenance_components"] is None
    empty = readiness([])
    assert empty["record_count"] == 0 and empty["public_release"] == "blocked"


def test_insufficient_groups(records):
    humans = [r for r in records if r["split"] == "train" and r["label"] == "human"]
    for row in humans:
        row["provenance_group"] = humans[0]["provenance_group"]
    assert not readiness(records)["pipeline_minimum_checks_passed"]


def test_mixed_and_unknown_preserved():
    fixture = Path(__file__).parents[1] / "ml" / "fixtures" / "cv_collection"
    rows = json.loads((fixture / "metadata.json").read_text(encoding="utf-8"))
    report = readiness(prepare(rows, fixture)["records"])
    assert report["class_counts"]["mixed"] == report["class_counts"]["unknown"] == 1
    assert not report["pipeline_minimum_checks_passed"]


def test_attestations_are_not_approval(records):
    for row in records:
        row.update(source_status="consented-local", consent_status="documented", license_status="approved", label_verification="verified")
    study = {"independence": {"author_links_reviewed": True, "profile_links_reviewed": True,
                              "prompt_links_reviewed": True, "split_registry_reviewed": True},
             "external_holdout": {"record_ids": [r["record_id"] for r in records if r["split"] == "test"],
                                  "external_collection": True, "cv_specific": True, "unseen_authors": True,
                                  "sealed": True, "independent_review": True},
             "subgroup_evaluation": {"consent_and_privacy_approved": True, "prespecified_groups": True,
                                     "adequate_independent_samples_reviewed": True},
             "model_families": {"fictional-model": "fictional-family"}}
    result = readiness(records, evidence="unvalidated_research", study=study)
    assert result["external_cv_holdout"] == "attested_not_verified"
    assert result["training"] == "blocked_pending_independent_review" and result["public_release"] == "blocked"
    assert result["ai_model_families_attested"] == 1
    fake = deepcopy(study)
    fake["external_holdout"]["record_ids"] = [records[0]["record_id"]]
    assert readiness(records, evidence="unvalidated_research", study=fake)["external_cv_holdout"] == "not_established"
