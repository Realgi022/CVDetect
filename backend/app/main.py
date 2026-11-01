from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.formparsers import MultiPartParser
from starlette.datastructures import UploadFile

from .extraction import DocumentError, extract_document
from .analysis import analyze_text
from .writing_insights import writing_insights
from .writing_patterns import writing_patterns

app = FastAPI(title="CVDetect API")

# Only the default local Vite development origins are allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


MAX_FILE_SIZE = 5 * 1024 * 1024
# Allow limited multipart headers and framing in addition to the file itself.
MAX_REQUEST_SIZE = MAX_FILE_SIZE + 64 * 1024


@app.post("/api/cv/extract")
async def extract_cv(request: Request, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return await extract_upload(request)


@app.post("/api/cv/analyze")
async def analyze_cv(request: Request, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    document = await extract_upload(request)
    text = document["extracted_text"]
    report = analyze_text(text)
    report["writing_insights"] = writing_insights(text)
    report["writing_patterns"] = writing_patterns(text)
    return report


async def extract_upload(request: Request) -> dict:
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise HTTPException(400, "Expected multipart form data containing one file.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_REQUEST_SIZE:
            raise HTTPException(413, "Upload exceeds the 5 MB limit.")

    async def stream():
        yield bytes(body)

    # The bounded request stays in memory, including Starlette's upload spool.
    class MemoryParser(MultiPartParser):
        spool_max_size = MAX_REQUEST_SIZE + 1

    try:
        form = await MemoryParser(request.headers, stream(), max_files=1, max_fields=1).parse()
    except Exception:
        raise HTTPException(400, "Invalid multipart upload; provide one file.") from None
    try:
        items = form.multi_items()
        if len(items) != 1 or items[0][0] != "file" or not isinstance(items[0][1], UploadFile):
            raise HTTPException(400, "Provide exactly one file named 'file'.")
        upload = items[0][1]
        data = await upload.read(MAX_FILE_SIZE + 1)
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(413, "Upload exceeds the 5 MB limit.")
        try:
            return extract_document(upload.filename or "", data)
        except DocumentError as exc:
            raise HTTPException(exc.status, exc.message) from None
    finally:
        await form.close()
