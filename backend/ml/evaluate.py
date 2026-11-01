"""Evaluate a fitted pipeline on the held-out partition only."""
from collections import Counter

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from .dataset import check_split, identifier


def evaluate(model, train_records, test_records):
    check_split(train_records, test_records)
    labels = ["human", "ai"]
    truth = [r["label"] for r in test_records]
    predicted = model.predict([r["text"] for r in test_records])
    matrix = confusion_matrix(truth, predicted, labels=labels)
    precision, recall, f1, support = precision_recall_fscore_support(truth, predicted, labels=labels, zero_division=0)
    human_count = int(matrix[0].sum())
    return {
        "warning": "Research smoke test only: tiny or unrepresentative datasets, especially synthetic labels, cannot establish real-world detection accuracy or authorship.",
        "class_counts": {"train": dict(Counter(r["label"] for r in train_records)), "test": dict(Counter(truth))},
        "group_counts": {part: {key: len({identifier(r[key]) for r in records}) for key in ("source_id", "document_group")} for part, records in (("train", train_records), ("test", test_records))},
        "confusion_matrix": {"label_order": labels, "rows_actual_columns_predicted": matrix.tolist()},
        "per_class": {label: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i]), "support": int(support[i])} for i, label in enumerate(labels)},
        "human_false_positive_rate": float(matrix[0, 1] / human_count) if human_count else None,
    }
