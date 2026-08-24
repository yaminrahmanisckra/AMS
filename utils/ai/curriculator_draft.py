"""AI drafts for Curriculator Part C course entries."""
import json

from utils.ai.client import generate_outline_json_with_meta
from utils.ai.curriculator_context import get_program_plos, resolve_syllabus_document
from utils.ai.outline_parser import extract_json_from_response


def clip(text, limit=8000):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit] + '\n…[truncated]'


def _plos_for_entry(entry):
    part = getattr(entry, 'part', None)
    doc = getattr(part, 'document', None) if part else None
    if doc is None:
        doc = resolve_syllabus_document()
    return get_program_plos(doc) if doc else []


def generate_course_entry_draft(entry, sections=None):
    """Return a proposal content_json fragment for the requested sections."""
    content = entry.get_content_dict() if hasattr(entry, 'get_content_dict') else {}
    wanted = set(sections or ['rationale', 'clos', 'mapping', 'content'])
    plos = _plos_for_entry(entry)

    system_prompt = (
        'You draft curriculum fields for a Bangladeshi university course outline (OBE). '
        'Write in clear academic English. Map CLOs to the given PLO ids only. '
        'Do not invent PLO numbers that are not in the list. Return JSON only.'
    )
    user_prompt = json.dumps({
        'task': 'curriculator_part_c_draft',
        'sections': sorted(wanted),
        'course': {
            'code': entry.course_code,
            'name': entry.course_name,
            'credit': entry.credit,
            'year': entry.year,
            'term': entry.term,
            'type': entry.entry_type,
        },
        'program_plos': plos,
        'existing': {
            'rationale': clip(content.get('rationale') or '', 2000),
            'clos': content.get('clos') or [],
            'mapping_clos': content.get('mapping_clos') or [],
            'section_a_items': content.get('section_a_items') or [],
            'section_b_items': content.get('section_b_items') or [],
        },
        'output_schema': {
            'rationale': '',
            'clos': [{'text': '', 'plo': 'PLO1'}],
            'mapping_clos': [{'teaching_learning': '', 'assessment': ''}],
            'section_a_items': [{'content': '', 'clos': 'CLO1'}],
            'section_b_items': [{'content': '', 'clos': 'CLO1'}],
        },
    }, ensure_ascii=False)

    meta = generate_outline_json_with_meta(system_prompt, user_prompt, max_tokens=3500)
    payload = extract_json_from_response(meta.get('text') or '')
    if not isinstance(payload, dict):
        raise ValueError('এআই খসড়া অসম্পূর্ণ JSON ছিল।')

    proposal = {}
    if 'rationale' in wanted and payload.get('rationale'):
        proposal['rationale'] = payload.get('rationale')
    if 'clos' in wanted and isinstance(payload.get('clos'), list):
        proposal['clos'] = payload.get('clos')
    if 'mapping' in wanted and isinstance(payload.get('mapping_clos'), list):
        proposal['mapping_clos'] = payload.get('mapping_clos')
    if 'content' in wanted:
        if isinstance(payload.get('section_a_items'), list):
            proposal['section_a_items'] = payload.get('section_a_items')
        if isinstance(payload.get('section_b_items'), list):
            proposal['section_b_items'] = payload.get('section_b_items')
        if payload.get('section_a'):
            proposal['section_a'] = payload.get('section_a')
        if payload.get('section_b'):
            proposal['section_b'] = payload.get('section_b')
    return proposal


def push_entry_to_course(entry):
    """Copy accepted Part C fields onto Course Information (outline lock source)."""
    from blueprints.course_management.models import Course

    course = None
    if getattr(entry, 'course_id', None):
        course = Course.query.get(entry.course_id)
    if course is None and entry.course_code:
        q = Course.query.filter(Course.course_code == entry.course_code)
        if entry.year:
            q = q.filter(Course.year == entry.year)
        if entry.term:
            q = q.filter(Course.term == entry.term)
        course = q.first() or Course.query.filter(Course.course_code == entry.course_code).first()
    if course is None:
        raise ValueError('Course Information-এ মিলিয়ে কোর্স পাওয়া যায়নি।')

    content = entry.get_content_dict() or {}
    if content.get('rationale'):
        course.rationale = content.get('rationale')

    clos = content.get('clos') or []
    mapping = content.get('mapping_clos') or []
    if clos:
        mapped = []
        for idx, row in enumerate(clos):
            if not isinstance(row, dict):
                continue
            map_row = mapping[idx] if idx < len(mapping) and isinstance(mapping[idx], dict) else {}
            mapped.append({
                'text': (row.get('text') or '').strip(),
                'plo': row.get('plo') or '',
                'teaching_strategy': map_row.get('teaching_learning') or '',
                'assessment_strategy': map_row.get('assessment') or '',
            })
        if mapped:
            course.clo = json.dumps(mapped, ensure_ascii=False)

    items_a = content.get('section_a_items') or []
    items_b = content.get('section_b_items') or []

    def _content_rows_json(items, fallback_text):
        rows = []
        for row in items or []:
            if isinstance(row, dict):
                text = (row.get('content') or row.get('topic') or '').strip()
                if not text:
                    continue
                rows.append({
                    'content': text,
                    'hrs': str(row.get('hrs') or row.get('hours') or '').strip(),
                    'clo': str(row.get('clo') or row.get('clos') or '').strip(),
                })
            else:
                text = str(row or '').strip()
                if text:
                    rows.append({'content': text, 'hrs': '', 'clo': ''})
        if rows:
            return json.dumps(rows, ensure_ascii=False)
        return fallback_text or None

    if items_a or content.get('section_a'):
        course.content_section_a = _content_rows_json(items_a, content.get('section_a'))
    if items_b or content.get('section_b'):
        course.content_section_b = _content_rows_json(items_b, content.get('section_b'))

    entry.course_id = course.id
    return course.id
