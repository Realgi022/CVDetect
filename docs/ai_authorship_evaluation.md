# Offline AI-authorship evaluation protocol

**Research only. The current classifier remains unvalidated and always inconclusive in the isolated local server.** This framework does not train, fetch data, run inference, modify the app, or establish authorship. The included command uses only fictional texts, invented labels and manually fabricated predictions/scores—not the classifier. Its reports say **SYNTHETIC SOFTWARE TEST ONLY — NOT REAL-WORLD MODEL VALIDATION.**

## Running the fictional software test

From `backend` in the project's Python environment (install both requirements files as described in the README):

```powershell
python -m ml.research_evaluation --format json
python -m ml.research_evaluation --format markdown --thresholds 0 0.1 0.2
```

Output goes to stdout; the command writes no files. Redirect only fictional reports if needed, for example `python -m ml.research_evaluation --format json > ml/artifacts/fictional-report.json` after creating the ignored directory. Do not publish or commit reports, hashes or sensitive metadata from real data. The JSON and Markdown include source identity and status, model ID, seed, thresholds, class counts, confusion matrix, metrics, domains, audit summary and limitations. Results are fractions, not probabilities of authorship. The fictional model identifier is a stub; no trained model is used.

## Definitions and denominators

Ground truth has four explicit values: `human`, `ai`, `mixed`, and `unknown`; predictions have `human`, `ai`, and `inconclusive`. Only human/AI-labeled rows enter the binary matrix. These labels must be supported by independently reviewed provenance; the software cannot verify it. Fictional labels are invented. Mixed/unknown counts and prediction distributions are reported separately, not treated as binary errors or correct predictions.

The two-by-two matrix contains only **classified** eligible rows; its rows are actual human/AI and columns are predicted human/AI. Abstentions by actual class and total sample counts are separate. With AI as positive: TP = actual AI predicted AI, TN = actual human predicted human, FP = actual human predicted AI, FN = actual AI predicted human. For each class, precision is correct predictions for that class divided by all classified predictions of that class; recall is correct predictions divided by classified actual examples of that class. F1 is `2 TP / (2 TP + FP + FN)` with the class of interest as positive. Balanced accuracy is the mean of classified human recall and classified AI recall and is undefined if either is undefined.

- Human false-positive rate is reported both as FP / **all** eligible human-labeled examples (including abstentions) and FP / classified human-labeled examples. AI false-negative rate is analogously FN / all AI-labeled examples and FN / classified AI-labeled examples. These describe observed errors, not verified population rates. The all-examples version can fall to zero simply because everything is abstained; always inspect abstentions and coverage.
- Eligible coverage is classified human/AI examples / all human/AI examples. Eligible abstention rate is abstained human/AI examples / all human/AI examples. Total abstentions also include mixed/unknown.
- Selective accuracy is correct classified eligible predictions / all classified eligible predictions; selective error is incorrect classified eligible predictions / all classified eligible predictions. Undefined denominators return JSON `null`, never an invented zero. Per-domain metrics require at least the configured minimum eligible count (default 10) and both human and AI labels; otherwise only counts and a suppression reason are shown. Even meeting this mechanical minimum does not establish statistical adequacy.

Accuracy alone obscures class imbalance, false accusations, abstentions and failure on particular domains or groups. A false positive can unfairly stigmatize an applicant; report false positives and uncertainty alongside false negatives, sample sizes and coverage. CVs differ from essays, news and online answers in length, format, editing and purpose. Independent consented, provenance-verified CV-specific evaluation across relevant populations and shifts is necessary for research, but would not prove authorship or justify hiring decisions. See the [collection protocol](../backend/ml/DATASET_PROTOCOL.md) and [decision record](../backend/ml/RESEARCH_DECISION.md).

## Abstention and leakage controls

For supplied model predictions and raw decision scores, abstain when `abs(score) <= threshold`, including equality and zero. Otherwise retain the supplied predicted class, so the caller must respect the actual classifier class order; an already inconclusive prediction stays inconclusive. Decision scores are uncalibrated margins, **not AI-authorship probabilities**. Validation sweeps show coverage and selective error at each threshold without choosing a winner. A final test call accepts exactly one threshold: it must have been fixed using independent validation data before the test was inspected. The tool cannot verify when or how a caller chose that threshold; repeated test calls or manual selection on test results contaminate the holdout.

`evaluate_experiment` first calls Day 14's `audit_manifest` on the **complete** train/validation/test manifest. It rejects missing provenance fields, invalid or missing partitions, shared provenance groups and cross-split normalized exact or possible near-duplicates. Within-split near matches are counted as warnings; inspect them independently. The audit trusts supplied IDs, relationships and labels. Heuristic matching can miss paraphrases, translations, undocumented links and prior exposure; passing cannot prove independence. Pairwise comparison is quadratic and intended for small batches. The model ID and seed are recorded metadata, not proof that model training was reproducible or independent. If the model was trained on outside data, separately audit its source lineage and held-out exposure.

## Future approved inputs

MAGE, HC3 and TXD-22 remain **blocked** until licensing, source rights, consent/privacy and provenance review are complete; none is downloaded by this tool. Follow the [dataset research note](ai_authorship_dataset_research.md) and manifest schema. For a future separately approved study, build a complete manifest with assigned independent train/validation/test groups and supply a list of `{dataset_id, original_record_id, prediction, score}` for every row in the requested evaluation split. Call `evaluate_experiment` with the full manifest, those outputs, `split`, `thresholds`, `model_id`, `seed`, and `evidence_status`. Non-synthetic reports require each record's license status to be marked `approved`, but this is only a metadata check, **not** proof of legal permission, consent, correct provenance or authorization. Outputs must uniquely match the split; never use a test sweep. The CLI intentionally accepts no third-party dataset path. A separate approved workflow must handle secure data access, review, model provenance and retention.

The framework does not promote results to a public interface. Mixed/unknown rows should remain separately analyzed rather than silently removed from the overall study narrative or converted to binary labels. The research server remains loopback-only with its opt-ins and security controls unchanged.
