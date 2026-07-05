"""Resolve Curriculator PLO / CLO context for AI outline generation."""
import re

from blueprints.curriculator.models import (
    SyllabusCourseEntry,
    SyllabusDocument,
    SyllabusPart,
    SyllabusPartASection,
)

YEAR_TERM_SUFFIX = {
    ('first', 'first'): '1_1',
    ('first', 'second'): '1_2',
    ('second', 'first'): '2_1',
    ('second', 'second'): '2_2',
    ('third', 'first'): '3_1',
    ('fourth', 'first'): '4_1',
    ('fourth', 'second'): '4_2',
}


def _norm(value):
    return (value or '').strip().lower()


def year_term_to_suffix(year, term):
    return YEAR_TERM_SUFFIX.get((_norm(year), _norm(term)))


def _extract_core_code(code_str):
    if not code_str:
        return None
    match = re.search(r'([A-Za-z]+)\s*(\d{4})', code_str)
    if match:
        return f'{match.group(1)}{match.group(2)}'.upper()
    return (code_str or '').strip().upper()


def resolve_syllabus_document(batch=None, curriculum_batches=None):
    """Pick the best matching Curriculator syllabus document by batch."""
    docs = SyllabusDocument.query.order_by(SyllabusDocument.updated_at.desc()).all()
    if not docs:
        return None

    candidates = []
    for batch_value in [batch] + list(curriculum_batches or []):
        if not batch_value:
            continue
        batch_value = str(batch_value).strip()
        for doc in docs:
            if batch_value in doc.get_batches_list():
                candidates.append(doc)
    if candidates:
        return candidates[0]
    return docs[0]


def _get_part_a_section(doc, section_key):
    part_a = SyllabusPart.query.filter_by(document_id=doc.id, part_key='A').first()
    if not part_a:
        return None
    rec = SyllabusPartASection.query.filter_by(part_id=part_a.id, section_key=section_key).first()
    return rec.get_data() if rec else None


def get_program_plos(doc):
    data = _get_part_a_section(doc, 'plos')
    if not isinstance(data, list):
        return []
    return [
        {
            'id': (row.get('id') or f'PLO{idx}').strip(),
            'text': (row.get('text') or '').strip(),
            'category': (row.get('category') or '').strip() or None,
        }
        for idx, row in enumerate(data, start=1)
        if isinstance(row, dict) and (row.get('id') or row.get('text'))
    ]


def _find_course_entry(doc, course_code, course_name=None, year=None, term=None):
    part_c = SyllabusPart.query.filter_by(document_id=doc.id, part_key='C').first()
    if not part_c:
        return None

    entries = SyllabusCourseEntry.query.filter_by(part_id=part_c.id).order_by(
        SyllabusCourseEntry.sort_order, SyllabusCourseEntry.id
    ).all()
    if not entries:
        return None

    target_core = _extract_core_code(course_code)
    year_n, term_n = _norm(year), _norm(term)

    def matches(entry):
        code_match = False
        if course_code and entry.course_code:
            if entry.course_code.strip().upper() == course_code.strip().upper():
                code_match = True
            elif target_core and _extract_core_code(entry.course_code) == target_core:
                code_match = True
        name_match = bool(
            course_name and entry.course_name
            and course_name.strip().lower() in entry.course_name.strip().lower()
        )
        if not (code_match or name_match):
            return False
        if year_n and _norm(entry.year) != year_n:
            return False
        if term_n and _norm(entry.term) != term_n:
            return False
        return True

    for entry in entries:
        if matches(entry):
            return entry
    for entry in entries:
        if course_code and entry.course_code and entry.course_code.strip().upper() == course_code.strip().upper():
            return entry
    return None


def get_curriculator_clos(doc, course_code, course_name=None, year=None, term=None):
    entry = _find_course_entry(doc, course_code, course_name=course_name, year=year, term=term)
    if not entry:
        return []
    content = entry.get_content_dict()
    clos = content.get('clos') or []
    result = []
    for idx, row in enumerate(clos, start=1):
        if not isinstance(row, dict):
            continue
        text = (row.get('text') or row.get('upon_completion') or row.get('description') or '').strip()
        if not text:
            continue
        plo_raw = row.get('plo', '')
        plos = []
        if isinstance(plo_raw, str) and plo_raw.strip():
            plos = [p.strip() for p in re.split(r'[,;]+', plo_raw) if p.strip()]
        elif isinstance(plo_raw, list):
            plos = [str(p).strip() for p in plo_raw if str(p).strip()]
        result.append({'number': idx, 'description': text, 'plos': plos})
    return result


def get_course_mapped_plos(doc, course_code, course_name=None, year=None, term=None):
    """PLO ids mapped to this course from Part A course↔PLO matrix."""
    suffix = year_term_to_suffix(year, term)
    if not suffix:
        return []

    plos = get_program_plos(doc)
    if not plos:
        return []

    section_key = f'mapping_course_plo_{suffix}'
    matrix = _get_part_a_section(doc, section_key)
    if not isinstance(matrix, dict):
        return []

    part_c = SyllabusPart.query.filter_by(document_id=doc.id, part_key='C').first()
    if not part_c:
        return []

    year_label, term_label = YEAR_TERM_SUFFIX.get((_norm(year), _norm(term)), (year, term))
    entries = [
        e for e in SyllabusCourseEntry.query.filter_by(part_id=part_c.id).order_by(
            SyllabusCourseEntry.sort_order, SyllabusCourseEntry.id
        ).all()
        if _norm(e.year) == _norm(year_label) and _norm(e.term) == _norm(term_label)
    ]

    row_idx = None
    target_core = _extract_core_code(course_code)
    for i, entry in enumerate(entries):
        if course_code and entry.course_code and entry.course_code.strip().upper() == course_code.strip().upper():
            row_idx = i
            break
        if target_core and entry.course_code and _extract_core_code(entry.course_code) == target_core:
            row_idx = i
            break
        if course_name and entry.course_name and course_name.strip().lower() in entry.course_name.strip().lower():
            row_idx = i
            break

    if row_idx is None:
        return []

    cells = matrix.get('cells') or []
    if row_idx >= len(cells):
        return []

    mapped = []
    row = cells[row_idx]
    for col_idx, plo in enumerate(plos):
        if col_idx < len(row) and row[col_idx]:
            mapped.append(plo['id'])
    return mapped


def build_suggested_plo_mapping(clos_with_plo, default_weight=3):
    """Build save_course_outline-compatible plo_mapping from CLO rows."""
    mapping = {}
    for clo in clos_with_plo or []:
        clo_num = clo.get('number')
        plos = clo.get('plos') or []
        if not clo_num or not plos:
            continue
        clo_key = f'CLO {clo_num}'
        mapping[clo_key] = {}
        for plo in plos:
            plo_key = plo if str(plo).upper().startswith('PLO') else f'PLO {plo}'
            mapping[clo_key][plo_key] = default_weight
    return mapping


def build_curriculator_context(session, curriculum=None, batch=None):
    """Assemble Curriculator PLO/CLO data for AI context."""
    curriculum_batches = []
    if curriculum and hasattr(curriculum, 'get_batches_list'):
        curriculum_batches = curriculum.get_batches_list()

    doc = resolve_syllabus_document(batch=batch, curriculum_batches=curriculum_batches)
    if not doc:
        return None

    year = getattr(session, 'year', None)
    term = getattr(session, 'term', None)
    course_code = getattr(session, 'course_code', None)
    course_name = getattr(session, 'course_name', None)

    plos = get_program_plos(doc)
    clos = get_curriculator_clos(doc, course_code, course_name=course_name, year=year, term=term)
    course_plos = get_course_mapped_plos(doc, course_code, course_name=course_name, year=year, term=term)
    suggested_mapping = build_suggested_plo_mapping(clos)

    return {
        'document_name': doc.name,
        'program_plos': plos,
        'course_mapped_plos': course_plos,
        'clos_with_plo': clos,
        'suggested_plo_mapping': suggested_mapping,
    }
