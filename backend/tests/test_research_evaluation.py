from copy import deepcopy

import pytest

from ml.manifest_audit import text_hash
from ml.research_evaluation import (
    SYNTHETIC_WARNING, as_json, as_markdown, evaluate_experiment,
    fictional_fixture, metrics, threshold_predictions,
)


@pytest.fixture
def inputs():
    records, outputs = fictional_fixture()
    return records, [o for r, o in zip(records, outputs) if r["split"] == "validation"]


def report(inputs, **changes):
    records, outputs = inputs
    options = dict(split="validation", thresholds=[0, 0.2], model_id="fictional", seed=42, evidence_status="synthetic")
    options.update(changes)
    return evaluate_experiment(records, outputs, **options)


def test_metrics_with_abstention_and_nonbinary():
    truth = ["human", "human", "human", "ai", "ai", "ai", "mixed", "unknown"]
    predicted = ["human", "ai", "inconclusive", "ai", "human", "inconclusive", "ai", "inconclusive"]
    result = metrics(truth, predicted)
    assert result["confusion_matrix"]["counts"] == [[1, 1], [1, 1]]
    assert result["false_positive_count"] == result["false_negative_count"] == 1
    assert result["human_false_positive_rate_all_humans"] == result["ai_false_negative_rate_all_ai"] == 1 / 3
    assert result["human_false_positive_rate_classified_humans"] == result["ai_false_negative_rate_classified_ai"] == .5
    assert result["per_class"]["ai"]["precision"] == result["per_class"]["ai"]["recall_classified"] == result["per_class"]["ai"]["f1_classified"] == .5
    assert result["balanced_accuracy_classified"] == result["selective_accuracy"] == result["selective_error"] == .5
    assert result["coverage_eligible"] == 4 / 6 and result["abstention_rate_eligible"] == 2 / 6
    assert result["abstained_total"] == 3
    assert result["non_binary_prediction_distribution"]["mixed"]["ai"] == 1
    assert result["non_binary_prediction_distribution"]["unknown"]["inconclusive"] == 1


def test_no_denominators_and_missing_classes():
    empty = metrics([], [])
    assert empty["coverage_eligible"] is None and empty["selective_accuracy"] is None
    assert empty["balanced_accuracy_classified"] is None
    all_abstain = metrics(["human", "ai"], ["inconclusive", "inconclusive"])
    assert all_abstain["coverage_eligible"] == 0 and all_abstain["selective_error"] is None
    assert all_abstain["human_false_positive_rate_all_humans"] == 0
    assert all_abstain["human_false_positive_rate_classified_humans"] is None
    one_class = metrics(["human"], ["human"])
    assert one_class["balanced_accuracy_classified"] is None
    assert one_class["ai_false_negative_rate_all_ai"] is None


@pytest.mark.parametrize("truth,pred", [(["other"], ["ai"]), (["human"], ["other"]), (["human"], []), ([None], ["human"])])
def test_invalid_metric_inputs(truth, pred):
    with pytest.raises(ValueError):
        metrics(truth, pred)


def test_threshold_boundary_and_explicit_inconclusive():
    assert threshold_predictions(["ai", "human", "inconclusive", "ai"], [.2, -.21, .9, 0], .2) == ["inconclusive", "human", "inconclusive", "inconclusive"]


@pytest.mark.parametrize("threshold", [-1, float("nan"), float("inf"), True, "0"])
def test_invalid_threshold(threshold):
    with pytest.raises(ValueError):
        threshold_predictions(["ai"], [1], threshold)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), None, True, "1"])
def test_invalid_score(score):
    with pytest.raises(ValueError):
        threshold_predictions(["ai"], [score], 0)


def test_validation_sweep_domains_and_reproducible_reports(inputs):
    first = report(inputs, min_domain_count=2)
    second = report(inputs, min_domain_count=2)
    assert as_json(first) == as_json(second) and as_markdown(first) == as_markdown(second)
    assert SYNTHETIC_WARNING in as_json(first) and SYNTHETIC_WARNING in as_markdown(first)
    assert [r["threshold"] for r in first["runs"]] == [0, .2]
    assert first["runs"][0]["domains"]["fictional-cv"]["metrics"] is not None
    assert first["runs"][1]["overall"]["coverage_eligible"] == 0
    assert "Ancient observatory" not in as_json(first)
    assert report(inputs)["runs"][0]["domains"]["fictional-cv"]["metrics"] is None


def test_test_split_rejects_sweeps(inputs):
    records, _ = inputs
    all_records, all_outputs = fictional_fixture()
    test_outputs = [o for r, o in zip(all_records, all_outputs) if r["split"] == "test"]
    with pytest.raises(ValueError, match="exactly one"):
        report((records, test_outputs), split="test", thresholds=[0, .2])
    result = report((records, test_outputs), split="test", thresholds=[.2])
    assert result["evaluation_split"] == "test"


def test_output_ids_must_match(inputs):
    records, outputs = inputs
    with pytest.raises(ValueError, match="Missing predictions"):
        report((records, outputs[:-1]))
    with pytest.raises(ValueError, match="uniquely match"):
        report((records, outputs + [outputs[0]]))


def test_source_status_and_synthetic_warning_cannot_be_removed(inputs):
    with pytest.raises(ValueError, match="approved"):
        report(inputs, evidence_status="unvalidated_research")
    records, outputs = deepcopy(inputs)
    for row in records:
        row["license_status"] = "approved"
    result = report((records, outputs), evidence_status="unvalidated_research")
    assert result["warning"] == SYNTHETIC_WARNING and result["evidence_status"] == "synthetic"


def test_missing_provenance_and_invalid_splits(inputs):
    records, outputs = deepcopy(inputs)
    records[0]["provenance_group"] = ""
    with pytest.raises(ValueError, match="provenance_group"):
        report((records, outputs))
    records[0]["provenance_group"] = "valid"
    records[0]["split"] = None
    with pytest.raises(ValueError, match="every record"):
        report((records, outputs))


def test_cross_split_duplicate_and_provenance_fail(inputs):
    records, outputs = deepcopy(inputs)
    records[3]["text"] = records[0]["text"]
    records[3]["text_hash"] = text_hash(records[3]["text"])
    records[3]["label"] = records[0]["label"]
    with pytest.raises(ValueError, match="cross-split"):
        report((records, outputs))
    records, outputs = deepcopy(inputs)
    records[3]["related_groups"] = [records[0]["provenance_group"]]
    with pytest.raises(ValueError, match="provenance"):
        report((records, outputs))


def test_near_duplicate_warning_within_split(inputs):
    records, outputs = deepcopy(inputs)
    records[4]["text"] = records[3]["text"] + " Extra."
    records[4]["text_hash"] = text_hash(records[4]["text"])
    result = report((records, outputs))
    assert result["leakage_audit"]["within_split_near_pairs"] >= 1
