"""Build structured context for AI Course Outline generation."""
import json
import re

from utils.ai.calendar_utils import build_calendar_summary


def _parse_json_field(value):
    if not value:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _extract_core_code(code_str):
    if not code_str:
        return None
    match = re.search(r'([A-Za-z]+)\s*(\d{4})', code_str)
    if match:
        return f'{match.group(1)}{match.group(2)}'
    return None


def find_best_course_for_session(session, Course, CurriculumYearTerm=None, query_for_window=None):
    """Score curriculum courses to pick the best match for a class session."""
    if not Course or not session:
        return None

    courses = Course.query.filter(
        (Course.course_code == session.course_code) | (Course.course_name == session.course_name)
    ).all()
    if not courses:
        core = _extract_core_code(session.course_code or '')
        if core:
            courses = [c for c in Course.query.all() if _extract_core_code(c.course_code or '') == core]
    if not courses:
        return None
    if len(courses) == 1:
        return courses[0]

    def score(course):
        pts = 0
        if course.rationale:
            pts += 3
        if course.clo:
            pts += 3
        if course.content_section_a or course.content_section_b:
            pts += 2
        if session.year and course.year and str(session.year).lower() in str(course.year).lower():
            pts += 2
        if session.term and course.term and str(session.term).lower() in str(course.term).lower():
            pts += 2
        if CurriculumYearTerm and query_for_window and session.academic_session:
            cfg = query_for_window(CurriculumYearTerm).filter_by(
                curriculum_id=course.curriculum_id,
                academic_session=session.academic_session,
            ).first()
            if cfg:
                pts += 4
        return pts

    return max(courses, key=score)


def resolve_session_batch(session, CourseSessionAssignment=None):
    """Resolve student batch for a class session via CourseSessionAssignment."""
    if not CourseSessionAssignment or not session:
        return None
    assignment = CourseSessionAssignment.query.filter_by(session_id=session.id).first()
    return assignment.batch if assignment and assignment.batch else None


def build_outline_context(session, course_data=None, curriculum=None, calendar_events=None,
                          teacher_name='', CourseSessionAssignment=None, CourseFileUpload=None,
                          include_rag=True, include_curriculator=True, generation_options=None):
    """Assemble all inputs the AI needs."""
    course = course_data
    curriculum_batches = []
    if curriculum and hasattr(curriculum, 'get_batches_list'):
        curriculum_batches = curriculum.get_batches_list()

    batch = resolve_session_batch(session, CourseSessionAssignment=CourseSessionAssignment)

    content_a = _parse_json_field(getattr(course, 'content_section_a', None) if course else None)
    content_b = _parse_json_field(getattr(course, 'content_section_b', None) if course else None)
    clos = course.get_clos_list() if course and hasattr(course, 'get_clos_list') else []

    calendar_summary = build_calendar_summary(
        calendar_events or [],
        academic_session=getattr(session, 'academic_session', '') or '',
        year=getattr(session, 'year', '') or '',
        term=getattr(session, 'term', '') or '',
    )

    credit = float(course.credit) if course and course.credit else None
    classes_per_week = int(credit) if credit else None
    if getattr(session, 'course_scope', None) in ('part_a', 'part_b') and classes_per_week:
        classes_per_week = max(1, classes_per_week // 2)
    total_classes = int(credit * 14) if credit else None

    opts = generation_options if isinstance(generation_options, dict) else {}
    if opts.get('classes_per_week'):
        classes_per_week = int(opts['classes_per_week'])
    if opts.get('total_classes'):
        total_classes = int(opts['total_classes'])

    context = {
        'session': {
            'course_code': session.course_code,
            'course_name': session.course_name,
            'academic_session': session.academic_session,
            'year': session.year,
            'term': session.term,
            'batch': batch,
            'section': getattr(session, 'section', None),
            'course_scope': getattr(session, 'course_scope', 'full'),
            'course_delivery_type': getattr(session, 'course_type', None) or 'theory',
            'teacher_name': teacher_name,
        },
        'course': {
            'course_code': course.course_code if course else session.course_code,
            'course_name': course.course_name if course else session.course_name,
            'credit': credit,
            'course_type': getattr(course, 'course_type', None) if course else None,
            'category': getattr(course, 'category', None) if course else None,
            'core_optional': getattr(course, 'core_optional', None) if course else None,
            'rationale': getattr(course, 'rationale', None) if course else None,
            'clos': clos,
            'content_section_a': content_a,
            'content_section_b': content_b,
        },
        'curriculum': {
            'name': curriculum.name if curriculum else None,
            'applicable_batches': curriculum_batches,
        },
        'calendar': calendar_summary,
        'constraints': {
            'classes_per_week': classes_per_week,
            'total_classes': total_classes,
            'cie_marks_default': '40',
            'smee_marks_default': '60',
            'working_weekdays': 'Sunday to Thursday',
            'language': 'English only',
            'curriculum_is_source_of_truth': True,
        },
    }

    if include_curriculator:
        try:
            from utils.ai.curriculator_context import build_curriculator_context
            curriculator_ctx = build_curriculator_context(session, curriculum=curriculum, batch=batch)
            if curriculator_ctx:
                context['curriculator'] = curriculator_ctx
        except Exception:
            pass

    if include_rag and CourseFileUpload is not None:
        try:
            from utils.ai.rag_context import build_rag_context
            uploads = CourseFileUpload.query.filter_by(session_id=session.id).order_by(
                CourseFileUpload.created_at.desc()
            ).all()
            rag_ctx = build_rag_context(session, course_data=course, uploads=uploads)
            if rag_ctx.get('snippets'):
                context['uploaded_materials'] = rag_ctx
        except Exception:
            pass

    return context
