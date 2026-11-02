# Offline detector comparison — Day 24

This is research only, never a hiring tool or proof of authorship. No pretrained weights have been downloaded or evaluated. Model-card information below was inspected on 2 November 2026; check the linked cards, their license texts, dependencies and provenance again before use. Model licenses do not by themselves establish rights to training data or evaluation examples.

| Model | License and size | Languages and input | Main limitation |
|---|---|---|---|
| [Fakespot RoBERTa AI text detector](https://huggingface.co/fakespot-ai/roberta-base-ai-text-detection-v1) | Apache-2.0; 124.6M FP32 parameters, approximately 499 MB weights | English; RoBERTa supports 512 tokens including special tokens | Not validated for CVs. Card says longer texts generally perform better and recommends `clean_text`; this harness uses raw text instead and does not run repository code. Training sources and contamination need independent review. |
| [OpenAI GPT-2 output detector, base](https://huggingface.co/openai-community/roberta-base-openai-detector) | MIT; 125.2M FP32 parameters, approximately 501 MB weights | English; 512 tokens including special tokens | Fine-tuned on GPT-2 output and WebText; not representative of modern generators or CVs. Card explicitly cautions against standalone detection. |
| [Oxidane TMR detector](https://huggingface.co/Oxidane/tmr-ai-text-detector) | MIT; 124.6M FP32 parameters, approximately 499 MB weights | English; card uses 512 tokens | Model-card RAID results are not CV results; it warns about short and out-of-distribution text. Independent training-data and benchmark-contamination review is needed. |

All three can theoretically run locally on CPU via PyTorch, Transformers, tokenizers and safetensors; memory exceeds weight size and latency depends heavily on hardware. No CPU speed or memory benchmark has yet been performed. Downloads and installations require network access; they are **not** performed by the harness. Recommended first candidate: **Fakespot**, Apache License 2.0, for its explicitly named human/AI classes and more recent AI-text focus versus the GPT-2 detector. Its suitability, performance and preprocessing effects are unproven. Consider TMR as another research candidate, not as a verified improvement.

## Safety and evaluation protocol

Use the existing `ml.cv_collection` workflow for documented consent, rights/privacy review, CV metadata, grouped train/validation/test splits and leakage auditing. Metadata are attestations, not proof. Independently establish whether candidate pretraining/fine-tuning overlaps the evaluation material. The harness checks baseline training IDs when invoked via its CLI, and audits known cross-split duplicate/provenance links, but cannot detect unrecorded overlap, edits, or external training contamination. Keep the final test set sealed until the comparison protocol and threshold are fixed using validation data. Do not interpret fictional tests as accuracy or select a model from them. There is no retraining or tuning in this tool.

For both models it abstains below 20 Unicode word tokens or above 20,000 characters; the candidate additionally abstains above 512 tokenizer tokens, without silent truncation. These limits are research policy choices, not validated operating points. `mixed` and `unknown` labels are reported as prediction distributions and excluded from binary metrics. The report contains aggregate confusion matrices, precision/recall, false-positive rates, coverage, AUC when both classes are scored, Brier score and reliability-bin summaries, as well as per-document CPU latency summaries. Reliability bins are descriptive and can be misleading when small. Model-specific eligible sets can differ: compare coverage and avoid interpreting their aggregate scores as paired results. The baseline latency includes repeated trusted pickle loading and hash checks; candidate loading is outside inference timing, so timings are not apples-to-apples.

CV-specific tests exercise bullet-like text, short summaries/skills, an illustrative human-edited AI draft, and length/abstention handling. They are software tests, not validation data. No text, scores per record, or identifiers are intentionally printed by the harness. Reports and console capture can still reveal sensitive aggregate information; protect research data and outputs.

The baseline loader uses the existing explicit trust and SHA-256 environment flags. The optional candidate loader accepts an explicitly supplied absolute local model directory, requires `model.safetensors`, disables remote code and network loading, validates the RoBERTa Human/AI mapping, and runs on CPU. Local-only and safetensors reduce risk but do not establish artifact safety. Independently review and trust model, tokenizer, metadata and installed packages. Do not copy arbitrary code from a model repository.

## Commands after explicit approval

Do not run a download until approved. In an isolated research environment, after reviewing packages and their licenses, install CPU-compatible dependencies (these commands download packages):

```powershell
cd C:\Projects\CVDetect\backend
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install transformers safetensors huggingface_hub
```

To download only the candidate files after approval, pin the inspected revision `f9cdb14d1f8b105f597d80fa7b56f20c6ea0e9db`; verify the downloaded files and their origin before use. Dependencies are not locked or tested in this repository, so record their exact installed versions for any comparison:

```powershell
# AFTER explicit approval and installing reviewed dependencies:
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:DAY24_MODEL = 'C:\Users\realg\AppData\Local\Temp\opencode\day24-fakespot'
.\.venv\Scripts\python.exe -c "import os; from huggingface_hub import snapshot_download; snapshot_download(repo_id='fakespot-ai/roberta-base-ai-text-detection-v1', revision='f9cdb14d1f8b105f597d80fa7b56f20c6ea0e9db', local_dir=os.environ['DAY24_MODEL'], allow_patterns=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.json','merges.txt'])"
```

From `backend`, configure the trusted baseline exactly as in `docs/local_research_demo.md`. Supply an existing external `prepared.json` generated by `ml.cv_collection`, then run (stdout is an aggregate report):

```powershell
cd C:\Projects\CVDetect\backend
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.\.venv\Scripts\python.exe -m ml.detector_comparison --manifest 'C:\path\outside\repository\prepared.json' --split validation --evidence unvalidated_research --candidate-dir $env:DAY24_MODEL --threshold 0.5
```

For a fictional prepared manifest use `--evidence synthetic`; for baseline-only omit `--candidate-dir`. This uses the same threshold for both models, fixed before final test. To run the sealed test replace `validation` with `test` only after the protocol has been frozen and independence reviewed. Installation, artifact downloads, real evaluation data, and model replacement have not been authorized or performed.
