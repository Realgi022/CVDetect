"""Small in-memory audit for provenance manifests; never downloads or trains.

Duplicate comparisons are quadratic and intended for small, reviewed batches.
Identifiers and hashes may themselves be sensitive; do not publish audit outputs.
"""
import hashlib
import math
import re
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from .dataset import identifier, normalize, passages

LABELS = frozenset({"human", "ai", "mixed", "unknown"})
SPLITS = frozenset({"train", "validation", "test"})
LICENSES = frozenset({"approved", "conditional", "blocked", "unverified"})


def text_hash(text):
    """SHA-256 of the UTF-8 encoded existing NFKC/casefold/token normalization."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def validate_manifest(records):
    """Validate structure and hashes, without claiming the metadata is truthful."""
    if not isinstance(records, list) or not records:
        raise ValueError("Manifest must be a non-empty list.")
    ids, hashes = set(), {}
    for i, row in enumerate(records):
        if not isinstance(row, dict):
            raise ValueError(f"Record {i}: expected an object.")
        for field in ("dataset_id", "source_url", "original_record_id", "provenance_group", "source_domain", "text"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Record {i}: missing or invalid {field}.")
        try:
            url = urlsplit(row["source_url"])
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.port not in (None, 443):
                raise ValueError
        except ValueError:
            raise ValueError(f"Record {i}: invalid source_url; use an HTTPS URL without credentials.") from None
        for field, allowed in (("label", LABELS), ("license_status", LICENSES)):
            if not isinstance(row.get(field), str) or row[field] not in allowed:
                raise ValueError(f"Record {i}: invalid {field}.")
        if "model_id" not in row or (row["model_id"] is not None and (not isinstance(row["model_id"], str) or not row["model_id"].strip())):
            raise ValueError(f"Record {i}: model_id must be null or a non-empty string.")
        for field in ("related_groups", "transformations"):
            if not isinstance(row.get(field), list) or any(not isinstance(v, str) or not v.strip() for v in row[field]):
                raise ValueError(f"Record {i}: {field} must be a list of non-empty strings.")
        if "split" not in row or (row["split"] is not None and (not isinstance(row["split"], str) or row["split"] not in SPLITS)):
            raise ValueError(f"Record {i}: invalid split.")
        if not normalize(row["text"]):
            raise ValueError(f"Record {i}: no usable text.")
        try:
            digest = text_hash(row["text"])
        except UnicodeEncodeError:
            raise ValueError(f"Record {i}: invalid Unicode in text.") from None
        if not isinstance(row.get("text_hash"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["text_hash"]) or row["text_hash"] != digest:
            raise ValueError(f"Record {i}: invalid or mismatched text_hash.")
        key = (identifier(row["dataset_id"]), identifier(row["original_record_id"]))
        if key in ids:
            raise ValueError(f"Record {i}: duplicate dataset and original record ID.")
        ids.add(key)
        if digest in hashes and hashes[digest] != row["label"]:
            raise ValueError(f"Record {i}: inconsistent labels for identical normalized text.")
        hashes[digest] = row["label"]
    if any(r["split"] is None for r in records) and any(r["split"] is not None for r in records):
        raise ValueError("Split must be assigned to every record or none.")
    return records


def duplicate_report(records, threshold=0.85):
    """Report pair indices only, never text. Approximate matches require review."""
    validate_manifest(records)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("Similarity threshold must be in (0, 1].")
    normalized = [normalize(r["text"]) for r in records]
    result = []
    for i, a in enumerate(normalized):
        for j in range(i + 1, len(records)):
            b = normalized[j]
            exact = a == b
            shared = bool(passages(a) & passages(b))
            # SequenceMatcher can be asymmetric; compare both directions so
            # reordering input records cannot change component membership.
            ratio = max(SequenceMatcher(None, a, b, autojunk=False).ratio(),
                        SequenceMatcher(None, b, a, autojunk=False).ratio())
            if exact or shared or ratio >= threshold:
                result.append({"left": i, "right": j, "kind": "exact" if exact else "near", "cross_split": records[i]["split"] is not None and records[i]["split"] != records[j]["split"]})
    return result


def _components(records, duplicates):
    parent = list(range(len(records)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        parent[find(a)] = find(b)

    groups = {}
    for i, row in enumerate(records):
        for value in [row["provenance_group"], *row["related_groups"]]:
            key = identifier(value)
            if key in groups:
                union(i, groups[key])
            else:
                groups[key] = i
    for pair in duplicates:
        union(pair["left"], pair["right"])
    components = {}
    for i in range(len(records)):
        components.setdefault(find(i), []).append(i)
    return list(components.values())


def audit_manifest(records):
    """Summarize labels, sources, split and duplicates; reject unsafe assigned splits."""
    duplicates = duplicate_report(records)
    components = _components(records, duplicates)
    if any(pair["cross_split"] for pair in duplicates):
        raise ValueError("Unsafe split: cross-split exact or possible near-duplicate.")
    if any(len({records[i]["split"] for i in component}) > 1 for component in components):
        raise ValueError("Unsafe split: related provenance groups cross partitions.")
    if records[0]["split"] is not None and {r["split"] for r in records} != SPLITS:
        raise ValueError("Unsafe split: train, validation and test must all be non-empty.")
    return {"records": len(records), "labels": dict(sorted(Counter(r["label"] for r in records).items())),
            "datasets": dict(sorted(Counter(r["dataset_id"] for r in records).items())),
            "domains": dict(sorted(Counter(r["source_domain"] for r in records).items())),
            "license_statuses": dict(sorted(Counter(r["license_status"] for r in records).items())),
            "splits": dict(sorted(Counter(r["split"] or "unassigned" for r in records).items())),
            "components": len(components), "duplicates": duplicates}


def plan_splits(records, seed="cvdetect-v1"):
    """Plan three partitions by stable hashed components; fail closed on unsafe inputs.

    No class balance or representative sampling is guaranteed. Existing assignments
    are never overwritten. Similarity grouping may overmerge boilerplate.
    """
    validate_manifest(records)
    if any(r["split"] is not None for r in records):
        raise ValueError("Split plan requires unassigned records.")
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("Split seed must be a non-empty string.")
    components = _components(records, duplicate_report(records))
    if len(components) < 3:
        raise ValueError("Unsafe split: at least three independent components are required.")
    def component_key(component):
        ids = sorted((identifier(records[i]["dataset_id"]), identifier(records[i]["original_record_id"])) for i in component)
        import json
        return hashlib.sha256(json.dumps([seed, ids], ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
    components.sort(key=component_key)
    count = len(components)
    n_test = max(1, count // 5)
    n_validation = max(1, count // 5)
    assignment = {}
    for pos, component in enumerate(components):
        split = "test" if pos < n_test else "validation" if pos < n_test + n_validation else "train"
        for i in component:
            assignment[i] = split
    planned = [{**row, "split": assignment[i]} for i, row in enumerate(records)]
    audit_manifest(planned)
    return planned
