"""Offline research comparison. Never imported by the public or research servers."""
import argparse
import hashlib
import json
import pickle
import platform
from collections import Counter
from pathlib import Path

import sklearn
import numpy
import scipy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from .cv_collection import FIELDS, validate_metadata, validate_output_dir
from .manifest_audit import _components, audit_manifest, duplicate_report, text_hash
from .research_evaluation import SYNTHETIC_WARNING, evaluate_experiment

MODEL_VERSION = "research-comparison-v1"
MODELS = ("logistic_regression", "linear_svm")
THRESHOLDS = (0.0, 0.05, 0.1)


def make_pipeline(kind, seed):
    if kind == "logistic_regression":
        classifier = LogisticRegression(random_state=seed, max_iter=1000)
    elif kind == "linear_svm":
        classifier = LinearSVC(random_state=seed, max_iter=10000)
    else:
        raise ValueError("Unsupported research model.")
    return Pipeline([("tfidf", TfidfVectorizer()), ("classifier", classifier)])


def fingerprint(records):
    """Fingerprint all manifest fields and raw text, not just normalized hashes."""
    stable = sorted(records, key=lambda r: (r["dataset_id"], r["original_record_id"]))
    encoded = json.dumps(stable, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def validate_training_data(records, evidence):
    """Check attestations and group structure; cannot verify their truth."""
    if evidence not in ("synthetic", "unvalidated_research"):
        raise ValueError("Invalid evidence status.")
    audit_manifest(records)
    if records[0]["split"] is None:
        raise ValueError("Assigned train, validation and test splits are required.")
    metadata = []
    for row in records:
        if not FIELDS.issubset(row):
            raise ValueError("CV provenance and consent metadata are required.")
        metadata.append({key: row[key] for key in FIELDS})
        if row["record_id"] != row["original_record_id"]:
            raise ValueError("Record IDs must match the manifest IDs.")
        expected_source = "fictional" if evidence == "synthetic" else "consented-local"
        expected_verification = "illustrative" if evidence == "synthetic" else "verified"
        if row["source_status"] != expected_source:
            raise ValueError("Source status does not match evidence mode.")
        if row["label"] in ("human", "ai") and row.get("label_verification") != expected_verification:
            raise ValueError("Binary labels require the appropriate provenance verification status.")
        if evidence != "synthetic" and row["license_status"] != "approved":
            raise ValueError("Rights status is not approved.")
    validate_metadata(metadata)
    by_id = {row["record_id"]: row for row in records}
    for row in records:
        required = []
        if row["prompt_family"]:
            required.append(row["prompt_family"])
        if row["parent_record_id"]:
            required.append(by_id[row["parent_record_id"]]["provenance_group"])
        if not set(required).issubset(row["related_groups"]):
            raise ValueError("Parent and prompt provenance links are required.")
    # A consent reference may link multiple documents from one participant;
    # count and partition them together even if a group was omitted by mistake.
    grouping = [{**row, "related_groups": [*row["related_groups"], row["consent_ref"]]} for row in records]
    components = _components(grouping, duplicate_report(records))
    if any(len({records[i]["split"] for i in component}) != 1 for component in components):
        raise ValueError("Related consent references or provenance cross partitions.")
    for label in ("human", "ai"):
        groups = sum(any(records[i]["split"] == "train" and records[i]["label"] == label for i in component) for component in components)
        if groups < 2:
            raise ValueError("Training requires at least two independent groups per binary class.")
    for part in ("validation", "test"):
        if {r["label"] for r in records if r["split"] == part and r["label"] in ("human", "ai")} != {"human", "ai"}:
            raise ValueError("Validation and test each require both binary classes.")
    return records


def _outputs(model, records, split):
    selected = [r for r in records if r["split"] == split]
    texts = [r["text"] for r in selected]
    predictions = model.predict(texts)
    scores = model.decision_function(texts)
    return [{"dataset_id": row["dataset_id"], "original_record_id": row["original_record_id"],
             "prediction": str(prediction), "score": float(score)} for row, prediction, score in zip(selected, predictions, scores)]


def run_comparison(records, output_dir, *, evidence, seed=42):
    """One local held-out evaluation per manifest and output directory.

    The exclusive claim is a practical guard, not a tamper-proof test registry.
    Never use test results to change configuration or choose another experiment.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Seed must be an integer between 0 and 2**32 - 1.")
    directory = validate_output_dir(output_dir)
    validate_training_data(records, evidence)
    digest = fingerprint(records)
    claim = directory / f"test-claim-{digest}.json"
    for path in (directory / f"model-{digest}.pkl", directory / f"report-{digest}.json"):
        if path.exists() or path.is_symlink():
            raise FileExistsError("Research output already exists.")
    with claim.open("x", encoding="utf-8") as handle:
        json.dump({"manifest_fingerprint": digest, "status": "claimed", "warning": "Do not repeat test-driven tuning."}, handle)
    # The claim remains even on failure, so an interrupted evaluation is not silently repeated.
    training = sorted((r for r in records if r["split"] == "train" and r["label"] in ("human", "ai")),
                      key=lambda r: (r["dataset_id"], r["original_record_id"]))
    models, validations, choices = {}, {}, []
    for kind in MODELS:
        model = make_pipeline(kind, seed)
        model.fit([r["text"] for r in training], [r["label"] for r in training])
        models[kind] = model
        evaluation = evaluate_experiment(records, _outputs(model, records, "validation"), split="validation",
                                         thresholds=THRESHOLDS, model_id=kind, seed=seed, evidence_status=evidence)
        validations[kind] = evaluation
        for run in evaluation["runs"]:
            m = run["overall"]
            if m["balanced_accuracy_classified"] is not None:
                # Deterministic, explicitly predefined validation-only tie breaking.
                choices.append((m["balanced_accuracy_classified"], -m["human_false_positive_rate_all_humans"],
                                m["coverage_eligible"], -run["threshold"], kind))
    if not choices:
        raise ValueError("Validation does not support selecting a model and threshold.")
    best = max(choices)
    selected, threshold = best[-1], -best[-2]
    test = evaluate_experiment(records, _outputs(models[selected], records, "test"), split="test",
                               thresholds=[threshold], model_id=selected, seed=seed, evidence_status=evidence)
    report = {"warning": SYNTHETIC_WARNING if evidence == "synthetic" else "UNVALIDATED RESEARCH ONLY — NOT REAL-WORLD MODEL VALIDATION.",
              "evidence_status": evidence, "model_version": MODEL_VERSION, "seed": seed,
              "manifest_fingerprint": digest, "model_config": {"vectorizer": "TfidfVectorizer defaults", "candidates": list(MODELS),
              "logistic_regression": {"max_iter": 1000, "random_state": seed}, "linear_svm": {"max_iter": 10000, "random_state": seed},
              "validation_thresholds": list(THRESHOLDS), "selection": "maximize classified balanced accuracy, then minimize human false-positive rate on all humans, then maximize coverage, then lowest threshold; lexical model name breaks remaining ties"},
              "versions": {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
                           "numpy": numpy.__version__, "scipy": scipy.__version__},
              "split_ids": {part: sorted([[r["dataset_id"], r["original_record_id"]] for r in records if r["split"] == part]) for part in ("train", "validation", "test")},
              "training_label_counts": dict(sorted(Counter(r["label"] for r in training).items())),
              "excluded_training_label_counts": dict(sorted(Counter(r["label"] for r in records if r["split"] == "train" and r["label"] not in ("human", "ai")).items())),
              "selected_model": selected, "selected_threshold": threshold, "validation": validations, "test": test,
              "limitations": ["Selection uses validation only; a local claim cannot prevent test reuse in another directory or by another program.",
                              "Metadata are attestations, not proof of consent, provenance, independence or verified authorship.",
                              "Scores are uncalibrated margins, not authorship probabilities; no public deployment is authorized."]}
    # Pickle is executable on load; write only to explicitly configured external storage.
    with (directory / f"model-{digest}.pkl").open("xb") as handle:
        pickle.dump(models[selected], handle, protocol=pickle.HIGHEST_PROTOCOL)
    with (directory / f"report-{digest}.json").open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        handle.write("\n")
    return report


def fictional_records():
    """Build a fixed fictional-only manifest from existing software fixtures."""
    fixtures = Path(__file__).parent / "fixtures"
    smoke = json.loads((fixtures / "synthetic_smoke.json").read_text(encoding="utf-8"))
    challenge = json.loads((fixtures / "fictional_challenge.json").read_text(encoding="utf-8"))
    source = [(r, "train" if r["split"] == "train" else "validation") for r in smoke] + [(r, "test") for r in challenge[:4]]
    records = []
    for i, (row, split) in enumerate(source, 1):
        is_ai = row["label"] == "ai"
        record_id, group = f"r-{i:08x}", f"g-{i:08x}"
        records.append({"dataset_id": "fictional-training-smoke", "source_url": "https://example.org/fictional-training-smoke",
                        "license_status": "unverified", "record_id": record_id, "original_record_id": record_id,
                        "provenance_group": group, "related_groups": [f"g-{i + 1000:08x}"] if is_ai else [],
                        "label": row["label"], "label_verification": "illustrative", "source_status": "fictional",
                        "consent_status": "fictional", "consent_ref": f"c-{i:08x}", "collection_method": "ai-generated" if is_ai else "human-authored",
                        "document_type": "cv-section", "language": "en", "prompt_family": f"g-{i + 1000:08x}" if is_ai else None,
                        "model_id": "fictional-model" if is_ai else None, "model_version": "fictional-v1" if is_ai else None,
                        "generation_settings_ref": "fictional-settings" if is_ai else None, "human_editing_history": [],
                        "parent_record_id": None, "privacy_review": "approved", "rights_review": "approved",
                        "source_domain": "fictional-cv", "text": row["text"], "text_hash": text_hash(row["text"]),
                        "split": split, "transformations": []})
    return records


def main():
    parser = argparse.ArgumentParser(description="Fictional offline training smoke test; no real datasets accepted by this CLI.")
    parser.add_argument("--output-dir", required=True, help="Existing absolute external research directory with ignore-all .gitignore")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        run_comparison(fictional_records(), args.output_dir, evidence="synthetic", seed=args.seed)
        print(SYNTHETIC_WARNING)
        print("Fictional comparison completed; inspect the local report and trusted-only model artifact.")
    except (ValueError, OSError, TypeError, KeyError):
        parser.exit(2, "Research training failed: check data, split, permissions and existing test claim. No input text displayed.\n")


if __name__ == "__main__":
    main()
