# Offline AI-authorship model comparison

**SYNTHETIC SOFTWARE TEST ONLY — NOT REAL-WORLD MODEL VALIDATION.** The command below uses existing fictional CV-style fixtures and their invented labels, not verified author histories. It never downloads data or accesses a model service. It does not modify the local inference model, public API, scoring or UI. The classifier remains unvalidated and the research endpoint remains inconclusive.

## Fictional smoke test

Install `backend/requirements.txt` and `backend/ml/requirements.txt`. From `backend` in PowerShell, create a **new**, private output directory outside any Git working tree:

```powershell
$out = Join-Path $env:TEMP 'cvdetect-day17-fictional'
New-Item -ItemType Directory -Path $out
Set-Content -Path (Join-Path $out '.gitignore') -Value '*' -Encoding ascii
python -m ml.research_training --output-dir $out --seed 42
```

The only CLI input is the fixed bundled fictional fixture. It prints no examples or scores. It writes a JSON test claim, JSON report, and one serialized selected model under `$out`. If the same manifest has already been claimed in that directory, the command refuses a second run—even with a different seed—and it never overwrites an artifact. A claim is retained if a run fails. Inspect report metadata locally with `Get-ChildItem $out` and `Get-Content (Get-ChildItem $out -Filter 'report-*.json').FullName`. These reports and models are fictional diagnostics, not evidence of real-world performance.

For this fictional test, after review, remove only the files created in this dedicated directory, then remove the empty directory:

```powershell
Get-ChildItem $out -File -Filter 'model-*.pkl' | Remove-Item
Get-ChildItem $out -File -Filter 'report-*.json' | Remove-Item
Get-ChildItem $out -File -Filter 'test-claim-*.json' | Remove-Item
Remove-Item (Join-Path $out '.gitignore')
Remove-Item $out
```

For real research, follow the separately approved retention and withdrawal process, including backups and downstream derivatives. `.gitignore` and location checks are not encryption, access control, a secure-deletion mechanism, or protection against malicious local processes. Restrict filesystem access and do not publish raw text, identifiers, report details, hashes or models. TF-IDF vocabularies and coefficients can reveal training content. **Pickle artifacts can execute arbitrary code when loaded**: never load untrusted files, including files from a shared directory or unknown source. This project does not automatically load the artifact into any server. Deletion does not guarantee physical erasure or remove backups.

## Models, labels and eligibility

The offline module compares scikit-learn `TfidfVectorizer` plus logistic regression and TF-IDF plus `LinearSVC`, using fixed default settings, explicit iteration limits and random seed. Each pipeline fits its vectorizer and classifier **only on the same binary-eligible training rows**. Mixed and unknown rows are counted as excluded from fitting; they remain in validation/test evaluations and prediction distributions. Neither style nor model output establishes ground truth. Non-synthetic binary records require an explicit `label_verification: verified` attestation backed by independent evidence. Synthetic records use `illustrative`, never verified. Attestations are not verified by code.

The reusable `run_comparison` function accepts a complete Day 16 CV manifest with assigned train/validation/test splits, CV collection metadata, and `label_verification` on binary rows. It uses the existing manifest audit and collection validator. Source status, consent, privacy and rights reviews must be complete for every row, with approved license status for non-synthetic rows; parent/prompt links and required metadata are checked. Binary training requires at least two independent connected groups per class; both validation and test must contain both binary labels. These minimums are software safeguards, not scientifically sufficient sample sizes. The tool does not independently check consent, label evidence, source rights or missing/incorrect provenance. Real-world use requires separate ethical/legal and privacy review, consent scope verification, preapproved research protocol, trustworthy labels and securely managed data. **MAGE, HC3 and TXD-22 remain blocked**. No real dataset is approved by this code; the CLI deliberately has no real-data input option.

## Validation, abstention and holdout

The two candidates and fixed thresholds 0, 0.05 and 0.1 are evaluated on validation data only, using [the existing evaluation definitions](ai_authorship_evaluation.md). The predetermined rule maximizes classified balanced accuracy, then minimizes human false positives among all human-labeled validation rows, then maximizes coverage, then uses the smallest threshold and lexical model name for deterministic ties. This is a software exercise, not a safety criterion; selective metrics can conceal abstention and false positives remain consequential. The model and threshold are fixed before evaluating the test partition once. Reports include the validation comparisons, selected configuration and a single held-out evaluation, including coverage, errors, class metrics and domain breakdown. Decision values are raw margins **not probabilities of authorship**.

An exclusive manifest-fingerprint claim prevents repeating the test in the same output directory, including after interruption. This is **not tamper-proof**: another directory, edited manifest, process or manual deletion can bypass it, and repeated test exposure can contaminate a holdout. Enforce a separate access-controlled test registry, preregister model selection, freeze the test set, and replace exposed test sets for later experiments. The fingerprint covers all manifest fields and exact text, not independent evidence of source provenance. The report records split IDs, configuration, seed, Python/scikit-learn/numpy/scipy versions and fingerprint; reproducibility can still vary across platforms and numerical libraries. Hashes and IDs can be sensitive or linkable.

## Before any public deployment

There is no go decision. Fictional labels, tiny samples and observed writing style cannot establish accuracy or fairness. A future study needs independently consented, provenance-verified CV-specific data, source-separated test sets, meaningful sample sizes, mixed/unknown and editing analyses, subgroup and language assessments, false-positive and false-negative rates with uncertainty, independent replication, prespecified acceptance criteria, shift monitoring and legal/ethical review. Even then, do not present raw margins as authorship probabilities or use them as proof of authorship or automated hiring decisions. Maintain human oversight and appeals, and demonstrate a justified safe use before considering any deployment.
