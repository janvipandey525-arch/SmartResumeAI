"""
Extract plain text from an uploaded resume file (PDF / DOCX / TXT).

Kept dependency-light and defensive: unsupported types and parse failures raise
a ValueError with a clear message the router turns into a 400.
"""
from __future__ import annotations

import io

MAX_BYTES = 5 * 1024 * 1024  # 5 MB cap — resumes are small; reject oversized uploads.


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise ValueError("File too large (max 5 MB).")

    name = (filename or "").lower()

    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")

    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as e:  # noqa: BLE001 - surface a clean message to the client
            raise ValueError(f"Could not read PDF: {e}")

    if name.endswith(".docx"):
        try:
            import docx  # python-docx

            document = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in document.paragraphs)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Could not read DOCX: {e}")

    raise ValueError("Unsupported file type. Upload a .pdf, .docx, or .txt file.")
