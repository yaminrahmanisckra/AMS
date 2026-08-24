"""Course Q&A AI drafts grounded in outline + uploaded course files."""
import json
import re

from utils.ai.client import generate_text_with_meta
from utils.ai.rag_context import build_rag_context


MARKS_ATTENDANCE_RE = re.compile(
    r'\b(mark|marks|grade|result|attendance|present|absent|nambar|নম্বর|মার্ক|উপস্থিত|অনুপস্থিত|গ্রেড)\b',
    re.I,
)

AI_PREFIX = 'এআই সহায়তায়'


def looks_like_marks_or_attendance(text):
    return bool(MARKS_ATTENDANCE_RE.search(text or ''))


def clip(text, limit=6000):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit] + '\n…[truncated]'


def _outline_snippets(session):
    from blueprints.class_management.models import CourseOutline

    outline = CourseOutline.query.filter_by(session_id=session.id).first()
    if not outline:
        return ''
    parts = [
        outline.course_summary or '',
        outline.course_objectives or '',
        outline.clo_data or '',
        outline.prerequisites or '',
    ]
    return clip('\n'.join(p for p in parts if p), 4000)


def build_session_rag(session):
    from blueprints.class_management.models import CourseFileUpload
    from blueprints.course_management.models import Course

    course = None
    if getattr(session, 'course_code', None):
        course = Course.query.filter_by(course_code=session.course_code).first()
    uploads = CourseFileUpload.query.filter_by(session_id=session.id).all()
    rag = build_rag_context(session, course_data=course, uploads=uploads, max_snippets=4, max_chars=2800)
    snippets = rag.get('snippets') or []
    file_text = '\n\n'.join(
        f"[{row.get('file_name')}] {row.get('excerpt')}" for row in snippets if row.get('excerpt')
    )
    outline_text = _outline_snippets(session)
    combined = '\n\n'.join(p for p in (outline_text, file_text) if p)
    return {
        'text': combined.strip(),
        'source_count': rag.get('source_count') or 0,
        'has_outline': bool(outline_text),
    }


def generate_teacher_reply(session, thread, latest_student_text):
    rag = build_session_rag(session)
    if looks_like_marks_or_attendance(latest_student_text):
        raise ValueError('marks_or_attendance')
    if not rag['text']:
        raise ValueError('empty_rag')

    history = []
    for msg in sorted(thread.messages or [], key=lambda m: m.created_at or 0):
        role = 'Teacher' if msg.sender_role == 'teacher' else 'Student'
        body = (msg.body or '').strip()
        if body:
            history.append(f'{role}: {clip(body, 800)}')

    system_prompt = (
        'You are a course teacher assistant. Answer from the provided course materials only. '
        'If the materials do not contain the answer, say you will check and reply later. '
        'Never reveal or guess marks, grades, or attendance. Write in the student\'s language '
        '(Bangla or English). Keep the reply short (under 180 words). Do not claim to be human.'
    )
    user_prompt = (
        f'Course: {session.course_code or ""} {session.course_name or ""}\n'
        f'Thread subject: {thread.subject}\n\n'
        f'COURSE MATERIALS:\n{clip(rag["text"])}\n\n'
        f'THREAD:\n' + '\n'.join(history[-8:]) + '\n\n'
        f'Write the teacher reply only (no preamble).'
    )
    meta = generate_text_with_meta(system_prompt, user_prompt, max_tokens=700)
    text = (meta.get('text') or '').strip()
    if not text:
        raise ValueError('empty_reply')
    return text, rag
