from copy import deepcopy
from pathlib import Path

import pytest

from ml.baseline import train
from ml.challenge import evaluate_challenge, metrics, validate_challenge
from ml.dataset import load_dataset, split_records

FIXTURES = Path(__file__).parents[1] / "ml" / "fixtures"


@pytest.fixture
def data():
    return (load_dataset(FIXTURES / "synthetic_smoke.json"),
            load_dataset(FIXTURES / "fictional_challenge.json"))


def test_challenge_is_valid_isolated_and_deterministic(data):
    smoke, challenge = data
    validate_challenge(smoke, challenge)
    training, test = split_records(smoke)
    fitted = train(training, test)
    assert evaluate_challenge(fitted, challenge) == evaluate_challenge(fitted, challenge)
    assert "moisture" not in fitted.named_steps["tfidf"].vocabulary_
    assert evaluate_challenge(fitted, challenge)["overall"]["count"] == len(challenge)


@pytest.mark.parametrize("field", ["source_id", "document_group"])
def test_source_overlap_rejected(data, field):
    smoke, challenge = data
    challenge[0][field] = " " + smoke[-1][field].upper() + " "
    with pytest.raises(ValueError, match="overlap"):
        validate_challenge(smoke, challenge)


@pytest.mark.parametrize("text", ["exact", "normalized", "near"])
def test_cross_dataset_duplicates_rejected(data, text):
    smoke, challenge = data
    original = smoke[0]["text"]
    challenge[0]["text"] = {"exact": original, "normalized": original.upper(), "near": original + " An extra sentence."}[text]
    with pytest.raises(ValueError, match="[Dd]uplicate|near-duplicate"):
        validate_challenge(smoke, challenge)


def test_rewrite_leak_and_schema_rejected(data):
    smoke, challenge = data
    challenge[0]["rewrite"] = smoke[-1]["text"]
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        validate_challenge(smoke, challenge)
    challenge = deepcopy(data[1])
    challenge[0]["category"] = "unknown"
    with pytest.raises(ValueError, match="category"):
        validate_challenge(smoke, challenge)


def test_challenge_split_rejected(data):
    smoke, challenge = data
    challenge[0]["split"] = "train"
    with pytest.raises(ValueError, match="training split"):
        validate_challenge(smoke, challenge)


def test_known_metrics_and_missing_human():
    records = [{"label": label} for label in ("human", "human", "ai", "ai")]
    result = metrics(records, ["ai", "human", "ai", "human"])
    assert result["confusion_matrix"]["rows_actual_columns_predicted"] == [[1, 1], [1, 1]]
    assert result["human_false_positive_rate"] == 0.5
    assert all(result["per_class"][label]["f1"] == 0.5 for label in ("human", "ai"))
    assert metrics([{"label": "ai"}], ["ai"])["human_false_positive_rate"] is None
