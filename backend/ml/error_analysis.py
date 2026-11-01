"""Offline analysis of the fixed fictional experiment; no model or report is saved."""
import argparse
import json
import math

from .baseline import train
from .challenge import FIXTURES, validate_challenge
from .dataset import load_dataset, split_records


def influential_features(model, limit=10):
    """Rank signed coefficients, using the classifier's actual class ordering.

    These are global training associations, not per-example explanations. The
    vectorizer and coefficients come only from the fitted training partition.
    """
    if limit < 1:
        raise ValueError("Feature limit must be positive.")
    classifier = model.named_steps["classifier"]
    names = model.named_steps["tfidf"].get_feature_names_out()
    coefficients = classifier.coef_[0]
    classes = classifier.classes_
    if len(classes) != 2 or set(classes) != {"human", "ai"}:
        raise ValueError("Expected a binary human/ai classifier.")
    ranked = sorted(zip(names, coefficients), key=lambda item: (float(item[1]), str(item[0])))
    def entries(items):
        return [{"feature": str(name), "coefficient": float(value)} for name, value in items]
    return {
        "warning": "Coefficients associate TF-IDF features with illustrative labels in eight fictional training records; they do not establish authorship or causation. Features may include generic words and are not individual explanations.",
        "positive_coefficient_label": str(classes[1]),
        "negative_coefficient_label": str(classes[0]),
        "toward_negative_label": entries([item for item in ranked if item[1] < 0][:limit]),
        "toward_positive_label": entries(sorted((item for item in ranked if item[1] > 0), key=lambda item: (-float(item[1]), str(item[0])))[:limit]),
    }


def selective_metrics(records, predictions, scores, threshold):
    """Abstain when abs(decision score) <= threshold; no scores are probabilities."""
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("Threshold must be finite and nonnegative.")
    if len(records) != len(predictions) or len(records) != len(scores):
        raise ValueError("Records, predictions and scores must have equal length.")
    if any(not math.isfinite(float(score)) for score in scores):
        raise ValueError("Decision scores must be finite.")
    if any(r["label"] not in ("human", "ai") for r in records) or any(p not in ("human", "ai") for p in predictions):
        raise ValueError("Expected human/ai labels and predictions.")
    classified = [i for i, score in enumerate(scores) if abs(float(score)) > threshold]
    abstained = [i for i, score in enumerate(scores) if abs(float(score)) <= threshold]
    humans = [i for i in classified if records[i]["label"] == "human"]
    abstained_humans = [records[i]["source_id"] for i in abstained if records[i]["label"] == "human"]
    false_positives = sum(predictions[i] == "ai" for i in humans)
    return {
        "threshold": threshold, "total": len(records), "classified": len(classified), "abstained": len(abstained),
        "coverage": len(classified) / len(records) if records else None,
        "selective_accuracy": sum(predictions[i] == records[i]["label"] for i in classified) / len(classified) if classified else None,
        "classified_human_count": len(humans), "human_false_positive_count": false_positives,
        "human_false_positive_rate_among_classified_humans": false_positives / len(humans) if humans else None,
        "total_human_count": sum(r["label"] == "human" for r in records),
        "abstained_human_count": len(abstained_humans), "abstained_human_source_ids": abstained_humans,
    }


def analyze(model, records, thresholds):
    texts = [r["text"] for r in records]
    predictions = list(model.predict(texts)) if texts else []
    scores = list(model.decision_function(texts)) if texts else []
    errors = [{"source_id": r["source_id"], "document_group": r["document_group"],
               "actual_illustrative_label": r["label"], "predicted_label": str(predicted),
               "category": r["category"], "label_provenance": r["generator_or_author_source"],
               "related_rewrite_kind": r.get("rewrite_kind")}
              for r, predicted in zip(records, predictions) if r["label"] != predicted]
    return {
        "warning": "Fictional diagnostic only; labels and editing history are illustrative and unverified. Scores are not authorship probabilities. Abstention does not fix generalization; no threshold is selected for deployment.",
        "training": "Fixed smoke training partition only; challenge originals used only for diagnosis, not fitting or tuning.",
        "challenge_original_count": len(records), "misclassified_count": len(errors), "misclassified": errors,
        "training_feature_associations": influential_features(model),
        "abstention_rule": "Abstain when absolute decision score is less than or equal to the margin; other predictions use the unchanged classifier. Related rewrites are not counted.",
        "abstention_experiments": [selective_metrics(records, predictions, scores, threshold) for threshold in thresholds],
    }


def main():
    parser = argparse.ArgumentParser(description="Fictional offline diagnostic; never an authorship detector.")
    parser.add_argument("--thresholds", type=float, nargs="+", default=[0.0, 0.05, 0.1, 0.2],
                        help="Nonnegative score margins for research only (default: 0 0.05 0.1 0.2).")
    args = parser.parse_args()
    try:
        smoke = load_dataset(FIXTURES / "synthetic_smoke.json")
        challenge = load_dataset(FIXTURES / "fictional_challenge.json")
        training, test = split_records(smoke)
        validate_challenge(smoke, challenge)
        model = train(training, test)
        print(json.dumps(analyze(model, challenge, args.thresholds), indent=2, allow_nan=False))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error analysis cannot run: {exc}\n")


if __name__ == "__main__":
    main()
