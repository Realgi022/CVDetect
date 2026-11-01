"""Fictional diagnostic only: train on the fixed smoke partition, never on this set."""
import json
import re
import string
from collections import Counter
from pathlib import Path

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from .baseline import train
from .dataset import check_split, load_dataset, normalize, split_records

FIXTURES = Path(__file__).parent / "fixtures"
CATEGORIES = {"student_project", "professional_achievement", "career_change", "technical_bullets", "polished_summary"}


def validate_challenge(smoke, challenge):
    if any("split" in r for r in challenge):
        raise ValueError("Challenge records must not specify a training split.")
    for r in challenge:
        if r.get("category") not in CATEGORIES:
            raise ValueError("Invalid challenge category.")
        if ("rewrite" in r) != ("rewrite_kind" in r):
            raise ValueError("Rewrites require text and a kind.")
        if "rewrite" in r and (not isinstance(r["rewrite"], str) or not normalize(r["rewrite"]) or not isinstance(r["rewrite_kind"], str) or not r["rewrite_kind"].strip()):
            raise ValueError("Invalid rewrite.")
    # Check both smoke partitions, including rewrites, without treating related
    # challenge versions as independent records in the reported metrics.
    smoke_without_split = [{k: v for k, v in r.items() if k != "split"} for r in smoke]
    check_split(smoke_without_split, challenge)
    for r in challenge:
        if "rewrite" in r:
            variant = dict(r, text=r["rewrite"])
            check_split(smoke_without_split, [variant, next(x for x in challenge if x["label"] != r["label"])])


def metrics(records, predictions):
    labels = ["human", "ai"]
    truth = [r["label"] for r in records]
    matrix = confusion_matrix(truth, predictions, labels=labels)
    p, r, f, support = precision_recall_fscore_support(truth, predictions, labels=labels, zero_division=0)
    return {"count": len(records), "class_counts": dict(Counter(truth)),
            "confusion_matrix": {"label_order": labels, "rows_actual_columns_predicted": matrix.tolist()},
            "per_class": {label: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(support[i])} for i, label in enumerate(labels)},
            "human_false_positive_rate": float(matrix[0, 1] / matrix[0].sum()) if matrix[0].sum() else None}


def evaluate_challenge(model, records):
    predictions = list(model.predict([r["text"] for r in records]))
    categories = {}
    for category in sorted(CATEGORIES):
        indices = [i for i, r in enumerate(records) if r["category"] == category]
        if len(indices) >= 2:
            categories[category] = metrics([records[i] for i in indices], [predictions[i] for i in indices])
    checks = {}
    transformations = {
        "punctuation_removed": lambda s: s.translate(str.maketrans("", "", string.punctuation)),
        "uppercase": str.upper,
        "single_line": lambda s: re.sub(r"\s+", " ", s).strip(),
    }
    for name, transform in transformations.items():
        modified = list(model.predict([transform(r["text"]) for r in records]))
        checks[name] = {"paired_count": len(records), "prediction_changes": sum(a != b for a, b in zip(predictions, modified)), "changed_source_ids": [records[i]["source_id"] for i, (a, b) in enumerate(zip(predictions, modified)) if a != b]}
    related = []
    for i, record in enumerate(records):
        if "rewrite" in record:
            predicted = model.predict([record["rewrite"]])[0]
            related.append({"source_id": record["source_id"], "kind": record["rewrite_kind"], "original_prediction": predictions[i], "rewrite_prediction": predicted, "changed": bool(predicted != predictions[i])})
    return {"warning": "Fictional diagnostic labels are unverified; this is not real-world accuracy, fairness, or authorship probability. Related rewrites are paired, not independent samples.", "overall": metrics(records, predictions), "by_category": categories, "sensitivity": checks, "related_rewrites": related}


def main():
    try:
        smoke = load_dataset(FIXTURES / "synthetic_smoke.json")
        challenge = load_dataset(FIXTURES / "fictional_challenge.json")
        training, test = split_records(smoke)
        validate_challenge(smoke, challenge)
        model = train(training, test)
        print(json.dumps(evaluate_challenge(model, challenge), indent=2))
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Challenge evaluation cannot run: {exc}") from exc


if __name__ == "__main__":
    main()
