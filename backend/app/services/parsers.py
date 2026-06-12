import io
import logging

logger = logging.getLogger(__name__)


def parse_upload(content: bytes, content_type: str | None, filename: str) -> str:
    """
    Extract plain text from uploaded files (PDF, DOCX, TXT).
    
    Args:
        content: File content as bytes
        content_type: MIME type of the file
        filename: Name of the file
        
    Returns:
        Extracted text content
    """
    ct = (content_type or "").lower()
    fn = (filename or "").lower()

    if "pdf" in ct or fn.endswith(".pdf"):
        return _parse_pdf(content)
    if "word" in ct or fn.endswith(".docx") or fn.endswith(".doc"):
        return _parse_docx(content)
    if ct.startswith("text/") or fn.endswith(".txt") or fn.endswith(".md"):
        return content.decode("utf-8", errors="replace")

    try:
        return _parse_docx(content)
    except Exception:
        return content.decode("utf-8", errors="replace")


def _parse_pdf(content: bytes) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        content: PDF file content as bytes
        
    Returns:
        Extracted text content
        
    Raises:
        Exception: If PDF parsing fails
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        parts = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                parts.append(f"--- Page {i + 1} ---\n{text}")
        return "\n\n".join(parts)
    except Exception as exc:
        logger.warning("PDF parse failed: %s", exc)
        return content.decode("utf-8", errors="replace")


def _parse_docx(content: bytes) -> str:
    """
    Extract text from a DOCX file.
    
    Args:
        content: DOCX file content as bytes
        
    Returns:
        Extracted text content
        
    Raises:
        Exception: If DOCX parsing fails
    """
    try:
        from docx import Document

        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as exc:
        logger.warning("DOCX parse failed: %s", exc)
        raise
