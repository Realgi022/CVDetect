# CVDetect

An early foundation for a CV quality analysis website. Uploads and analysis are **not implemented**; the interface is a preview and no CVs are collected or stored. Experimental AI-writing detection cannot reliably determine authorship and is not implemented.

## Requirements

- Windows, PowerShell, Python 3.14 (also supports recent Python 3 versions)
- Node.js 20.19+ or 22.12+ and npm

FastAPI and Pydantic 2 versions in `backend/requirements.txt` support Python 3.14. The frontend uses Vite, React, TypeScript and Tailwind CSS.

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

Open http://localhost:5173. The header reports the actual backend health; it refreshes every 15 seconds. To use another backend URL, set `$env:VITE_API_URL = "http://localhost:8000"` before `npm run dev`. Restart Vite after changing it. CORS currently permits only the default local Vite origins (`localhost:5173` and `127.0.0.1:5173`); explicitly configure trusted origins in `backend/app/main.py` before any production deployment.

## Test

With the backend running, execute `Invoke-RestMethod http://localhost:8000/api/health` in PowerShell; it should return `status : ok`. Stop the backend and wait up to 15 seconds to see the frontend report it offline; restart it to see the connected status return. The upload button remains disabled. To type-check and build the frontend, run `npm run build` from `frontend`.

## Structure

- `backend/app/main.py`: FastAPI app, local CORS policy and health endpoint.
- `backend/requirements.txt`: Python dependencies.
- `frontend/src/App.tsx`: homepage and connection indicator.
- `frontend/src/health.ts`: backend health request and URL configuration.
- `frontend/src/style.css`: Tailwind entry point and base styles.
- `frontend/vite.config.ts`: React and Tailwind Vite plugins.
- `.gitignore`: dependency, environment, build, cache and document exclusions.

There is no database, authentication, external AI API, or paid service.
