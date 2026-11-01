"""Opt-in trusted local pickle diagnostics. Pickle can execute arbitrary code."""
import hashlib
import hmac
import json
import math
import os
import pickle
import re
from pathlib import Path

from .dev_inference import validate_text

MAX_ARTIFACT_BYTES = 50 * 1024 * 1024


def infer_trusted(text):
    """Load only an explicitly trusted, hash-pinned artifact; never train."""
    validate_text(text)
    if os.environ.get("CVDETECT_RESEARCH_TRUSTED_PICKLE") != "1":
        raise RuntimeError("Trusted artifact opt-in is not configured.")
    model_path = os.environ.get("CVDETECT_RESEARCH_MODEL_PATH", "")
    report_path = os.environ.get("CVDETECT_RESEARCH_MODEL_REPORT", "")
    expected = os.environ.get("CVDETECT_RESEARCH_MODEL_SHA256", "")
    if not model_path or not report_path or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise RuntimeError("Trusted artifact configuration is incomplete.")
    model_file, report_file = Path(model_path), Path(report_path)
    if not model_file.is_absolute() or not report_file.is_absolute() or model_file.is_symlink() or report_file.is_symlink():
        raise RuntimeError("Artifact paths must be absolute regular files.")
    with model_file.open("rb") as handle:
        data = handle.read(MAX_ARTIFACT_BYTES + 1)
    if len(data) > MAX_ARTIFACT_BYTES or not hmac.compare_digest(hashlib.sha256(data).hexdigest(), expected):
        raise RuntimeError("Trusted artifact hash mismatch.")
    with report_file.open("rb") as handle:
        report_bytes = handle.read(1024 * 1024 + 1)
    if len(report_bytes) > 1024 * 1024:
        raise RuntimeError("Invalid research report.")
    try:
        report = json.loads(report_bytes)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise RuntimeError("Invalid research report.") from None
    if (not isinstance(report, dict) or report.get("evidence_status") != "synthetic"
            or report.get("model_version") != "research-comparison-v1"
            or report.get("selected_model") not in ("logistic_regression", "linear_svm")
            or not isinstance(report.get("manifest_fingerprint"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", report["manifest_fingerprint"])
            or model_file.name != f"model-{report['manifest_fingerprint']}.pkl"):
        raise RuntimeError("Artifact metadata is unavailable or unsupported.")
    # A matching digest proves only byte identity, not safety or provenance.
    # Only use artifacts the operator personally created and independently trusts.
    try:
        model = pickle.loads(data)
    except ValueError:
        raise RuntimeError("Unsupported research artifact.") from None
    classes = model.named_steps["classifier"].classes_
    if len(classes) != 2 or set(classes) != {"human", "ai"}:
        raise RuntimeError("Unsupported research model classes.")
    score = float(model.decision_function([text])[0])
    if not math.isfinite(score):
        raise RuntimeError("Invalid research score.")
    return {"status": "unvalidated_research_model", "authorship_conclusion": "inconclusive",
            "model_metadata": {"name": report["selected_model"], "model_version": report["model_version"],
                               "evidence_status": "synthetic", "artifact_sha256": expected,
                               "manifest_fingerprint": report["manifest_fingerprint"]},
            "model_diagnostic": {"raw_uncalibrated_decision_score": score,
                                 "positive_direction": f"toward the illustrative {classes[1]} training label"},
            "limitations": ["Synthetic software-test model trained on fictional examples with illustrative, unverified labels; real-world accuracy and fairness are not established.",
                            "The raw score is not an AI-authorship probability and cannot determine who wrote text.",
                            "False accusations can harm applicants; never use this research diagnostic for hiring or other consequential decisions.",
                            "The conclusion is always inconclusive; abstention does not establish safety or accuracy."]}
