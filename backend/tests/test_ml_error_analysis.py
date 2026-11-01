import json
import subprocess
import sys
from pathlib import Path

import pytest

from ml.baseline import train
from ml.challenge import FIXTURES, validate_challenge
from ml.dataset import load_dataset, split_records
from ml.error_analysis import analyze, influential_features, selective_metrics


@pytest.fixture
def fitted_and_challenge():
    smoke = load_dataset(FIXTURES / "synthetic_smoke.json")
    challenge = load_dataset(FIXTURES / "fictional_challenge.json")
    validate_challenge(smoke, challenge)
    training, test = split_records(smoke)
    return train(training, test), challenge


def test_report_errors_metadata_and_no_text(fitted_and_challenge):
    model, challenge = fitted_and_challenge
    report = analyze(model, challenge, [0, 0.1])
    assert report == analyze(model, challenge, [0, 0.1])
    assert report["misclassified_count"] == 4
    assert [r["source_id"] for r in report["misclassified"]] == ["challenge-02", "challenge-05", "challenge-08", "challenge-09"]
    assert report["misclassified"][-1]["actual_illustrative_label"] == "human"
    assert report["misclassified"][-1]["predicted_label"] == "ai"
    assert report["misclassified"][-1]["category"] == "polished_summary"
    encoded = json.dumps(report)
    assert all(r["text"] not in encoded and r.get("rewrite", "not-a-rewrite") not in encoded for r in challenge)
    assert "moisture" not in model.named_steps["tfidf"].vocabulary_


def test_feature_coefficient_orientation_and_order(fitted_and_challenge):
    model, _ = fitted_and_challenge
    features = influential_features(model, limit=1000)
    classifier = model.named_steps["classifier"]
    original = dict(zip(model.named_steps["tfidf"].get_feature_names_out(), classifier.coef_[0]))
    assert features["positive_coefficient_label"] == classifier.classes_[1]
    assert features["negative_coefficient_label"] == classifier.classes_[0]
    for side, sign in [("toward_negative_label", -1), ("toward_positive_label", 1)]:
        values = features[side]
        assert all(x["coefficient"] == original[x["feature"]] and sign * x["coefficient"] > 0 for x in values)
        assert [abs(x["coefficient"]) for x in values] == sorted((abs(x["coefficient"]) for x in values), reverse=True)
    with pytest.raises(ValueError, match="positive"):
        influential_features(model, 0)


def test_margin_boundaries_and_denominators():
    records = [{"label": label, "source_id": str(i)} for i, label in enumerate(["human", "human", "ai", "ai", "human"])]
    result = selective_metrics(records, ["ai", "ai", "ai", "human", "human"], [0.2, 0.1, -0.1, -0.11, 0.0], 0.1)
    assert (result["classified"], result["abstained"], result["coverage"]) == (2, 3, 0.4)
    assert result["selective_accuracy"] == 0
    assert (result["human_false_positive_count"], result["classified_human_count"], result["total_human_count"]) == (1, 1, 3)
    assert result["human_false_positive_rate_among_classified_humans"] == 1
    assert result["abstained_human_source_ids"] == ["1", "4"]
    assert result["abstained_human_count"] == 2
    assert selective_metrics(records, ["ai"] * 5, [0] * 5, 0)["classified"] == 0


def test_empty_and_all_abstained():
    result = selective_metrics([], [], [], 0)
    assert result["coverage"] is None and result["selective_accuracy"] is None
    assert result["human_false_positive_rate_among_classified_humans"] is None
    result = selective_metrics([{"label": "human", "source_id": "x"}], ["ai"], [0.01], 0.1)
    assert result["classified"] == 0 and result["abstained_human_count"] == 1
    assert result["selective_accuracy"] is None and result["human_false_positive_rate_among_classified_humans"] is None


@pytest.mark.parametrize("threshold", [-1, float("nan"), float("inf")])
def test_invalid_threshold(threshold):
    with pytest.raises(ValueError, match="Threshold"):
        selective_metrics([], [], [], threshold)


def test_invalid_lengths_and_scores():
    with pytest.raises(ValueError, match="equal length"):
        selective_metrics([], ["ai"], [], 0)
    with pytest.raises(ValueError, match="finite"):
        selective_metrics([{"label": "human", "source_id": "x"}], ["human"], [float("nan")], 0)


def test_cli_custom_thresholds():
    completed = subprocess.run([sys.executable, "-m", "ml.error_analysis", "--thresholds", "0", "0.1"], cwd=Path(__file__).parents[1], capture_output=True, text=True, check=True)
    assert [x["threshold"] for x in json.loads(completed.stdout)["abstention_experiments"]] == [0, 0.1]
