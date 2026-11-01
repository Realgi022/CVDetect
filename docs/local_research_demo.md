# Local end-to-end research demo

**Fictional software test only.** This prototype extracts a fictional PDF/DOCX in memory and can run an explicitly trusted synthetic research model. It always reports **INCONCLUSIVE**. It is not reliable authorship detection, is not connected to the public React app, and must never be used for hiring or consequential decisions. Use only fictional or expressly authorized test documents; the demo below creates fictional content. Do not upload real CVs or personal data.

## Verify and create a fictional artifact

From the repository root in PowerShell, with backend and ML dependencies installed:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/research_ui.test.cjs
```

In a separate terminal from the repository root:

```powershell
cd frontend
npm run build
```

From `backend`, create a **new**, access-controlled directory outside any Git working tree and generate the existing fictional smoke-test artifact (this command trains only on the bundled fictional fixtures):

```powershell
$out = Join-Path $env:TEMP 'cvdetect-day20-fictional'
New-Item -ItemType Directory -Path $out
Set-Content -Path (Join-Path $out '.gitignore') -Value '*' -Encoding ascii
.\.venv\Scripts\python.exe -m ml.research_training --output-dir $out --seed 42
```

If the directory already contains a test claim or model, select a different new directory; the training command will not overwrite artifacts. The generated report and pickle can contain training-derived information. Keep them private; `.gitignore` is not access control. **Pickle loading can execute arbitrary code.** Use only a model you personally created in a trusted environment. A SHA-256 digest detects byte changes but does **not** prove safety, identity or provenance; neither the report nor this tool independently verifies the model's training history. Never trust a downloaded or unreviewed pickle/joblib file. The research loader only accepts reports marked `synthetic` from the current comparison format, and does not load or train a model on server startup.

## Configure and launch the local server

In that same backend terminal, inspect the files, then explicitly configure the model you trust:

```powershell
Get-ChildItem $out
$model = (Get-ChildItem $out -Filter 'model-*.pkl').FullName
$report = (Get-ChildItem $out -Filter 'report-*.json').FullName
$env:CVDETECT_ENV = 'development'
$env:CVDETECT_EXPERIMENTAL_INFERENCE = '1'
$env:CVDETECT_RESEARCH_TRUSTED_PICKLE = '1'
$env:CVDETECT_RESEARCH_MODEL_PATH = $model
$env:CVDETECT_RESEARCH_MODEL_REPORT = $report
$env:CVDETECT_RESEARCH_MODEL_SHA256 = (Get-FileHash -Algorithm SHA256 $model).Hash.ToLowerInvariant()
.\.venv\Scripts\python.exe -m app.dev_server
```

The server owns a socket bound to `127.0.0.1:8001`, rejects forwarding headers and checks exact Host, Origin, session cookie and CSRF token for both new POST routes. Do not expose it with a proxy, tunnel, public container mapping or port forward. Local protections are not authentication and do not protect against malicious local processes or a compromised browser. No input or output is intentionally stored by the application; browsers, OS, screenshots or external tooling may retain data. Access logs are disabled by this launcher.

## Generate and use a fictional test document

In another PowerShell terminal from `backend`, create a fictional DOCX outside the repository:

```powershell
$env:CVDETECT_FICTIONAL_DOCX = Join-Path $env:TEMP 'cvdetect-fictional-demo.docx'
.\.venv\Scripts\python.exe -c "import os; from docx import Document; d=Document(); d.add_paragraph('Fictional project: mapped stars for an imaginary museum exhibit.'); d.save(os.environ['CVDETECT_FICTIONAL_DOCX'])"
Start-Process 'http://127.0.0.1:8001/research'
```

Select the fictional DOCX, choose **Extract text for preview**, inspect the text, then select **Run trusted artifact diagnostic**. A trusted-artifact error indicates missing opt-in, path, digest, matching synthetic report, or unreadable/unsupported artifact; check configuration and restart. The separate **Run Experimental Analysis** button retains the original in-memory eight-example baseline and does not use the artifact. Both are unvalidated. The displayed decision score is a raw, uncalibrated model value, **not an AI-authorship probability or percentage**; it cannot determine who wrote a CV. False positives can harm applicants. Independent, provenance-verified and consented CV-specific evaluation, subgroup and shift testing, replication, and legal/ethical/privacy review are required before considering public deployment.

Select **Reset and clear preview** to clear the page's preview and result state, then stop the server with Ctrl+C. In the server terminal remove the environment variables:

```powershell
Remove-Item Env:CVDETECT_ENV, Env:CVDETECT_EXPERIMENTAL_INFERENCE, Env:CVDETECT_RESEARCH_TRUSTED_PICKLE, Env:CVDETECT_RESEARCH_MODEL_PATH, Env:CVDETECT_RESEARCH_MODEL_REPORT, Env:CVDETECT_RESEARCH_MODEL_SHA256
```

After reviewing the fictional outputs, remove the specific fictional DOCX and model/report/claim files under the dedicated test directory, then remove its `.gitignore` and the directory if empty. Follow the retention and withdrawal protocol instead for any separately authorized research data. Deleting files does not guarantee removal from backups or physical storage. The normal server must still return 404 for research routes.
