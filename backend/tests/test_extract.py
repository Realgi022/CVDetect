from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pymupdf
import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import MAX_FILE_SIZE, app

client = TestClient(app)


def pdf(text="Hello CV", encrypted=False):
    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    options = {"encryption": pymupdf.PDF_ENCRYPT_AES_256, "owner_pw": "owner", "user_pw": "secret"} if encrypted else {}
    data = doc.tobytes(**options)
    doc.close()
    return data


def docx(text="Hello CV"):
    doc = Document()
    doc.add_paragraph(text)
    doc.add_paragraph("Second paragraph")
    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def send(name, data):
    return client.post("/api/cv/extract", files={"file": (name, data, "application/octet-stream")})


@pytest.mark.parametrize("name,data", [("cv.pdf", pdf()), ("cv.docx", docx())])
def test_valid(name, data):
    response = send(name, data)
    assert response.status_code == 200
    result = response.json()
    assert result["filename"] == name
    assert result["file_type"] == name.split(".")[-1]
    assert "Hello CV" in result["extracted_text"]
    assert result["character_count"] == len(result["extracted_text"])
    if name.endswith("docx"):
        assert "Hello CV\n\nSecond paragraph" in result["extracted_text"]


@pytest.mark.parametrize("name,data,status,detail", [
    ("cv.txt", b"text", 415, "Unsupported"),
    ("cv.pdf", b"", 422, "empty"),
    ("cv.pdf", b"not a pdf", 422, "corrupt"),
    ("cv.docx", pdf(), 422, "corrupt"),
    ("cv.pdf", pdf(encrypted=True), 422, "Encrypted"),
    ("cv.pdf", pdf(text=""), 422, "No text"),
    ("cv.pdf", b"x" * (MAX_FILE_SIZE + 1), 413, "5 MB"),
    ("cv.pdf", b"x" * (MAX_FILE_SIZE + 70_000), 413, "5 MB"),
])
def test_invalid(name, data, status, detail):
    response = send(name, data)
    assert response.status_code == status
    assert detail in response.json()["detail"]


def test_zip_bomb_limit():
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * (21 * 1024 * 1024))
    response = send("cv.docx", out.getvalue())
    assert response.status_code == 422
    assert "decompression" in response.json()["detail"]


def test_filename_path_removed():
    assert send("../../person.pdf", pdf()).json()["filename"] == "person.pdf"


def test_missing_and_extra_files():
    assert client.post("/api/cv/extract", json={}).status_code == 400
    assert client.post("/api/cv/extract", files={"other": ("cv.pdf", pdf())}).status_code == 400
    assert client.post("/api/cv/extract", files=[("file", ("a.pdf", pdf())), ("file", ("b.pdf", pdf()))]).status_code == 400


def test_health_and_cors():
    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.options("/api/cv/extract", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_empty_docx_error_is_not_pdf_specific():
    document = Document()
    out = BytesIO()
    document.save(out)
    response = send("empty.docx", out.getvalue())
    assert response.status_code == 422
    assert "DOCX" in response.json()["detail"]
    assert "scanned" not in response.json()["detail"]


def test_no_text_pdf_explains_ocr_limitation():
    response = send("scan.pdf", pdf(text=""))
    assert response.status_code == 422
    assert "OCR" in response.json()["detail"]


def test_malformed_docx_does_not_expose_parser_error():
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr("[Content_Types].xml", "not xml")
        archive.writestr("word/document.xml", "not xml")
    response = send("bad.docx", out.getvalue())
    assert response.status_code == 422
    assert response.json()["detail"] == "The document is corrupt or has an invalid structure."
