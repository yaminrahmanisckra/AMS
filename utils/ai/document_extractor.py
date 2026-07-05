"""Extract plain text from uploaded course files."""
import os
import re


def _clean_text(text):
    if not text:
        return ''
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_text_from_file(file_path, file_type=None):
    """Return extracted plain text or empty string on failure."""
    if not file_path or not os.path.isfile(file_path):
        return ''

    ext = (file_type or os.path.splitext(file_path)[1]).lower().lstrip('.')
    try:
        if ext == 'pdf':
            return _extract_pdf(file_path)
        if ext in ('doc', 'docx'):
            return _extract_docx(file_path)
        if ext in ('txt', 'md'):
            return _extract_plain(file_path)
    except Exception:
        return ''
    return ''


def _extract_plain(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as handle:
        return _clean_text(handle.read())


def _extract_pdf(file_path):
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return ''
    reader = PdfReader(file_path)
    parts = []
    for page in reader.pages[:40]:
        parts.append(page.extract_text() or '')
    return _clean_text('\n'.join(parts))


def _extract_docx(file_path):
    try:
        from docx import Document
    except ImportError:
        return ''
    doc = Document(file_path)
    parts = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    return _clean_text('\n'.join(parts))


def chunk_text(text, chunk_size=1200, overlap=150):
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]
