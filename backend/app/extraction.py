"""In-memory, bounded document extraction. Never log document contents."""
import re
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile

import pymupdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

MAX_UNCOMPRESSED = 20 * 1024 * 1024
MAX_TEXT = 2_000_000
MAX_PAGES = 200


class DocumentError(Exception):
    def __init__(self, message: str, status: int = 422):
        self.message = message
        self.status = status


def normalize(text: str) -> str:
    return "\n\n".join("\n".join(" ".join(line.split()) for line in part.splitlines() if line.strip()) for part in re.split(r"\n\s*\n", text) if part.strip())


def extract_document(filename: str, data: bytes) -> dict:
    filename = PurePosixPath(filename.replace("\\", "/")).name
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ("pdf", "docx"):
        raise DocumentError("Unsupported file type. Choose a PDF or DOCX file.", 415)
    if not data:
        raise DocumentError("The document is empty.")
    try:
        text = extract_pdf(data) if extension == "pdf" else extract_docx(data)
    except DocumentError:
        raise
    except Exception:
        raise DocumentError("The document is corrupt or has an invalid structure.") from None
    text = normalize(text)
    if not text:
        if extension == "pdf":
            raise DocumentError("No text found. The PDF may be empty or scanned/image-only; OCR is not supported. Try a text-based PDF or DOCX.")
        raise DocumentError("No text found in the DOCX. Check that it contains selectable text; images and text boxes may not be extracted.")
    if len(text) > MAX_TEXT:
        raise DocumentError("The document contains too much text to process.")
    return {"filename": filename, "file_type": extension, "character_count": len(text), "extracted_text": text}


def extract_pdf(data: bytes) -> str:
    if not data.startswith(b"%PDF-"):
        raise DocumentError("The PDF is corrupt or has an invalid structure.")
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass or doc.is_encrypted:
            raise DocumentError("Encrypted PDFs are not supported.")
        if doc.is_repaired:
            raise DocumentError("The PDF is corrupt or has an invalid structure.")
        if len(doc) > MAX_PAGES:
            raise DocumentError("The PDF exceeds the 200-page limit.")
        parts = []
        size = 0
        for page in doc:
            text = page.get_text("blocks")
            for block in text:
                if block[6] == 0:
                    size += len(block[4])
                    if size > MAX_TEXT:
                        raise DocumentError("The document contains too much text to process.")
                    parts.append(block[4])
        return "\n\n".join(parts)


def extract_docx(data: bytes) -> str:
    if data.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        raise DocumentError("Encrypted or legacy Word documents are not supported. Use an unencrypted DOCX.")
    with ZipFile(BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > MAX_UNCOMPRESSED:
            raise DocumentError("The DOCX exceeds decompression safety limits.")
        if any(e.flag_bits & 1 for e in entries):
            raise DocumentError("Encrypted DOCX files are not supported.")
        names = [e.filename for e in entries]
        if len(names) != len(set(names)) or not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
            raise DocumentError("The DOCX is corrupt or has an invalid structure.")
        if archive.testzip() is not None:
            raise DocumentError("The DOCX is corrupt or has an invalid structure.")
    document = Document(BytesIO(data))
    parts = []
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text
            # Word list markers are often formatting, not part of paragraph.text.
            if text.strip() and not re.match(r"^\s*(?:[•●▪◦‣∙·■□◆►➤\uf0b7]|[-*–—]\s|\(?\d{1,2}[.)]\s)", text) and (block._p.pPr is not None and block._p.pPr.numPr is not None or block.style and block.style.name.lower().startswith(("list bullet", "list number"))):
                text = "• " + text
            parts.append(text)
        elif isinstance(block, Table):
            for row in block.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n\n".join(parts)
