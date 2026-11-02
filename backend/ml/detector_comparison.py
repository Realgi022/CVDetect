"""Offline, research-only comparison. No training, network, or application routes."""
import argparse
import json
import math
import os
import re
import statistics
import time
from pathlib import Path

from sklearn.metrics import roc_auc_score

from .artifact_inference import infer_trusted
from .cv_collection import FIELDS, REPO, validate_metadata
from .dataset import identifier
from .manifest_audit import audit_manifest
from .research_evaluation import metrics

MIN_WORDS = 20
MAX_CHARS = 20_000
MAX_TOKENS = 512


class TooLong(Exception):
    """Candidate refuses to silently truncate a document."""


def baseline(text):
    result = infer_trusted(text)
    if result['model_metadata']['name'] != 'logistic_regression':
        raise ValueError('Baseline must be the trusted logistic regression artifact.')
    value = result['model_diagnostic']['ai_class_probability']
    if value is None:
        raise ValueError('Baseline does not provide predict_proba.')
    return value


def load_candidate(directory):
    """Load only a locally supplied, independently trusted safetensors checkpoint."""
    path = Path(directory)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ValueError('Candidate path must be an absolute trusted local directory.')
    if not (path / 'model.safetensors').is_file() or (path / 'model.safetensors').is_symlink():
        raise ValueError('A local regular model.safetensors file is required.')
    # This prevents downloads and dynamic model code, not malicious dependency or
    # tokenizer/config exploitation. The operator must review and trust files.
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(str(path), local_files_only=True, trust_remote_code=False, use_safetensors=True)
    model.to('cpu').eval()
    labels = {int(k): str(v).casefold() for k, v in model.config.id2label.items()}
    if labels != {0: 'human', 1: 'ai'} or model.config.model_type != 'roberta':
        raise ValueError('Candidate must expose the expected Human/AI class mapping and RoBERTa architecture.')

    def predict(text):
        tokens = tokenizer(text, return_tensors='pt', truncation=False)
        if tokens['input_ids'].shape[1] > MAX_TOKENS:
            raise TooLong
        with torch.inference_mode():
            return float(torch.softmax(model(**tokens).logits, dim=-1)[0, 1])
    return predict


def validate_inputs(records, split, evidence):
    audit = audit_manifest(records)
    if split not in ('validation', 'test') or not any(r['split'] == split for r in records):
        raise ValueError('Choose a nonempty validation or test split.')
    if evidence not in ('synthetic', 'unvalidated_research'):
        raise ValueError('Invalid evidence status.')
    if evidence == 'unvalidated_research':
        validate_metadata([{k: row.get(k) for k in FIELDS} for row in records])
        if any(r['source_status'] != 'consented-local' or r['license_status'] != 'approved' for r in records):
            raise ValueError('All research examples require documented consent and approved rights.')
    elif any('fictional' not in r['dataset_id'].casefold() for r in records):
        raise ValueError('Synthetic evidence requires fictional dataset IDs.')
    return audit


def compare(records, *, split, evidence, models, threshold=0.5):
    """Run fixed-threshold binary diagnostics on the same audited partition.

    Real data must come from the reviewed local collection metadata workflow.
    Results contain aggregates only. No threshold fitting or model training.
    """
    audit = validate_inputs(records, split, evidence)
    if not isinstance(models, dict) or not models or any(not callable(m) for m in models.values()):
        raise ValueError('Provide named model callables.')
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('Threshold must be a finite value in [0, 1].')
    selected = [r for r in records if r['split'] == split]
    reports = {}
    for name, predict in models.items():
        truth, decisions, scored_truth, scores, latency = [], [], [], [], []
        reasons = {'insufficient_text': 0, 'character_limit': 0, 'candidate_token_limit': 0}
        for row in selected:
            text, label = row['text'], row['label']
            truth.append(label)
            if len(re.findall(r'\w+', text, re.UNICODE)) < MIN_WORDS:
                reasons['insufficient_text'] += 1
                decisions.append('inconclusive')
                continue
            if len(text) > MAX_CHARS:
                reasons['character_limit'] += 1
                decisions.append('inconclusive')
                continue
            start = time.perf_counter()
            try:
                score = predict(text)
            except TooLong:
                reasons['candidate_token_limit'] += 1
                decisions.append('inconclusive')
                continue
            latency.append((time.perf_counter() - start) * 1000)
            if isinstance(score, bool) or not isinstance(score, (float, int)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError('Invalid model output; comparison stopped.')
            decisions.append('ai' if score >= threshold else 'human')
            if label in ('human', 'ai'):
                scored_truth.append(int(label == 'ai'))
                scores.append(score)
        bins = []
        for i in range(10):
            indices = [j for j, p in enumerate(scores) if min(int(p * 10), 9) == i]
            if indices:
                bins.append({'lower': i / 10, 'upper': (i + 1) / 10, 'count': len(indices),
                             'mean_score': sum(scores[j] for j in indices) / len(indices),
                             'observed_ai_fraction': sum(scored_truth[j] for j in indices) / len(indices)})
        reports[name] = {'classification': metrics(truth, decisions), 'abstention_reasons_all_labels': reasons,
                         'scored_binary_count': len(scores),
                         'roc_auc': float(roc_auc_score(scored_truth, scores)) if len(set(scored_truth)) == 2 else None,
                         'brier_score': sum((p - y) ** 2 for p, y in zip(scores, scored_truth)) / len(scores) if scores else None,
                         'calibration_bins': bins,
                         'latency_ms': {'count': len(latency), 'mean': statistics.mean(latency) if latency else None,
                                        'median': statistics.median(latency) if latency else None,
                                        'max': max(latency) if latency else None}}
    return {'warning': 'SYNTHETIC SOFTWARE TEST ONLY — NOT REAL-WORLD MODEL VALIDATION.' if evidence == 'synthetic' else 'UNVALIDATED RESEARCH ONLY — NOT FOR HIRING.',
            'split': split, 'threshold': threshold, 'min_words': MIN_WORDS, 'max_chars': MAX_CHARS,
            'candidate_max_tokens': MAX_TOKENS, 'audit_counts': {'records': audit['records'], 'splits': audit['splits']},
            'models': reports,
            'limitations': ['Metadata, labels, consent and candidate training-set independence are not independently verified.',
                            'Mixed and unknown labels are excluded from binary metrics; no text or identifiers are returned.',
                            'Scores are uncalibrated. Small calibration bins and fictional labels do not establish calibration.',
                            'Latency is per document, includes tokenization and baseline artifact loading, and excludes candidate startup; not a controlled benchmark.',
                            'Each model has its own scored subset; compare coverage as well as metrics. Threshold must be fixed before test evaluation.']}


def main():
    parser = argparse.ArgumentParser(description='Offline comparison; trusted inputs only, never downloads or trains.')
    parser.add_argument('--manifest', required=True, help='Absolute external prepared JSON from ml.cv_collection')
    parser.add_argument('--split', choices=('validation', 'test'), required=True)
    parser.add_argument('--evidence', choices=('synthetic', 'unvalidated_research'), required=True)
    parser.add_argument('--candidate-dir', help='Explicitly trusted local safetensors model directory; optional')
    parser.add_argument('--threshold', type=float, default=0.5, help='Fixed in advance; never select on test')
    args = parser.parse_args()
    try:
        path = Path(args.manifest)
        if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.resolve().is_relative_to(REPO):
            raise ValueError('Manifest must be a regular file outside the repository.')
        payload = json.loads(path.read_text(encoding='utf-8'))
        records = payload['records']
        # Validate the manifest and consent before opening any model artifacts.
        validate_inputs(records, args.split, args.evidence)
        report_path = Path(os.environ.get('CVDETECT_RESEARCH_MODEL_REPORT', ''))
        if not report_path.is_absolute() or report_path.is_symlink() or not report_path.is_file():
            raise ValueError('Trusted baseline report is required.')
        if report_path.stat().st_size > 1024 * 1024:
            raise ValueError('Invalid baseline report.')
        baseline_report = json.loads(report_path.read_text(encoding='utf-8'))
        train_ids = {tuple(map(identifier, item)) for item in baseline_report['split_ids']['train']}
        if any((identifier(r['dataset_id']), identifier(r['original_record_id'])) in train_ids for r in records if r['split'] == args.split):
            raise ValueError('Evaluation records overlap known baseline training IDs.')
        models = {'baseline': baseline}
        if args.candidate_dir:
            models['candidate'] = load_candidate(args.candidate_dir)
        result = compare(records, split=args.split, evidence=args.evidence, models=models, threshold=args.threshold)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, ImportError, RuntimeError):
        parser.exit(2, 'Comparison failed: review manifest, consent, split, trusted artifact configuration and local model dependencies. No input text is displayed.\n')


if __name__ == '__main__':
    main()
