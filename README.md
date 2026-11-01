# CVDetect

CVDetect extracts text from uploaded PDF and DOCX CVs, previews it, and offers explainable rule-based quality guidance. AI-writing detection is a future experimental feature, not implemented; it cannot reliably determine authorship.

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

From `backend`, run `python -m pytest -q`. From `frontend`, run `npm run build`. With the backend running, `Invoke-RestMethod http://localhost:8000/api/health` should return `status : ok`. Stop the backend and wait up to 15 seconds to see the frontend report it offline.

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

Heading matching is case-insensitive and uses a fixed list of common variations, with optional inline content after a colon. Bullet markers include common symbols and numbered lists; a lowercase line following an unfinished bullet is treated as a possible continuation. PDF line breaks and common DOCX formatted lists are preserved where possible. Some layouts, custom lists, wrapped lines, and headings will still be missed or misread; unrecognized content is not evidence that it is absent. These are English-oriented presentation heuristics, not validation of achievements.

The rules do not intentionally score demographics, names, school prestige, or contact details; recognizable contact lines and labeled personal fields are excluded. Unusual layouts or unlabeled personal information may still be treated as content, so complete independence from personal details cannot be guaranteed. The rules cannot verify claims, measure ability, infer missing facts, or understand all languages and layouts. Section recognition and line/bullet boundaries can be lost during extraction; scores may therefore underestimate a CV. Review the preview and interpret recommendations in context, not as requirements.

## Privacy and limitations

Documents are sent to the configured backend, processed in memory, and not saved by the application. The selected file, extracted text and analysis are held in page state until replaced or the page is closed/reloaded, not browser storage. Avoid sharing the response or running infrastructure that logs request or response bodies. Filenames are reduced to their basename; neither filenames nor document contents are intentionally logged by the application.

Scanned or image-only PDFs are not supported (no OCR); empty, encrypted, corrupt and unsupported documents are rejected. Extraction may not preserve layout, reading order, headers, text boxes or all complex DOCX content. Limits reduce resource risks but do not provide process isolation or guarantee protection from malicious parser inputs; this local development service is not hardened for public deployment. No AI analysis is performed.

## Structure

- `backend/app/main.py`: FastAPI routes, bounded multipart upload and local CORS policy.
- `backend/app/extraction.py`: in-memory document validation and extraction.
- `backend/app/analysis.py`: pure, rule-based quality analysis.
- `backend/tests/test_extract.py`: API and extraction tests.
- `backend/tests/test_analysis.py`: analysis and upload validation tests.
- `backend/requirements.txt`: Python dependencies.
- `frontend/src/App.tsx`: homepage and connection indicator.
- `frontend/src/health.ts`: backend health request and URL configuration.
- `frontend/src/extract.ts`: extraction API client.
- `frontend/src/analyze.ts` and `frontend/src/Dashboard.tsx`: analysis API client and report display.
- `frontend/src/style.css`: Tailwind entry point and base styles.
- `frontend/vite.config.ts`: React and Tailwind Vite plugins.
- `.gitignore`: dependency, environment, build, cache and document exclusions.

There is no database, authentication, external AI API, or paid service.
