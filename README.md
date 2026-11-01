# CVDetect

CVDetect extracts text from uploaded PDF and DOCX CVs, previews it, and offers explainable rule-based quality guidance. An isolated offline AI-writing classification experiment exists for research only; there is no detection feature in the API or dashboard, and it cannot reliably determine authorship.

## Requirements

- Windows, PowerShell, Python 3.14 (also supports recent Python 3 versions)
- Node.js 20.19+ or 22.12+ and npm

The dependency ranges include Python 3.14-compatible PyMuPDF and python-docx; installation and tests were run on Python 3.14.7 (PyMuPDF 1.28.2, python-docx 1.2.0). The frontend uses Vite, React, TypeScript and Tailwind CSS.

## Run locally

Open two PowerShell terminals in the repository root.

**Backend:**

```powershell
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

If script activation is blocked, use `.\.venv\Scripts\python.exe` in place of `python` in the commands above, without activating the environment.

**Frontend:**

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, choose or drop a PDF or DOCX, inspect the extracted text, and select **Analyze CV**. Analysis uploads the same file again. The header reports backend health and refreshes every 15 seconds. To use another backend URL, set `$env:VITE_API_URL = "http://localhost:8000"` before `npm run dev`. Restart Vite after changing it. CORS permits only the default local Vite origins (`localhost:5173` and `127.0.0.1:5173`); explicitly configure trusted origins in `backend/app/main.py` before deployment.

## Test

Install both `requirements.txt` and `ml/requirements.txt` to run the complete backend suite. From `backend`, run `python -m pytest -q`. From `frontend`, run `npm run build`. With the backend running, `Invoke-RestMethod http://localhost:8000/api/health` should return `status : ok`. Stop the backend and wait up to 15 seconds to see the frontend report it offline. The ML dependencies are not required to run the API itself.

## Extraction API

Send one multipart field named `file` to `POST /api/cv/extract`. For example, in PowerShell (use a local test file; the response contains its text):

```powershell
curl.exe -X POST -F "file=@C:\path\to\cv.pdf" http://localhost:8000/api/cv/extract
```

The JSON response contains `filename`, `file_type` (`pdf` or `docx`), `character_count`, and `extracted_text`. Errors have a `detail` message: unsupported types return 415, oversized uploads 413, malformed requests 400, and unreadable or empty documents 422. The maximum file size is 5 MiB (5,242,880 bytes); multipart framing is limited separately. PDF files are limited to 200 pages and extracted text to 2 million characters; DOCX archives are limited to 2,000 entries and 20 MiB uncompressed.

## Analysis API and scoring

`POST /api/cv/analyze` accepts the same multipart `file`, limits, and errors as extraction:

```powershell
curl.exe -X POST -F "file=@C:\path\to\cv.docx" http://localhost:8000/api/cv/analyze
```

The response has `overall_score`, `categories` (each with a score and calculation explanation), `strengths`, `weaknesses`, `recommendations`, and `method`. Scores are heuristic guidance, **not hiring suitability or ATS certification**. The overall score is the rounded weighted sum of the rounded category scores:

- **Structure (30%):** 30 points for a recognized education heading, 40 for experience or projects, 20 for skills and 10 for an optional summary. Projects count equally with experience, including for students.
- **Experience/projects (30%):** explicit bullets under those headings earn 20 points if present, plus up to 40 each for the fraction starting with a recognized action verb and the fraction with at least six words (a length heuristic, not proof of an achievement). Recognizable numerical outcomes are counted but never affect the score; they are not verified. Qualitative outcomes matter too; never invent metrics.
- **Skills (20%):** 40 points for a heading, 40 for content and 20 for separated items or multiple lines. No specific skill is required or verified.
- **Readability (20%):** percentage of content lines under recognized headings containing 1–40 words; no recognized content scores zero. This is a simple length check, not grammar or meaning analysis.

Heading matching is case-insensitive and uses a fixed list of common variations, with optional inline content after a colon. Bullet markers include common symbols and numbered lists; an immediately following lowercase line after an unfinished bullet is treated as a possible continuation. PDF line breaks and common DOCX formatted lists are preserved where possible. Some layouts, custom lists, uppercase wrapped lines, multi-column reading order, missing glyphs, and unrecognized headings or verbs will still be missed or misread; unrecognized content is not evidence that it is absent. Numbered lists in a recognized practical section may be mistaken for bullets. These are English-oriented presentation heuristics, not validation of achievements. Synthetic fixtures cover five profiles but do not establish accuracy or fairness on real CVs.

The rules do not intentionally score demographics, names, school prestige, or contact details; recognizable contact lines and labeled personal fields are excluded. Unusual layouts or unlabeled personal information may still be treated as content, so complete independence from personal details cannot be guaranteed. The rules cannot verify claims, measure ability, infer missing facts, or understand all languages and layouts. Section recognition and line/bullet boundaries can be lost during extraction; scores may therefore underestimate a CV. Review the preview and interpret recommendations in context, not as requirements.

## Privacy and limitations

Documents are sent to the configured backend, processed in memory, and not saved by the application. The selected file, extracted text and analysis are held in page state until replaced or the page is closed/reloaded, not browser storage. Avoid sharing the response or running infrastructure that logs request or response bodies. Filenames are reduced to their basename; neither filenames nor document contents are intentionally logged by the application.

Scanned or image-only PDFs are not supported (no OCR); empty, encrypted, corrupt and unsupported documents are rejected. Extraction may not preserve layout, reading order, headers, text boxes or all complex DOCX content. Limits reduce resource risks but do not provide process isolation or guarantee protection from malicious parser inputs; this local development service is not hardened for public deployment. No AI analysis is performed by the application.

## Offline experimental ML baseline

`backend/ml` is a standalone research smoke test, **not a reliable detector** and not connected to the service or dashboard. It trains an in-memory TF-IDF / logistic-regression pipeline on a fixed training partition, evaluates held-out records, and prints class counts, group counts, confusion matrix (rows actual, columns predicted; human then ai), precision, recall, F1 and the human-to-AI false-positive rate. The vectorizer is fitted on training data only. The experiment does not save or load models; never load untrusted pickle or joblib files, which can execute code.

From `backend` in the existing virtual environment:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r ml/requirements.txt
python -m pytest -q
python -m ml.run
python -m ml.challenge
python -m ml.error_analysis
```

Optionally pass a local JSON path to `python -m ml.run path/to/data.json`. The format is a JSON array of objects with nonempty strings `text`, `label` (`human` or `ai`), `source_id`, `document_group`, and `generator_or_author_source`. Optional `split` is `train` or `test` and must be supplied for all records or none. Identifiers must consistently represent original sources and related documents; record reliable provenance, collection consent, transformations, and generators/authors before any real research. With no explicit split, the code uses a fixed-seed group split across connected source/document identifiers; both partitions must contain both classes or the run fails rather than silently resampling. Reported counts cover records and unique identifiers, not independent authors.

The included `ml/fixtures/synthetic_smoke.json` is entirely fictional, with **simulated, unverified labels**, not known human-versus-model provenance. Its deliberately contrasting styles and tiny fixed split may yield flattering numbers; these are software smoke-test outputs only, not evidence of detection accuracy, generalization, or fairness. Duplicate normalized texts are rejected, as are cross-split overlapping source/document identifiers, highly similar texts, identical long lines, or matching ten-word passages. This conservative check can reject common boilerplate and cannot detect every paraphrase or incorrect provenance claim. Independently audit near-duplicates and source relationships before evaluation; do not use personal CVs here. If authorized data is ever used in a separate study, keep it outside Git (the ignored `backend/ml/private_data/` is provided, but ignore rules are not access control), with appropriate consent and retention controls. Never commit sensitive datasets or artifacts.

`python -m ml.challenge` trains the unchanged baseline solely on the fixed smoke training partition and reports a separate diagnostic on `ml/fixtures/fictional_challenge.json`; neither the challenge nor its rewrites are used for fitting or hyperparameter selection. It reports a confusion matrix, per-class metrics and human-label false-positive rate overall and by category, followed by paired punctuation, capitalization, formatting and rewrite checks. Category samples are only two each, so those numbers are descriptive examples, not meaningful group estimates. Transformations and rewrites are related to their original source IDs and are not counted as independent samples. Removing punctuation can also join words; uppercase and whitespace checks reflect this vectorizer's preprocessing, not general robustness. See [dataset audit](backend/ml/DATASET_AUDIT.md) for provenance, counts, shortcut analysis, duplicate-check limitations and paired examples.

`python -m ml.error_analysis` reports fictional error IDs and categories without full text, training-feature associations, and research-only abstention at predefined absolute decision-score margins 0, 0.05, 0.1 and 0.2. Optionally specify, for example, `python -m ml.error_analysis --thresholds 0 0.1 0.2`. A score exactly on the margin is abstained, including zero at margin zero. Scores are uncalibrated decision values, **not probabilities of authorship**; raw per-document scores are not printed. Coverage and selective accuracy use classified examples only, while the report also counts total and abstained human-labeled examples. Do not choose a deployment threshold using the challenge: abstention does not cure poor generalization, and an apparently lower conditional false-positive rate can hide excluded human examples. The command is restricted to fictional fixtures; its feature tokens would not be safe to publish from private text.

See the [future dataset protocol](backend/ml/DATASET_PROTOCOL.md) and [research decision and proposed evaluation gates](backend/ml/RESEARCH_DECISION.md). These are plans, not evidence of real-world detection performance.

**Deployment decision: no-go.** Fictional labels, tiny samples and overlapping human/machine styles cannot establish real-world accuracy or fairness; the experiment must not be used for applicant decisions. A future study would need independently collected, consented and provenance-verified writing with documented model versions, prompts, editing and mixed assistance, privacy and retention controls, representative populations and languages, source-separated independent tests, predefined error and subgroup thresholds, external replication, and documented human review and appeals. Only consider a go decision after independent validation against prespecified safety and fairness criteria, legal and ethical review, and monitoring under shift; otherwise remain no-go. Even then, do not claim authorship is proven or automate hiring decisions. Any future research interface should allow an inconclusive/abstention outcome rather than force uncertain cases into binary labels, with abstention thresholds validated independently—not on this challenge set.

Future evaluation would require appropriately consented, representative human-written, AI-generated, and mixed/edited samples, genuinely independent held-out tests across languages, genres, document lengths, accessibility needs and applicant groups, and monitoring of false-positive and false-negative rates under distribution shift. Short CVs and edited or formulaic writing are especially difficult; false accusations can harm applicants, including non-native English speakers. Detection cannot reliably establish authorship: human and machine writing overlap, and editing or assistance blurs any boundary. Model outputs must not be presented as probabilities a CV was AI-written without independent calibration and validation on the intended population and use case; even calibrated scores would not prove authorship or justify automated hiring decisions.

## Structure

- `backend/app/main.py`: FastAPI routes, bounded multipart upload and local CORS policy.
- `backend/app/extraction.py`: in-memory document validation and extraction.
- `backend/app/analysis.py`: pure, rule-based quality analysis.
- `backend/tests/test_extract.py`: API and extraction tests.
- `backend/tests/test_analysis.py`: analysis and upload validation tests.
- `backend/tests/fixtures/synthetic_cvs.json` and `backend/tests/test_synthetic_profiles.py`: fictional profiles and deterministic validation checks.
- `backend/requirements.txt`: Python dependencies.
- `backend/ml/`: isolated experimental baseline, pinned direct ML dependency, fictional smoke data and evaluation; `backend/tests/test_ml.py` tests it.
- `frontend/src/App.tsx`: homepage and connection indicator.
- `frontend/src/health.ts`: backend health request and URL configuration.
- `frontend/src/extract.ts`: extraction API client.
- `frontend/src/analyze.ts` and `frontend/src/Dashboard.tsx`: analysis API client and report display.
- `frontend/src/style.css`: Tailwind entry point and base styles.
- `frontend/vite.config.ts`: React and Tailwind Vite plugins.
- `.gitignore`: dependency, environment, build, cache and document exclusions.

There is no database, authentication, external AI API, or paid service.
