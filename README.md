# CVDetect

CVDetect extracts text from uploaded PDF and DOCX CVs and previews it on the current page. CV quality feedback and AI-writing detection are upcoming and are not implemented. AI-writing detection cannot reliably determine authorship.

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

Open http://localhost:5173, choose or drop a PDF or DOCX, and inspect the extracted text. The header reports backend health and refreshes every 15 seconds. To use another backend URL, set `$env:VITE_API_URL = "http://localhost:8000"` before `npm run dev`. Restart Vite after changing it. CORS permits only the default local Vite origins (`localhost:5173` and `127.0.0.1:5173`); explicitly configure trusted origins in `backend/app/main.py` before deployment.

## Test

From `backend`, run `python -m pytest -q`. From `frontend`, run `npm run build`. With the backend running, `Invoke-RestMethod http://localhost:8000/api/health` should return `status : ok`. Stop the backend and wait up to 15 seconds to see the frontend report it offline.

## Extraction API

Send one multipart field named `file` to `POST /api/cv/extract`. For example, in PowerShell (use a local test file; the response contains its text):

```powershell
curl.exe -X POST -F "file=@C:\path\to\cv.pdf" http://localhost:8000/api/cv/extract
```

The JSON response contains `filename`, `file_type` (`pdf` or `docx`), `character_count`, and `extracted_text`. Errors have a `detail` message: unsupported types return 415, oversized uploads 413, malformed requests 400, and unreadable or empty documents 422. The maximum file size is 5 MiB (5,242,880 bytes); multipart framing is limited separately. PDF files are limited to 200 pages and extracted text to 2 million characters; DOCX archives are limited to 2,000 entries and 20 MiB uncompressed.

## Privacy and limitations

Documents are sent to the configured backend, processed in memory, and not saved by the application. Extracted text is returned to the browser and held in page state until replaced or the page is closed/reloaded. Avoid sharing the response or running infrastructure that logs request or response bodies. Filenames are reduced to their basename; neither filenames nor document contents are intentionally logged by the application.

Scanned or image-only PDFs are not supported (no OCR); empty, encrypted, corrupt and unsupported documents are rejected. Extraction may not preserve layout, reading order, headers, text boxes or all complex DOCX content. Limits reduce resource risks but do not provide process isolation or guarantee protection from malicious parser inputs; this local development service is not hardened for public deployment. No AI analysis is performed.

## Structure

- `backend/app/main.py`: FastAPI routes, bounded multipart upload and local CORS policy.
- `backend/app/extraction.py`: in-memory document validation and extraction.
- `backend/tests/test_extract.py`: API and extraction tests.
- `backend/requirements.txt`: Python dependencies.
- `frontend/src/App.tsx`: homepage and connection indicator.
- `frontend/src/health.ts`: backend health request and URL configuration.
- `frontend/src/extract.ts`: extraction API client.
- `frontend/src/style.css`: Tailwind entry point and base styles.
- `frontend/vite.config.ts`: React and Tailwind Vite plugins.
- `.gitignore`: dependency, environment, build, cache and document exclusions.

There is no database, authentication, external AI API, or paid service.
