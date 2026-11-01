"""Conservative in-memory readiness inventory; never trains or collects data."""
import argparse
import json
from collections import Counter

from .cv_collection import FIELDS, validate_metadata
from .manifest_audit import _components, audit_manifest, duplicate_report, validate_manifest
from .research_evaluation import SYNTHETIC_WARNING
from .research_training import fictional_records, validate_training_data


def _status_counts(records, field, allowed):
    counts = Counter()
    for row in records:
        value = row.get(field)
        counts[value if isinstance(value, str) and value in allowed else "missing_or_invalid"] += 1
    return dict(sorted(counts.items()))


def readiness(records, *, evidence="synthetic", study=None):
    """Report inventory and blockers, not a certification or a permission grant.

    Optional study attestations are unverified. No identifiers or text appear in
    output. Malformed metadata or leakage always blocks all readiness findings.
    """
    if evidence not in ("synthetic", "unvalidated_research"):
        raise ValueError("Invalid evidence status.")
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("Expected a list of manifest objects.")
    if study is not None and not isinstance(study, dict):
        raise ValueError("Study attestations must be an object.")
    study = study or {}
    counts = {label: sum(r.get("label") == label for r in records) for label in ("human", "ai", "mixed", "unknown")}
    reviews = {
        "consent": _status_counts(records, "consent_status", {"documented", "fictional", "withdrawn", "pending"}),
        "rights": _status_counts(records, "rights_review", {"approved", "pending", "rejected"}),
        "privacy": _status_counts(records, "privacy_review", {"approved", "pending", "rejected"}),
        "license": _status_counts(records, "license_status", {"approved", "blocked", "conditional", "unverified"}),
    }
    blockers = []
    valid = metadata_valid = split_ok = False
    duplicate_counts = {"exact_pairs": None, "near_pairs": None, "cross_split_pairs": None}
    group_count = None
    try:
        validate_manifest(records)
        valid = True
        pairs = duplicate_report(records)
        duplicate_counts = {"exact_pairs": sum(p["kind"] == "exact" for p in pairs),
                            "near_pairs": sum(p["kind"] == "near" for p in pairs),
                            "cross_split_pairs": sum(p["cross_split"] for p in pairs)}
        audit_manifest(records)
        split_ok = records[0]["split"] is not None
        if not split_ok:
            blockers.append("Assigned train, validation and test partitions are not documented.")
    except (ValueError, TypeError, KeyError):
        blockers.append("Manifest is invalid or contains duplicate, provenance or split leakage; review securely.")
    try:
        if not records or any(not FIELDS.issubset(row) for row in records):
            raise ValueError
        validate_metadata([{key: row[key] for key in FIELDS} for row in records])
        metadata_valid = True
    except (ValueError, TypeError, KeyError):
        blockers.append("Collection metadata, consent, rights or privacy review is incomplete or contradictory.")
    if valid and metadata_valid:
        grouped = [{**r, "related_groups": [*r["related_groups"], r["consent_ref"]]} for r in records]
        components = _components(grouped, pairs)
        group_count = len(components)
        if split_ok and any(len({records[i]["split"] for i in part}) > 1 for part in components):
            split_ok = False
            blockers.append("Consent-linked provenance groups cross partitions.")
    if duplicate_counts["near_pairs"]:
        blockers.append("Possible near-duplicates require independent review; heuristics cannot prove independence.")
    try:
        validate_training_data(records, evidence)
        pipeline_eligible = True
    except (ValueError, TypeError, KeyError):
        pipeline_eligible = False
        blockers.append("Training pipeline eligibility checks are not satisfied.")
    if not split_ok:
        blockers.append("Independent partitions cannot be established from current metadata.")
    if evidence == "synthetic" or any(r.get("source_status") == "fictional" for r in records):
        blockers.append("Fictional labels and source histories are not real-world evidence.")
        evidence = "synthetic"

    eligible = {label: sum(r.get("label") == label and r.get("source_status") == "consented-local"
                           and r.get("label_verification") == "verified" and r.get("consent_status") == "documented"
                           and r.get("rights_review") == "approved" and r.get("privacy_review") == "approved"
                           and r.get("license_status") == "approved" for r in records) for label in ("human", "ai")}
    if not valid or not metadata_valid or not split_ok:
        # Do not count records from an invalid, unreviewed or leaking manifest as eligible.
        eligible = {"human": 0, "ai": 0}
    # `model_id` is not a family: a reviewed family mapping must be supplied.
    ai = [r for r in records if r.get("label") in ("ai", "mixed")]
    family_map = study.get("model_families", {})
    family_map = family_map if isinstance(family_map, dict) else {}
    family_values = [family_map.get(r.get("model_id")) if isinstance(r.get("model_id"), str) else None for r in ai]
    family_count = len({v for v in family_values if isinstance(v, str) and v.strip()})
    unmapped_models = sum(not isinstance(v, str) or not v.strip() for v in family_values)
    prompt_count = len({r["prompt_family"] for r in ai if isinstance(r.get("prompt_family"), str) and r["prompt_family"].strip()})
    if unmapped_models:
        blockers.append("Some model-family mappings are missing or unverified.")

    # Explicit separate assertions do not turn unverified metadata into proof.
    attestation = study.get("independence")
    attested = isinstance(attestation, dict) and all(attestation.get(k) is True for k in
        ("author_links_reviewed", "profile_links_reviewed", "prompt_links_reviewed", "split_registry_reviewed"))
    independence = "attested_not_verified" if split_ok and metadata_valid and attested and evidence != "synthetic" else "not_established"
    holdout = study.get("external_holdout")
    holdout_ids = holdout.get("record_ids") if isinstance(holdout, dict) else None
    test_rows = {r["record_id"]: r for r in records if r.get("split") == "test" and isinstance(r.get("record_id"), str)}
    test_ids = set(test_rows)
    holdout_valid = (isinstance(holdout_ids, list) and bool(holdout_ids)
                     and all(isinstance(x, str) for x in holdout_ids)
                     and len(set(holdout_ids)) == len(holdout_ids) and set(holdout_ids).issubset(test_ids)
                     and all(test_rows[x].get("source_status") == "consented-local" and test_rows[x].get("document_type") in ("cv", "resume", "cv-section") for x in holdout_ids)
                     and isinstance(holdout, dict) and all(holdout.get(k) is True for k in
                         ("external_collection", "cv_specific", "unseen_authors", "sealed", "independent_review")))
    external = "attested_not_verified" if holdout_valid and independence == "attested_not_verified" else "not_established"
    subgroup = study.get("subgroup_evaluation")
    subgroup_status = "attested_not_verified" if (evidence != "synthetic" and isinstance(subgroup, dict)
        and all(subgroup.get(k) is True for k in ("consent_and_privacy_approved", "prespecified_groups", "adequate_independent_samples_reviewed"))) else "not_established"
    if independence == "not_established":
        blockers.append("Independent author, profile and prompt splits require documented review.")
    if external == "not_established":
        blockers.append("A genuine independent external CV-specific holdout is not established.")
    if subgroup_status == "not_established":
        blockers.append("Consented and adequately sized subgroup evaluation is not established.")
    if not records:
        blockers.append("No examples supplied.")
    return {
        "warning": SYNTHETIC_WARNING if evidence == "synthetic" else "UNVALIDATED RESEARCH ONLY; all status fields are unverified attestations.",
        "record_count": len(records), "class_counts": counts, "eligible_binary_attested_counts": eligible,
        "independent_provenance_components": group_count,
        "distinct_consent_references_proxy_not_verified_authors": len({r["consent_ref"] for r in records if isinstance(r.get("consent_ref"), str) and r["consent_ref"]}),
        "ai_model_families_attested": family_count, "ai_records_missing_family_mapping": unmapped_models,
        "prompt_families_recorded": prompt_count, "review_status_counts": reviews,
        "duplicates": duplicate_counts, "manifest_valid": valid, "collection_metadata_valid": metadata_valid,
        "known_split_checks_passed": split_ok, "split_independence": independence,
        "external_cv_holdout": external, "subgroup_evaluation": subgroup_status,
        "pipeline_minimum_checks_passed": pipeline_eligible,
        "training": "blocked_pending_independent_review", "evaluation": "blocked_pending_independent_review",
        "public_release": "blocked", "blockers": blockers,
        "limitations": ["Counts and attestations are not independent verification of authorship, consent or rights.",
                        "No sample size, metadata field or duplicate heuristic can establish validity or guarantee independence.",
                        "Subgroups and external holdout require independent governance and evidence; no public release is authorized."],
    }


def main():
    parser = argparse.ArgumentParser(description="Fictional-only readiness software test; no real-data ingestion.")
    parser.parse_args()
    report = readiness(fictional_records())
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()
