import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

import ml.research_training as training
from app.main import app
from ml.manifest_audit import text_hash


@pytest.fixture
def records():
    return training.fictional_records()


@pytest.fixture
def output(tmp_path):
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("model", training.MODELS)
def test_model_types_determinism_and_train_only_vocabulary(records, model):
    train = [r for r in records if r["split"] == "train"]
    validation = next(r for r in records if r["split"] == "validation")
    validation["text"] += " qzxheldoutuniqueword"
    validation["text_hash"] = text_hash(validation["text"])
    training.validate_training_data(records, "synthetic")
    first, second = training.make_pipeline(model, 42), training.make_pipeline(model, 42)
    for pipeline in (first, second):
        pipeline.fit([r["text"] for r in train], [r["label"] for r in train])
        assert "qzxheldoutuniqueword" not in pipeline.named_steps["tfidf"].vocabulary_
    np.testing.assert_allclose(first.decision_function([validation["text"]]), second.decision_function([validation["text"]]))


def test_smoke_comparison_selection_and_test_claim(records, output, monkeypatch):
    calls = []
    original = training._outputs
    def spy(model, rows, split):
        calls.append(split)
        return original(model, rows, split)
    monkeypatch.setattr(training, "_outputs", spy)
    result = training.run_comparison(records, output, evidence="synthetic")
    assert calls == ["validation", "validation", "test"]
    assert result["warning"] == training.SYNTHETIC_WARNING
    assert set(result["validation"]) == set(training.MODELS)
    assert len(result["test"]["runs"]) == 1
    assert result["test"]["runs"][0]["threshold"] == result["selected_threshold"]
    assert len(list(output.glob("model-*.pkl"))) == 1
    assert len(list(output.glob("report-*.json"))) == 1
    report_file = next(output.glob("report-*.json"))
    assert json.loads(report_file.read_text(encoding="utf-8"))["warning"] == training.SYNTHETIC_WARNING
    with pytest.raises(FileExistsError):
        training.run_comparison(records, output, evidence="synthetic", seed=99)
    assert calls == ["validation", "validation", "test"]


def test_reproducibility_across_separate_directories(records, tmp_path):
    paths = [tmp_path / "first", tmp_path / "second"]
    for path in paths:
        path.mkdir()
        (path / ".gitignore").write_text("*\n", encoding="utf-8")
    a = training.run_comparison(records, paths[0], evidence="synthetic")
    b = training.run_comparison(deepcopy(records), paths[1], evidence="synthetic")
    assert a == b


@pytest.mark.parametrize("field,value", [("consent_status", "withdrawn"), ("rights_review", "pending"),
                                       ("privacy_review", "pending"), ("provenance_group", ""),
                                       ("label_verification", "unverified")])
def test_reject_unresolved_provenance_or_permissions(records, field, value):
    records[0][field] = value
    with pytest.raises(ValueError):
        training.validate_training_data(records, "synthetic")


def test_real_mode_requires_rights_and_verified_labels(records):
    for row in records:
        row.update(source_status="consented-local", consent_status="documented", label_verification="verified")
    with pytest.raises(ValueError, match="Rights"):
        training.validate_training_data(records, "unvalidated_research")
    for row in records:
        row["license_status"] = "approved"
    records[0]["label_verification"] = "unverified"
    with pytest.raises(ValueError, match="verification"):
        training.validate_training_data(records, "unvalidated_research")


def test_group_leakage_and_insufficient_independent_training_groups(records):
    records[-1]["related_groups"].append(records[0]["provenance_group"])
    with pytest.raises(ValueError, match="provenance"):
        training.validate_training_data(records, "synthetic")
    records = training.fictional_records()
    human = [r for r in records if r["split"] == "train" and r["label"] == "human"]
    for row in human[1:]:
        row["provenance_group"] = human[0]["provenance_group"]
    with pytest.raises(ValueError, match="two independent"):
        training.validate_training_data(records, "synthetic")


def test_shared_consent_reference_cannot_cross_split(records):
    records[-1]["consent_ref"] = records[0]["consent_ref"]
    with pytest.raises(ValueError, match="consent references"):
        training.validate_training_data(records, "synthetic")


def test_mixed_unknown_not_trained(records, output):
    row = deepcopy(records[0])
    row.update(record_id="r-fffffff0", original_record_id="r-fffffff0", provenance_group="g-fffffff0",
               consent_ref="c-fffffff0", label="unknown", label_verification="unverified", collection_method="unknown-origin",
               text="Invented navigation coursework for a lunar sailing crew.")
    row["text_hash"] = text_hash(row["text"])
    records.append(row)
    parent = records[0]
    mixed = deepcopy(parent)
    mixed.update(record_id="r-fffffff1", original_record_id="r-fffffff1", provenance_group="g-fffffff1",
                 related_groups=[parent["provenance_group"], "g-fffffff2"], label="mixed", label_verification="unverified",
                 collection_method="ai-assisted", prompt_family="g-fffffff2", model_id="fictional-model",
                 model_version="fictional-v1", generation_settings_ref="fictional-settings", human_editing_history=["fictional-edit"],
                 parent_record_id=parent["record_id"], transformations=["fictional-edit"],
                 text="A fictional astronomical workshop documented telescope maintenance.")
    mixed["text_hash"] = text_hash(mixed["text"])
    records.append(mixed)
    result = training.run_comparison(records, output, evidence="synthetic")
    assert result["training_label_counts"] == {"ai": 4, "human": 4}
    assert result["excluded_training_label_counts"] == {"mixed": 1, "unknown": 1}


def test_unsafe_output_and_existing_model(records, output):
    with pytest.raises(ValueError):
        training.run_comparison(records, Path(__file__).parents[1], evidence="synthetic")
    model = output / f"model-{training.fingerprint(records)}.pkl"
    model.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        training.run_comparison(records, output, evidence="synthetic")
    assert model.read_bytes() == b"existing"


def test_no_routes_registered_for_training():
    assert all("research_training" not in getattr(route, "path", "") for route in app.routes)
