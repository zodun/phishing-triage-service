"""Extract the actual attachment text, failing closed on unreadable pages."""

from io import BytesIO
from pypdf import PdfReader

MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PAGES = 30
MAX_TEXT_CHARS = 100_000


class PDFError(ValueError):
    pass


def extract_pdf_text(data: bytes) -> str:
    if len(data) > MAX_PDF_BYTES:
        raise PDFError("PDF exceeds the 15 MB attachment limit.")
    if not data.lstrip().startswith(b"%PDF-"):
        raise PDFError("The attachment is not a valid PDF.")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise PDFError("This PDF is encrypted. Supply an unlocked copy.")
        if not reader.pages or len(reader.pages) > MAX_PAGES:
            raise PDFError("PDF must contain between 1 and 30 pages.")
        pages = []
        total = 0
        for number, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if not text:
                raise PDFError(f"Page {number} has no readable text. Run OCR or supply a text-based PDF.")
            total += len(text)
            if total > MAX_TEXT_CHARS:
                raise PDFError("PDF text exceeds the 100,000 character limit.")
            pages.append(f"[Page {number}]\n{text}")
        return "\n\n".join(pages)
    except PDFError:
        raise
    except Exception as exc:
        raise PDFError("The PDF could not be read. Supply an intact, unlocked PDF.") from exc
