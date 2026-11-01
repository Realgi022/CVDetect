# AI-authorship dataset research and preparation

Reviewed 2026-11-01 from the linked public descriptions and metadata only; no full dataset was downloaded, no text was copied into this repository, and no classifier was trained. **All three candidates are blocked for CVDetect training and evaluation pending review.** “Conditional” below means a possible future research use only after the stated conditions are met, not approval. No candidate establishes reliable CV authorship detection or is approved for hiring decisions, the public application, or the local inference server.

## Candidate review

### MAGE — conditional research candidate, currently blocked

- **Official source and citation:** [Hugging Face `yaful/MAGE`](https://huggingface.co/datasets/yaful/MAGE), [project repository](https://github.com/yafuly/MAGE), and Li et al., *MAGE: Machine-generated Text Detection in the Wild* (2024), [paper](https://arxiv.org/abs/2305.13242).
- **License and restrictions:** The Hugging Face card says Apache-2.0, while the project repository's README badge says CC BY 4.0. This discrepancy is unresolved. The paper identifies multiple independently sourced benchmark corpora; neither umbrella claim establishes the rights, source terms, attribution, privacy or ML-training permissions of each item. Review each upstream dataset and applicable terms and reconcile the version/license conflict before any download or use.
- **Count and language:** The Hugging Face viewer reports 436,606 rows for its displayed three splits; the repository describes 447,674 texts and additional testbeds. These figures may cover different releases/subsets; reconciliation is unverified. Primarily English as described by the sampled domains; per-record language and language coverage have not been verified.
- **Domain and labeling:** News, opinion, reviews, question answering, stories, commonsense, Wikipedia and scientific writing. The repository states 0 = machine and 1 = human; it reports generations from 27 models and continuation/topical prompts. Some continuation examples incorporate human text; the binary label alone does not establish purely AI authorship. Map based on documented creation history, not merely this binary code; ambiguous cases remain `mixed` or `unknown`.
- **Provenance and privacy:** Source/model categories are documented, but the displayed HF schema exposes text, label and source rather than the original IDs/prompt-family links required for this project. Completeness of links, authorship histories and version information is unverified. Public online text can contain personal or sensitive information; publication is not consent for every reuse. Review and minimize data, and verify the provenance/rights for each sample.
- **Overlap:** MAGE and HC3 both describe ELI5 as a source ([MAGE paper §3](https://arxiv.org/html/2305.13242#S3), [HC3 repository](https://github.com/Hello-SimpleAI/chatgpt-comparison-detection)); actual record overlap is **unverified**. Other benchmark/pretraining overlap is possible. Audit original IDs, source relationships and duplicates across all corpora and splits.
- **CV suitability:** Out-of-domain only; not an independent CV/resume evaluation. CV-specific use remains blocked.

### HC3 — conditional research candidate, currently blocked

- **Official source and citation:** [HC3 project](https://github.com/Hello-SimpleAI/chatgpt-comparison-detection), [English release](https://huggingface.co/datasets/Hello-SimpleAI/HC3), and Guo et al., *How Close is ChatGPT to Human Experts? Comparison Corpus, Evaluation, and Detection* (2023), [arXiv:2301.07597](https://arxiv.org/abs/2301.07597).
- **License and restrictions:** The project states CC-BY-SA unless source restrictions are stricter. Its own table marks some source licenses unknown and includes noncommercial and other restrictions. Assess each source and current terms independently; the dataset card tag is not blanket permission, and source labels or repository licenses do not establish rights in individual human answers. Unknown/restricted portions remain blocked.
- **Count and language:** English and Chinese question-answer corpora. A [secondary survey](https://www.cs.cit.tum.de/fileadmin/w00cfj/sebis/publications/2023/Dha23a.pdf) reports 24,322 English questions and 12,853 Chinese questions, with multiple answers per question; exact release-specific row/answer totals are **unverified**, and question counts are not individual answer counts.
- **Domain and labeling:** Human answers paired with ChatGPT answers to questions from online Q&A sources, including Reddit ELI5, Wikipedia-related, medical and finance domains. Labels reflect source/collection designation; independent verification of human authorship, assistance, editing, exact model version and provenance at item level is unverified. Group all responses to the same or related question together.
- **Provenance and privacy:** Source and question-level information exists, but author identity, consent, full revisions and prompt families are not established for every item. Medical and forum answers may disclose sensitive personal information. Source-specific permission, privacy and downstream processing must be reviewed before use.
- **Overlap:** Shared upstream ELI5 with MAGE is documented, but shared records are not verified. Cross-corpus source IDs and text matching must be reviewed; translating, splitting into sentences or filtering can hide related examples.
- **CV suitability:** Q&A is not CV writing; no CV-specific validity follows. CV-specific use remains blocked.

### TXD-22 — conditional research candidate, currently blocked

- **Official source and citation:** Iqbal, Md Sadiq and Kashem, Mohammod Abul, *TXD-22: A Large-Scale Benchmark Dataset for Multi-Class AI-Generated and Mixed-Source Text Identification*, Mendeley Data v1 (2026), [DOI:10.17632/prcjcggtjf.1](https://data.mendeley.com/datasets/prcjcggtjf/1).
- **License and restrictions:** The landing page states CC BY 4.0; this is a publisher/contributor claim, not an independent clearance of participant rights, source materials, generated outputs, third-party model terms or permitted ML uses. Verify the actual files, consent scope and upstream restrictions before any use. Attribution and applicable legal requirements remain necessary.
- **Count and language:** The landing page reports 66,000 English Q&A samples, 3,000 per each of 22 classes. These are contributor-reported counts, not independently audited.
- **Domain and labeling:** Academic/professional question-answer responses, not CVs. The description reports 17 AI-system classes, a human-only class and four hybrid/refinement configurations, collected with a common question framework. Not every configuration containing two AI stages is necessarily human/AI mixed; map each using its documented creation history, never silently coerce unknown or mixed into binary labels. System names need not identify exact model/version.
- **Provenance and privacy:** The contributors report voluntary participation, informed consent from approximately 350 human participants, and no retained personally identifiable information. These claims and consent scope have not been independently verified; absence of identifiers is not proof of anonymity. The stated CSV columns are Question, Answer and Source; participant, prompt-family, exact model-version and revision links are not described as available in that schema. Without independently verified author and prompt-family links, safe independent splitting cannot be established.
- **Overlap:** No specific overlap with MAGE/HC3 verified; common questions, sources or generated variants remain possible. Audit before combining datasets.
- **CV suitability:** Useful only as a potential out-of-domain mixed-source research resource after clearance and provenance review. Not evidence of CV detection validity.

## Domain shift and governance

Essays, online answers, news and artificial Q&A differ from resumes in length, formatting, genre, authorship, editing, assistance, accessibility needs, language background and stakes. A model may learn dataset, prompt, vocabulary or style shortcuts rather than provenance; human and AI writing overlap. False accusations can harm applicants. An independently collected, consented, provenance-verified CV-style evaluation with independent authors, prompt families, models and editing histories is necessary even for research; it would not prove authorship or justify deployment. See [collection protocol](../backend/ml/DATASET_PROTOCOL.md) and [research decision](../backend/ml/RESEARCH_DECISION.md). Do not collect real CVs in this repository.

## Manifest and local preparation

The [fictional example](../backend/ml/fixtures/fictional_manifest.json) is for software testing only: its labels are invented, not verified provenance. The separate `ml.manifest_audit` module does not modify the existing binary baseline, infer provenance, train, download, or integrate with any API. Each in-memory row contains:

| Field | Contract |
| --- | --- |
| `dataset_id`, `original_record_id` | Nonempty stable IDs; their normalized pair must be unique. Never use personal identifiers. |
| `source_url` | HTTPS source URL without credentials; access and rights are not verified by the module. |
| `license_status` | `approved`, `conditional`, `blocked`, or `unverified`; a recorded value is **not** an authorization check. |
| `provenance_group`, `related_groups` | Nonempty globally namespaced group and list of additional group IDs for source document, author, prompt family, revisions, variants or other known relationships. Same identifiers connect transitively across datasets; namespace deliberately, and use the same ID for known shared origin. Unknown links must not be invented. |
| `source_domain`, `model_id` | Nonempty source-domain string; model/version string if documented, otherwise explicit `null`. |
| `label` | Exactly `human`, `ai`, `mixed`, or `unknown`; no automatic binary conversion. |
| `text`, `text_hash` | Local text needed for the audit, and lowercase SHA-256 of UTF-8 NFKC/casefold/word-token normalized text (`ml.dataset.normalize`). This is a normalized duplicate hash, not a hash of original bytes. |
| `split` | Explicit `null` for all rows before planning, or `train`, `validation`, `test` for all rows after planning. |
| `transformations` | List of nonempty descriptions; empty list means none recorded, not proof none occurred. |

Example, from `backend`, using only the fictional file:

```powershell
python -c "import json; from ml.manifest_audit import plan_splits, audit_manifest; r=json.load(open('ml/fixtures/fictional_manifest.json', encoding='utf-8')); print(audit_manifest(plan_splits(r)))"
```

`validate_manifest` checks fields, normalized hashes and inconsistent labels for identical normalized text. `duplicate_report` returns index pairs (including cross-split flags), not text. `audit_manifest` checks existing assignments; `plan_splits` deterministically sorts connected components by a seed and stable IDs, assigning approximately one fifth each to test and validation by component count. Known provenance links and detected exact/near duplicates are connected transitively. It requires at least three components and fails rather than splitting one; it does **not** ensure label balance, representativeness, sufficient sample sizes, or authorization. Review assignments, label counts, source concentration and all flagged pairs before use. Record the seed and manifest version; adding records or changing relationships can alter assignments. Freeze a separately governed evaluation set before experimentation.

Near matching uses normalized character similarity and shared ten-word passages; it may miss paraphrases, translations, short similarities, unknown relationships and source overlap, and can overmerge boilerplate. Pairwise work is quadratic and unsuitable for unbounded large corpora; use small approved batches and a separately reviewed scalable approach for larger data. Hashes, IDs, group memberships and audit outputs can be sensitive or linkable; hashes of short text are vulnerable to guessing and are not anonymization. Do not print or commit real text, manifests, hashes or audit outputs. Use access-controlled storage and the ignored `backend/ml/private_data/` or `backend/ml/artifacts/` only as convenience, not as access control.

## Day 15 decision

The existing tiny fictional smoke fixture can be used solely for local software smoke tests, with its simulated labels and no real-world claims. The new fictional manifest is likewise a format test, not training evidence. Third-party data remains blocked until licensing, source rights, consent/privacy, provenance and independent grouping are documented and approved for the specific purpose. A future binary experiment must explicitly exclude or separately analyze mixed/unknown cases, never silently relabel them. Do not replace or connect the experimental model, change its always-inconclusive output, or expose local research routes as a result of this preparation.
