"""Course Q&A AI drafts using Answer Guideline + law / learning resources."""
import json
import re

from utils.ai.client import generate_text_with_meta
from utils.ai.question_bank import get_active_guideline_text_cached


MARKS_ATTENDANCE_RE = re.compile(
    r'\b(mark|marks|grade|result|attendance|present|absent|nambar|নম্বর|মার্ক|উপস্থিত|অনুপস্থিত|গ্রেড)\b',
    re.I,
)

AI_PREFIX = 'এআই সহায়তায়'
_GUIDELINE_CHAR_LIMIT = 5500


def looks_like_marks_or_attendance(text):
    return bool(MARKS_ATTENDANCE_RE.search(text or ''))


def clip(text, limit=6000):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit] + '\n…[truncated]'


def _strip_html(text):
    return re.sub(r'<[^>]+>', ' ', text or '').strip()


def _flatten_json_text(value):
    if value is None:
        return ''
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ''
        if stripped[0] in ('{', '['):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
        else:
            return stripped
    if isinstance(value, list):
        return '\n'.join(p for p in (_flatten_json_text(item) for item in value) if p)
    if isinstance(value, dict):
        parts = []
        for key in ('topic', 'description', 'title', 'name', 'text', 'content'):
            if value.get(key):
                parts.append(str(value[key]))
        if not parts:
            for nested in value.values():
                flat = _flatten_json_text(nested)
                if flat:
                    parts.append(flat)
        return '\n'.join(parts)
    return str(value).strip()


def _outline_learning_resources(session_id):
    from blueprints.class_management.models import CourseOutline

    outline = CourseOutline.query.filter_by(session_id=session_id).first()
    if not outline:
        return ''
    parts = [
        _flatten_json_text(outline.textbooks),
        _flatten_json_text(outline.reference_books),
        _flatten_json_text(outline.other_resources),
    ]
    return clip('\n'.join(p for p in parts if p), 1500)


def build_qa_context(session_id):
    """Fast context: cached Answer Guideline + outline book lists (no file OCR)."""
    _gid, guideline_title, guideline_text = get_active_guideline_text_cached()
    resources_text = _outline_learning_resources(session_id)

    sections = []
    if guideline_text:
        sections.append(
            f'ANSWER GUIDELINE ({guideline_title or "active"}):\n{clip(guideline_text, _GUIDELINE_CHAR_LIMIT)}'
        )
    if resources_text:
        sections.append(f'LEARNING RESOURCES:\n{resources_text}')

    return {
        'guideline_title': guideline_title,
        'guideline_text': guideline_text or '',
        'resources_text': resources_text,
        'text': '\n\n'.join(sections).strip(),
        'has_guideline': bool(guideline_title),
        'has_guideline_text': bool((guideline_text or '').strip()),
    }



def generate_teacher_reply_from_data(
    *,
    session_id,
    course_code='',
    course_name='',
    thread_subject='',
    target_message_text='',
    thread_messages=None,
    latest_student_text=None,
):
    """Plain-data entry point safe across reset_db_session() during AI calls."""
    target_text = _strip_html(target_message_text or latest_student_text or thread_subject)
    if looks_like_marks_or_attendance(target_text):
        raise ValueError('marks_or_attendance')

    ctx = build_qa_context(session_id)
    if not ctx['has_guideline']:
        raise ValueError('no_guideline')
    if not ctx['has_guideline_text']:
        raise ValueError('guideline_not_extracted')

    history = []
    for msg in thread_messages or []:
        role = 'Teacher' if msg.get('sender_role') == 'teacher' else 'Student'
        body = _strip_html(msg.get('body') or '')
        if body:
            history.append(f'{role}: {clip(body, 500)}')

    system_prompt = (
        'You are a Bangladesh law teacher assistant. Draft a concise exam-style reply.\n'
        'Follow the Answer Guideline format (IRAC, problem question, short note, etc.) when it fits.\n'
        'Cite relevant Bangladesh Acts/sections and leading cases. Use standard legal knowledge.\n'
        'Never discuss marks, grades, or attendance. Match the student\'s language (Bangla or English).\n'
        'Under 220 words. Markdown only (headings, lists, bold). No HTML.'
    )
    user_prompt = (
        f'Course: {course_code or ""} {course_name or ""}\n'
        f'Thread subject: {thread_subject}\n\n'
        f'REPLY TO THIS MESSAGE:\n{clip(target_text, 1200)}\n\n'
        f'{ctx["text"]}\n\n'
        f'Earlier messages (context only):\n' + ('\n'.join(history[-6:]) if history else '(none)') + '\n\n'
        'Teacher reply:'
    )
    meta = generate_text_with_meta(
        system_prompt,
        user_prompt,
        max_tokens=900,
        timeout=75,
        max_retries=0,
    )
    text = (meta.get('text') or '').strip()
    if not text:
        raise ValueError('empty_reply')
    return text, ctx


def generate_teacher_reply(session, thread, latest_student_text):
    """Snapshot ORM fields before any long AI call detaches the SQLAlchemy session."""
    sorted_msgs = sorted(thread.messages or [], key=lambda m: m.created_at or 0)
    target_msg = None
    for msg in reversed(sorted_msgs):
        if (msg.body or '').strip():
            target_msg = msg
            break
    target_index = sorted_msgs.index(target_msg) if target_msg else -1
    history = [
        {'sender_role': m.sender_role, 'body': m.body or ''}
        for m in (sorted_msgs[:target_index] if target_index > 0 else [])
    ]
    return generate_teacher_reply_from_data(
        session_id=session.id,
        course_code=getattr(session, 'course_code', None) or '',
        course_name=getattr(session, 'course_name', None) or '',
        thread_subject=getattr(thread, 'subject', None) or '',
        target_message_text=latest_student_text or (target_msg.body if target_msg else ''),
        thread_messages=history,
    )
