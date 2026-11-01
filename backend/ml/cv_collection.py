"""Explicit local CV research preparation. No network, model, or application routes."""
import argparse
import json
import re
from pathlib import Path

from .manifest_audit import audit_manifest, duplicate_report, plan_splits, text_hash

REPO = Path(__file__).resolve().parents[2]
FICTIONAL_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cv_collection"
TOKEN = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
RECORD = re.compile(r"r-[0-9a-f]{8}\Z")
GROUP = re.compile(r"g-[0-9a-f]{8}\Z")
CONSENT = re.compile(r"c-[0-9a-f]{8}\Z")
MAX_BYTES = 100_000
FIELDS = {"record_id", "provenance_group", "related_groups", "label", "source_status", "consent_status",
          "consent_ref", "collection_method", "document_type", "language", "prompt_family", "model_id",
          "model_version", "generation_settings_ref", "human_editing_history", "parent_record_id",
          "privacy_review", "rights_review"}
EDIT_CODES = {"human-edited", "ai-assisted-edit", "human-reviewed", "fictional-edit"}
METHODS = {"human": "human-authored", "ai": "ai-generated", "mixed": "ai-assisted", "unknown": "unknown-origin"}


def _token(value, pattern=TOKEN):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def validate_metadata(rows):
    """Validate metadata before any document text is opened; no proof of consent."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("Metadata must be a non-empty list.")
    ids = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError(f"Record {i}: metadata fields are missing or unsupported.")
        if not _token(row["record_id"], RECORD) or row["record_id"] in ids:
            raise ValueError(f"Record {i}: invalid or duplicate record ID.")
        ids[row["record_id"]] = row
        if not _token(row["provenance_group"], GROUP) or not isinstance(row["related_groups"], list) or any(not _token(x, GROUP) for x in row["related_groups"]):
            raise ValueError(f"Record {i}: invalid provenance group.")
        if not isinstance(row["label"], str) or row["label"] not in METHODS or row["collection_method"] != METHODS[row["label"]]:
            raise ValueError(f"Record {i}: invalid label or collection method.")
        if row["source_status"] not in ("fictional", "consented-local"):
            raise ValueError(f"Record {i}: unsupported source status.")
        if row["consent_status"] != ("fictional" if row["source_status"] == "fictional" else "documented"):
            raise ValueError(f"Record {i}: consent missing, withdrawn or inconsistent.")
        if not _token(row["consent_ref"], CONSENT):
            raise ValueError(f"Record {i}: pseudonymous consent reference required.")
        if row["rights_review"] != "approved" or row["privacy_review"] != "approved":
            raise ValueError(f"Record {i}: privacy and rights review must be approved.")
        if row["document_type"] not in ("cv", "resume", "cv-section") or not _token(row["language"]):
            raise ValueError(f"Record {i}: invalid document type or language code.")
        if not isinstance(row["human_editing_history"], list) or any(not isinstance(x, str) or x not in EDIT_CODES for x in row["human_editing_history"]):
            raise ValueError(f"Record {i}: invalid editing history.")
        for field in ("model_id", "model_version", "generation_settings_ref"):
            if row[field] is not None and not _token(row[field]):
                raise ValueError(f"Record {i}: invalid generation metadata.")
        if row["prompt_family"] is not None and not _token(row["prompt_family"], GROUP):
            raise ValueError(f"Record {i}: invalid prompt family.")
        if row["label"] in ("ai", "mixed"):
            if not all(row[k] for k in ("model_id", "prompt_family", "generation_settings_ref")):
                raise ValueError(f"Record {i}: generation model, prompt family and settings reference are required.")
        elif any(row[k] is not None for k in ("model_id", "model_version", "prompt_family", "generation_settings_ref")):
            raise ValueError(f"Record {i}: generation metadata conflicts with label.")
        if row["label"] == "mixed":
            if not _token(row["parent_record_id"], RECORD) or not row["human_editing_history"]:
                raise ValueError(f"Record {i}: mixed records require a parent and editing history.")
        elif row["parent_record_id"] is not None or row["human_editing_history"]:
            raise ValueError(f"Record {i}: unexpected parent or editing history.")
    for i, row in enumerate(rows):
        if row["label"] == "mixed":
            parent = ids.get(row["parent_record_id"])
            if not parent or parent["label"] != "human" or parent["source_status"] != row["source_status"] or parent["consent_ref"] != row["consent_ref"]:
                raise ValueError(f"Record {i}: mixed record requires a human parent in the same source category.")
    return rows


def _outside_repo(path):
    return not path.is_relative_to(REPO)


def validate_output_dir(output):
    """Require an existing external, non-repository directory with an ignore-all marker."""
    raw = Path(output)
    if not raw.is_absolute() or raw.is_symlink():
        raise ValueError("Output must be an absolute external research directory, not a symlink.")
    directory = raw.resolve()
    if not _outside_repo(directory) or not directory.is_dir():
        raise ValueError("Output must be an existing directory outside the project repository.")
    if any((p / ".git").exists() for p in (directory, *directory.parents)):
        raise ValueError("Output must not be inside any Git working tree.")
    marker = directory / ".gitignore"
    if marker.is_symlink() or not marker.is_file() or marker.read_bytes() not in (b"*\n", b"*\r\n"):
        raise ValueError("Output directory requires a regular .gitignore containing only *.")
    return directory


def prepare(rows, input_dir, *, seed="cvdetect-cv-v1"):
    """Load explicitly named UTF-8 files after validation and plan all partitions."""
    validate_metadata(rows)
    directory = Path(input_dir).resolve()
    if not directory.is_dir():
        raise ValueError("Input directory is unavailable.")
    if not _outside_repo(directory) and directory != FICTIONAL_FIXTURES:
        raise ValueError("Only bundled fictional fixture inputs may be inside the repository.")
    if any(row["source_status"] != "fictional" for row in rows) and not _outside_repo(directory):
        raise ValueError("Participant inputs must be outside the project repository.")
    records = []
    parents = {r["record_id"]: r for r in rows}
    for i, row in enumerate(rows):
        path = directory / (row["record_id"] + ".txt")
        try:
            if path.is_symlink() or not path.is_file() or path.resolve().parent != directory or path.stat().st_size > MAX_BYTES:
                raise ValueError
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            raise ValueError(f"Record {i}: text file missing, invalid or too large.") from None
        related = list(row["related_groups"])
        if row["prompt_family"] is not None:
            related.append(row["prompt_family"])
        if row["parent_record_id"] is not None:
            related.append(parents[row["parent_record_id"]]["provenance_group"])
        record = {**row, "dataset_id": "cvdetect-local-collection", "source_url": "https://example.org/cvdetect-local-collection",
                  "license_status": "unverified" if row["source_status"] == "fictional" else "approved", "original_record_id": row["record_id"], "source_domain": "cv",
                  "related_groups": sorted(set(related)), "transformations": row["human_editing_history"],
                  "text": text, "text_hash": text_hash(text), "split": None}
        records.append(record)
    duplicates = duplicate_report(records)
    if any(p["kind"] == "exact" for p in duplicates):
        raise ValueError("Exact normalized duplicate detected; review before preparation.")
    planned = plan_splits(records, seed=seed)
    audit = audit_manifest(planned)
    warning = ("SYNTHETIC SOFTWARE TEST ONLY — NOT REAL-WORLD MODEL VALIDATION; all labels are invented."
               if all(r["source_status"] == "fictional" for r in rows)
               else "RESEARCH ONLY: metadata and consent are not independently verified; labels are not proof of authorship.")
    return {"warning": warning,
            "seed": seed, "near_duplicate_pairs": [{"left_index": p["left"], "right_index": p["right"]} for p in duplicates if p["kind"] == "near"],
            "split_counts": audit["splits"], "records": planned}


def main():
    parser = argparse.ArgumentParser(description="Prepare explicitly supplied local text records; no download or training.")
    parser.add_argument("--metadata", required=True, help="Local JSON metadata list")
    parser.add_argument("--input-dir", required=True, help="Local directory containing ID-named .txt files")
    parser.add_argument("--output-dir", required=True, help="Existing absolute external directory with ignore-all .gitignore")
    parser.add_argument("--seed", default="cvdetect-cv-v1")
    args = parser.parse_args()
    try:
        destination = validate_output_dir(args.output_dir)
        metadata_path = Path(args.metadata)
        if metadata_path.is_symlink() or not metadata_path.is_file() or metadata_path.stat().st_size > MAX_BYTES:
            raise ValueError("Metadata file unavailable or too large.")
        rows = json.loads(metadata_path.read_text(encoding="utf-8"))
        validate_metadata(rows)
        if not _outside_repo(metadata_path.resolve()) and metadata_path.resolve() != FICTIONAL_FIXTURES / "metadata.json":
            raise ValueError("Only bundled fictional metadata may be inside the repository.")
        if any(r["source_status"] != "fictional" for r in rows) and not _outside_repo(metadata_path.resolve()):
            raise ValueError("Participant metadata must be outside the project repository.")
        prepared = prepare(rows, args.input_dir, seed=args.seed)
        result_path = destination / "prepared.json"
        with result_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(prepared, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"Prepared {len(prepared['records'])} records; {len(prepared['near_duplicate_pairs'])} near-duplicate pairs require review. No raw text printed.")
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        parser.exit(2, "Preparation failed: check metadata, consent, paths, duplicates and split requirements; no text is displayed.\n")


if __name__ == "__main__":
    main()
