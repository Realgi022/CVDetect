from copy import deepcopy
from pathlib import Path

import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from ml.baseline import create_pipeline, train
from ml.dataset import check_split, load_dataset, split_records, validate_records
from ml.evaluate import evaluate

DATA = Path(__file__).parents[1] / "ml" / "fixtures" / "synthetic_smoke.json"


@pytest.fixture
def records():
    return load_dataset(DATA)


@pytest.mark.parametrize("field,value", [("label", "unknown"), ("text", ""), ("text", "   "), ("text", "!!!"), ("source_id", ""), ("document_group", None), ("generator_or_author_source", "")])
def test_invalid_record(records, field, value):
    records[0][field] = value
    with pytest.raises(ValueError):
        validate_records(records)


@pytest.mark.parametrize("field", ["text", "label", "source_id", "document_group", "generator_or_author_source"])
def test_missing_field(records, field):
    del records[0][field]
    with pytest.raises(ValueError):
        validate_records(records)


def test_duplicate_normalized_text(records):
    records[1]["text"] = "  " + records[0]["text"].upper() + "  "
    with pytest.raises(ValueError, match="Duplicate"):
        split_records(records)


@pytest.mark.parametrize("field", ["source_id", "document_group"])
def test_group_overlap(records, field):
    records[-1][field] = " " + records[0][field].upper() + " "
    with pytest.raises(ValueError, match="overlap"):
        split_records(records)


def test_near_duplicate_and_shared_section(records):
    records[-1]["text"] = records[0]["text"] + " Additional detail."
    with pytest.raises(ValueError, match="near-duplicate"):
        split_records(records)
    records[-1]["text"] = "Unrelated start.\n" + records[0]["text"] + "\nUnrelated ending about a different fictional role."
    with pytest.raises(ValueError, match="shared section"):
        split_records(records)


def test_shared_passage_with_different_boundaries(records):
    records[0]["text"] = "Introduction: one two three four five six seven eight nine ten eleven twelve. End."
    records[-1]["text"] = "Different start, one two three four five six seven eight nine ten eleven twelve. Different end."
    with pytest.raises(ValueError, match="near-duplicate"):
        split_records(records)


def test_missing_or_invalid_splits(records):
    del records[0]["split"]
    with pytest.raises(ValueError, match="every record"):
        validate_records(records)
    records[0]["split"] = "validation"
    with pytest.raises(ValueError, match="invalid split"):
        validate_records(records)


def test_pipeline_and_held_out_vocabulary(records):
    pipeline = create_pipeline()
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.named_steps["tfidf"], TfidfVectorizer)
    assert isinstance(pipeline.named_steps["classifier"], LogisticRegression)
    training, test = split_records(records)
    test[0]["text"] += " uniquetestonlytoken"
    fitted = train(training, test)
    assert "uniquetestonlytoken" not in fitted.named_steps["tfidf"].vocabulary_


def test_metrics_and_reproducibility(records):
    training, test = split_records(records)
    first = evaluate(train(training, test), training, test)
    second = evaluate(train(training, test), training, test)
    assert first == second
    assert first["class_counts"] == {"train": {"human": 4, "ai": 4}, "test": {"human": 2, "ai": 2}}
    assert first["group_counts"]["test"] == {"source_id": 4, "document_group": 4}
    assert sum(map(sum, first["confusion_matrix"]["rows_actual_columns_predicted"])) == 4


def test_known_metrics(records):
    training, test = split_records(records)
    class Stub:
        def predict(self, texts):
            return ["ai", "human", "ai", "human"]
    result = evaluate(Stub(), training, test)
    assert result["confusion_matrix"]["rows_actual_columns_predicted"] == [[1, 1], [1, 1]]
    assert result["human_false_positive_rate"] == 0.5
    assert all(result["per_class"][label]["f1"] == 0.5 for label in ("human", "ai"))


def test_group_split_deterministic(records):
    for record in records:
        del record["split"]
    # Shared identifiers form transitive components and must not cross the split.
    records[1]["source_id"] = records[0]["source_id"]
    records[2]["document_group"] = records[1]["document_group"]
    first = split_records(records)
    assert first == split_records(deepcopy(records))
    check_split(*first)
