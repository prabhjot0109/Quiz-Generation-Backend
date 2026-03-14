from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    combined = "\n".join(page.strip() for page in pages if page.strip()).strip()
    if not combined:
        raise ValueError("PDF did not contain extractable text.")
    return combined
