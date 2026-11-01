"""Validate fictional or responsibly sourced research data before splitting."""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from sklearn.model_selection import GroupShuffleSplit

REQUIRED = ("text", "label", "source_id", "document_group", "generator_or_author_source")
LABELS = {"human", "ai"}


def normalize(text):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def identifier(value):
    return unicodedata.normalize("NFKC", value).strip().casefold()


def passages(text):
    words = normalize(text).split()
    return {tuple(words[i:i + 10]) for i in range(len(words) - 9)}


def validate_records(records):
    if not isinstance(records, list) or not records:
        raise ValueError("Dataset must be a non-empty JSON array.")
    seen = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Record {index} must be an object.")
        for field in REQUIRED:
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise ValueError(f"Record {index} requires non-empty {field}.")
        if record["label"] not in LABELS:
            raise ValueError(f"Record {index} has invalid label.")
        normalized = normalize(record["text"])
        if not normalized:
            raise ValueError(f"Record {index} has no usable text.")
        if normalized in seen:
            raise ValueError("Duplicate normalized text found; remove duplicates before splitting.")
        seen.add(normalized)
        if "split" in record and record["split"] not in ("train", "test"):
            raise ValueError(f"Record {index} has invalid split.")
    if any("split" in r for r in records) and not all("split" in r for r in records):
        raise ValueError("Split must be specified for every record or none.")
    return records


def load_dataset(path):
    return validate_records(json.loads(Path(path).read_text(encoding="utf-8")))


def check_split(train, test):
    if not train or not test:
        raise ValueError("Train and test must both contain records.")
    validate_records(train + test)
    for key in ("source_id", "document_group"):
        if {identifier(r[key]) for r in train} & {identifier(r[key]) for r in test}:
            raise ValueError(f"{key} overlap across train and test.")
    # Conservative checks for copied passages and near-identical records; not semantic deduplication.
    for left in train:
        a = normalize(left["text"])
        sections_a = {normalize(line) for line in left["text"].splitlines() if len(normalize(line).split()) >= 6}
        for right in test:
            b = normalize(right["text"])
            sections_b = {normalize(line) for line in right["text"].splitlines() if len(normalize(line).split()) >= 6}
            if sections_a & sections_b or passages(a) & passages(b) or SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.85:
                raise ValueError("Possible near-duplicate text or shared section across train and test.")
    if {r["label"] for r in train} != LABELS:
        raise ValueError("Training data must contain both labels.")
    if {r["label"] for r in test} != LABELS:
        raise ValueError("Test data must contain both labels to report class metrics and false-positive rate.")


def split_records(records):
    validate_records(records)
    if "split" in records[0]:
        train = [r for r in records if r["split"] == "train"]
        test = [r for r in records if r["split"] == "test"]
    else:
        # Connected components keep records together when either identifier is shared.
        parents = list(range(len(records)))
        def find(i):
            while parents[i] != i:
                parents[i] = parents[parents[i]]
                i = parents[i]
            return i
        for key in ("source_id", "document_group"):
            first = {}
            for i, record in enumerate(records):
                value = identifier(record[key])
                if value in first:
                    parents[find(i)] = find(first[value])
                else:
                    first[value] = i
        groups = [find(i) for i in range(len(records))]
        if len(set(groups)) < 2:
            raise ValueError("At least two independent groups are required.")
        train_idx, test_idx = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42).split(records, groups=groups))
        train = [records[i] for i in train_idx]
        test = [records[i] for i in test_idx]
    check_split(train, test)
    return train, test
