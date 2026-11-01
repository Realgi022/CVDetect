"""Offline metrics for supplied predictions; never trains or serves a model."""
import argparse
import json
import math
from collections import Counter

from .dataset import identifier
from .manifest_audit import audit_manifest, text_hash

SYNTHETIC_WARNING = "SYNTHETIC SOFTWARE TEST ONLY — NOT REAL-WORLD MODEL VALIDATION."
LIMITATIONS = [
    "Labels and source status are supplied metadata, not independently verified by this tool.",
    "Raw decision scores are not AI-authorship probabilities; abstention does not establish safety or accuracy.",
    "Duplicate heuristics cannot prove independence or detect all undocumented relationships.",
    "Metrics are descriptive research diagnostics, not proof of authorship or suitability for applicant decisions.",
]
PREDICTIONS = {"human", "ai", "inconclusive"}


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def metrics(truth, predictions):
    """Binary metrics on classified eligible examples; abstentions remain visible."""
    if len(truth) != len(predictions):
        raise ValueError("Truth and predictions must have equal length.")
    if any(not isinstance(x, str) or x not in {"human", "ai", "mixed", "unknown"} for x in truth):
        raise ValueError("Invalid ground-truth label.")
    if any(not isinstance(x, str) or x not in PREDICTIONS for x in predictions):
        raise ValueError("Invalid prediction label.")
    counts = {label: truth.count(label) for label in ("human", "ai", "mixed", "unknown")}
    matrix = [[0, 0], [0, 0]]
    abstained = {"human": 0, "ai": 0}
    distribution = {label: {p: 0 for p in ("human", "ai", "inconclusive")} for label in ("mixed", "unknown")}
    for actual, predicted in zip(truth, predictions):
        if actual in distribution:
            distribution[actual][predicted] += 1
        elif predicted == "inconclusive":
            abstained[actual] += 1
        else:
            matrix[("human", "ai").index(actual)][("human", "ai").index(predicted)] += 1
    tn, fp = matrix[0]
    fn, tp = matrix[1]
    eligible = counts["human"] + counts["ai"]
    classified = tn + fp + fn + tp
    per_class = {}
    for name, true_positive, false_positive, false_negative, support in (
        ("human", tn, fn, fp, counts["human"]), ("ai", tp, fp, fn, counts["ai"]),
    ):
        per_class[name] = {
            "support_including_abstentions": support,
            "precision": _ratio(true_positive, true_positive + false_positive),
            "recall_classified": _ratio(true_positive, true_positive + false_negative),
            "f1_classified": _ratio(2 * true_positive, 2 * true_positive + false_positive + false_negative),
        }
    recalls = [per_class[name]["recall_classified"] for name in ("human", "ai")]
    return {
        "class_counts": counts, "total": len(truth), "eligible_binary": eligible,
        "confusion_matrix": {"rows_actual": ["human", "ai"], "columns_predicted": ["human", "ai"], "counts": matrix},
        "per_class": per_class,
        "balanced_accuracy_classified": sum(recalls) / 2 if all(x is not None for x in recalls) else None,
        "false_positive_count": fp, "false_negative_count": fn,
        "human_false_positive_rate_all_humans": _ratio(fp, counts["human"]),
        "human_false_positive_rate_classified_humans": _ratio(fp, tn + fp),
        "ai_false_negative_rate_all_ai": _ratio(fn, counts["ai"]),
        "ai_false_negative_rate_classified_ai": _ratio(fn, tp + fn),
        "abstained_by_eligible_class": abstained, "abstained_eligible": sum(abstained.values()),
        "abstained_total": predictions.count("inconclusive"), "classified_eligible": classified,
        "coverage_eligible": _ratio(classified, eligible), "abstention_rate_eligible": _ratio(sum(abstained.values()), eligible),
        "selective_accuracy": _ratio(tn + tp, classified), "selective_error": _ratio(fp + fn, classified),
        "non_binary_prediction_distribution": distribution,
    }


def threshold_predictions(predictions, scores, threshold):
    """Apply the existing conservative margin convention, retaining model direction.

    Predictions must come from the model's actual class ordering, not a guessed
    sign. Explicit inconclusive predictions always remain inconclusive.
    """
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or threshold < 0:
        raise ValueError("Threshold must be finite and nonnegative.")
    if len(predictions) != len(scores):
        raise ValueError("Predictions and scores must have equal length.")
    if any(not isinstance(p, str) or p not in PREDICTIONS for p in predictions):
        raise ValueError("Invalid prediction label.")
    if any(isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s) for s in scores):
        raise ValueError("Decision scores must be finite numbers.")
    return ["inconclusive" if abs(score) <= threshold else pred for pred, score in zip(predictions, scores)]


def evaluate_experiment(records, outputs, *, split, thresholds, model_id, seed, evidence_status, min_domain_count=10):
    """Audit all partitions and evaluate keyed predictions on validation or test.

    Validation supports sweeps; test accepts exactly one preselected threshold.
    Input labels, licensing and group identities are not verified by this code.
    """
    audit = audit_manifest(records)
    if records[0]["split"] is None:
        raise ValueError("All train, validation and test splits must be assigned.")
    if split not in ("validation", "test"):
        raise ValueError("Evaluate validation or test only.")
    if not isinstance(thresholds, (list, tuple)) or not thresholds or (split == "test" and len(thresholds) != 1):
        raise ValueError("Use one or more validation thresholds, or exactly one preselected test threshold.")
    if not isinstance(model_id, str) or not model_id.strip() or not isinstance(seed, (str, int)) or isinstance(seed, bool) or not str(seed).strip():
        raise ValueError("Model ID and experiment seed are required.")
    if evidence_status not in ("synthetic", "unvalidated_research"):
        raise ValueError("Invalid evidence status.")
    if evidence_status != "synthetic" and any(r["license_status"] != "approved" for r in records):
        raise ValueError("Non-synthetic research requires manually approved source status for every record.")
    if isinstance(min_domain_count, bool) or not isinstance(min_domain_count, int) or min_domain_count < 2:
        raise ValueError("Minimum domain count must be an integer of at least two.")
    selected = [r for r in records if r["split"] == split]
    def key(row):
        return (identifier(row["dataset_id"]), identifier(row["original_record_id"]))
    expected = {key(r) for r in selected}
    if not isinstance(outputs, list):
        raise ValueError("Outputs must be a list of keyed predictions.")
    by_id = {}
    for output in outputs:
        if not isinstance(output, dict) or any(not isinstance(output.get(k), str) or not output[k].strip() for k in ("dataset_id", "original_record_id")):
            raise ValueError("Each output requires dataset and original record IDs.")
        k = key(output)
        if k in by_id or k not in expected:
            raise ValueError("Output IDs must uniquely match the evaluation split.")
        by_id[k] = output
    if set(by_id) != expected:
        raise ValueError("Missing predictions for evaluation split.")
    selected.sort(key=key)
    truth = [r["label"] for r in selected]
    predictions = [by_id[key(r)].get("prediction") for r in selected]
    scores = [by_id[key(r)].get("score") for r in selected]
    runs = []
    for threshold in thresholds:
        predicted = threshold_predictions(predictions, scores, threshold)
        domains = {}
        for domain in sorted({r["source_domain"] for r in selected}):
            indexes = [i for i, r in enumerate(selected) if r["source_domain"] == domain]
            labels = [truth[i] for i in indexes]
            eligible_count = sum(label in ("human", "ai") for label in labels)
            enough = eligible_count >= min_domain_count and {"human", "ai"}.issubset(labels)
            domains[domain] = {"count": len(indexes), "eligible_binary": eligible_count,
                               "metrics": metrics(labels, [predicted[i] for i in indexes]) if enough else None,
                               "suppression_reason": None if enough else "Insufficient eligible examples or missing binary class."}
        runs.append({"threshold": threshold, "overall": metrics(truth, predicted), "domains": domains})
    near = sum(p["kind"] == "near" for p in audit["duplicates"])
    exact = sum(p["kind"] == "exact" for p in audit["duplicates"])
    # Synthetic wording cannot be removed even if callers supply different metadata.
    synthetic = evidence_status == "synthetic" or any("fictional" in r["dataset_id"].casefold() for r in records)
    return {
        "warning": SYNTHETIC_WARNING if synthetic else "UNVALIDATED RESEARCH ONLY — NOT REAL-WORLD MODEL VALIDATION.",
        "evidence_status": "synthetic" if synthetic else "unvalidated_research",
        "dataset_sources": sorted({(r["dataset_id"], r["source_url"], r["license_status"]) for r in records}),
        "model_id": model_id, "experiment_seed": seed, "evaluation_split": split,
        "threshold_config": {"rule": "abstain when abs(raw decision score) <= threshold; preserve supplied model prediction otherwise",
                             "selection": "Select independently on validation; never select using final test.",
                             "thresholds": list(thresholds), "min_domain_count": min_domain_count},
        "leakage_audit": {"status": "passed_known_checks", "records": audit["records"], "splits": audit["splits"],
                          "components": audit["components"], "within_split_exact_pairs": exact, "within_split_near_pairs": near,
                          "cross_split_pairs": 0, "provenance_concern": "Missing or incorrect relationships cannot be detected automatically; independently review all provenance and near matches."},
        "runs": runs, "limitations": LIMITATIONS,
    }


def as_json(report):
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"


def as_markdown(report):
    """Deterministic report; embed complete aggregates without exposing records."""
    lines = ["# Offline authorship research evaluation", "", f"**{report['warning']}**", "",
             f"Evidence: {report['evidence_status']}; split: {report['evaluation_split']}; model: {report['model_id']}; seed: {report['experiment_seed']}.",
             "", "## Dataset sources", "", "```json", json.dumps(report["dataset_sources"], ensure_ascii=False, indent=2), "```",
             "", "## Threshold configuration", "", "```json", json.dumps(report["threshold_config"], ensure_ascii=False, indent=2, sort_keys=True), "```",
             "", "## Leakage audit", "", "```json", json.dumps(report["leakage_audit"], ensure_ascii=False, indent=2, sort_keys=True), "```",
             "", "## Metrics and domains", "", "```json", json.dumps(report["runs"], ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False), "```",
             "", "## Limitations", "", *[f"- {item}" for item in report["limitations"]], ""]
    return "\n".join(lines)


def fictional_fixture():
    """Illustrative labels and made-up model outputs, not classifier predictions."""
    texts = ["Ancient observatory catalogued distant stars.", "Bakery arranged colorful window displays.",
             "Marine club repaired a wooden vessel.", "Garden team mapped seasonal flower beds.",
             "Museum hosted a ceramics workshop.", "Lighthouse recorded changing coastal weather.",
             "Orchestra rehearsed a chamber composition.", "Library organized a collection of maps.",
             "Cyclists maintained a mountain trail.", "Robotics group assembled a miniature rover.",
             "Theatre volunteers designed paper scenery."]
    labels = ["human", "ai", "unknown", "human", "ai", "mixed", "unknown", "human", "ai", "mixed", "unknown"]
    splits = ["train"] * 3 + ["validation"] * 4 + ["test"] * 4
    records, outputs = [], []
    for i, (text, label, split) in enumerate(zip(texts, labels, splits)):
        row = {"dataset_id": "fictional-evaluation", "source_url": "https://example.org/fictional-evaluation",
               "license_status": "unverified", "original_record_id": f"fiction-{i:02d}",
               "provenance_group": f"fictional-group-{i:02d}", "related_groups": [], "source_domain": "fictional-cv",
               "model_id": None, "label": label, "text": text, "text_hash": text_hash(text),
               "split": split, "transformations": []}
        records.append(row)
        outputs.append({"dataset_id": row["dataset_id"], "original_record_id": row["original_record_id"],
                        "prediction": "ai" if i % 2 else "human", "score": (i - 5) / 10})
    return records, outputs


def main():
    parser = argparse.ArgumentParser(description="Fictional offline software test; no training or downloading.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.0, 0.2])
    args = parser.parse_args()
    records, outputs = fictional_fixture()
    report = evaluate_experiment(records, [o for r, o in zip(records, outputs) if r["split"] == "validation"],
                                 split="validation", thresholds=args.thresholds, model_id="fictional-stub-not-a-model",
                                 seed="fictional-v1", evidence_status="synthetic")
    print(as_json(report) if args.format == "json" else as_markdown(report), end="")


if __name__ == "__main__":
    main()
