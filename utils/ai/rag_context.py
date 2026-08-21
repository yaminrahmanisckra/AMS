"""Lightweight RAG context from teacher-uploaded course files."""
import re

from utils.ai.document_extractor import chunk_text, extract_text_from_file


def _keyword_tokens(*values):
    tokens = set()
    for value in values:
        if not value:
            continue
        if isinstance(value, list):
            for item in value:
                tokens.update(_keyword_tokens(item))
            continue
        if isinstance(value, dict):
            tokens.update(_keyword_tokens(*value.values()))
            continue
        for token in re.findall(r'[a-zA-Z0-9]{3,}', str(value).lower()):
            tokens.add(token)
    return tokens


def _score_chunk(chunk, keywords):
    if not chunk or not keywords:
        return 0
    lower = chunk.lower()
    return sum(1 for kw in keywords if kw in lower)


def ensure_upload_extracted(upload, refresh=False):
    """Populate upload.extracted_text if missing."""
    if not upload:
        return ''
    existing = getattr(upload, 'extracted_text', None)
    if existing and not refresh:
        return existing

    text = extract_text_from_file(upload.file_path, upload.file_type)
    if hasattr(upload, 'extracted_text'):
        upload.extracted_text = text or None
    return text or ''


def build_rag_context(session, course_data=None, uploads=None, max_snippets=3, max_chars=2400):
    """
    Rank uploaded file chunks by overlap with course topics and return top snippets.
  uploads: iterable of CourseFileUpload rows.
    """
    keywords = _keyword_tokens(
        getattr(session, 'course_code', None),
        getattr(session, 'course_name', None),
        getattr(course_data, 'rationale', None) if course_data else None,
        getattr(course_data, 'content_section_a', None) if course_data else None,
        getattr(course_data, 'content_section_b', None) if course_data else None,
    )

    ranked = []
    for upload in uploads or []:
        text = ensure_upload_extracted(upload)
        if not text:
            continue
        for chunk in chunk_text(text):
            ranked.append({
                'score': _score_chunk(chunk, keywords),
                'file_name': upload.file_name,
                'file_category': getattr(upload, 'file_category', None),
                'excerpt': chunk[:1200],
            })

    if not ranked:
        return {'snippets': [], 'source_count': 0}

    ranked.sort(key=lambda row: row['score'], reverse=True)
    if ranked[0]['score'] == 0:
        ranked = ranked[:max_snippets]
    else:
        ranked = [row for row in ranked if row['score'] > 0][:max_snippets] or ranked[:max_snippets]

    snippets = []
    total_chars = 0
    for row in ranked:
        excerpt = row['excerpt']
        if total_chars + len(excerpt) > max_chars:
            break
        snippets.append({
            'file_name': row['file_name'],
            'file_category': row['file_category'],
            'excerpt': excerpt,
        })
        total_chars += len(excerpt)

    return {
        'snippets': snippets,
        'source_count': len(uploads or []),
    }
