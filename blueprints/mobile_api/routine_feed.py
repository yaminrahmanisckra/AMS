"""Published routine slots for the signed-in teacher or student.

Mirrors the website's "my classes" rules: revealed routines only, scoped to
active operational windows. Teachers match their teacher id or call sign
(including shared slots stored as "AB/CD"). Students match registered course
codes. This read path does not write the routine.
"""
from __future__ import annotations

import re

from utils.ownership import resolve_caller_student, resolve_caller_teacher
from utils.timezone import bd_now
from utils.window_utils import filter_query_by_window_id, get_active_windows

WEEKDAYS = (
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
)
DAY_ORDER = {name.lower(): index for index, name in enumerate(
    ('Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')
)}
_SLOT_RE = re.compile(
    r'(\d{1,2}):(\d{2})\s*(AM|PM)?\s*[-–—]\s*(\d{1,2}):(\d{2})\s*(AM|PM)?',
    re.IGNORECASE,
)
_WIDGET_LINE_CAP = 5


def routine_payload(user, audience: str) -> dict:
    today = WEEKDAYS[bd_now().weekday()]
    windows = get_active_windows()
    published = _published_routines(windows)
    catalog_names = _catalog_names()

    classes = []
    if audience == 'teacher':
        teacher = resolve_caller_teacher(user)
        shorts = _teacher_shorts(teacher)
        if teacher is None:
            notice = 'Your account is not linked to a teacher profile.'
        else:
            notice = None
            for window, saved in published:
                parts = _assigned_parts(teacher, window.id)
                for row in _entries(saved.id):
                    if _include_teacher_slot(row, teacher, shorts, parts):
                        classes.append(_class_dict(
                            row, saved, window, catalog_names, {},
                        ))
    else:
        student = resolve_caller_student(user)
        if student is None:
            notice = 'No student record is linked to this account.'
        else:
            notice = None
            for window, saved in published:
                codes, registration_names = _registration_codes(student, window.id)
                if not codes:
                    continue
                for row in _entries(saved.id):
                    if _include_student_slot(row, codes):
                        classes.append(_class_dict(
                            row, saved, window, catalog_names, registration_names,
                        ))

    classes.sort(key=_class_sort_key)
    today_classes = [item for item in classes if item['day'].lower() == today.lower()]

    if notice is None and not published:
        notice = 'No published routine yet.'
    elif notice is None and not classes:
        notice = 'None of your classes are in the published routine.'

    window_names = {item['window_name'] for item in classes}
    lines = []
    for item in today_classes[:_WIDGET_LINE_CAP]:
        detail_bits = []
        if len(window_names) > 1 and item['window_name']:
            detail_bits.append(item['window_name'])
        if item['room']:
            detail_bits.append(item['room'])
        if audience == 'student' and item['teacher']:
            detail_bits.append(item['teacher'])
        lines.append({
            'time': item['time_compact'] or item['time'],
            'course_code': item['course_code'],
            'course_name': item['course_name'],
            'room': item['room'],
            'teacher': item['teacher'],
            'day': item['day'],
            'detail': ' · '.join(detail_bits),
        })

    return {
        'schema': 1,
        'viewer': audience,
        'display_name': getattr(user, 'full_name', '') or '',
        'timezone': 'Asia/Dhaka',
        'today': today,
        'generated_at': bd_now().isoformat(timespec='seconds'),
        'notice': notice,
        'published_routines': [
            {
                'id': saved.id,
                'name': saved.name or saved.year,
                'year': saved.year,
                'window_id': window.id,
                'window_name': window.name,
                'updated_at': _utc_iso(saved.updated_at or saved.created_at),
            }
            for window, saved in published
        ],
        'classes': classes,
        'today_classes': today_classes,
        'widget': {
            'title': "Today's classes",
            'empty_text': 'No classes today',
            'lines': lines,
            'more_count': max(0, len(today_classes) - len(lines)),
        },
    }


def _published_routines(windows):
    from blueprints.routine_management.models import SavedRoutine

    found = []
    for window in windows:
        query = SavedRoutine.query.filter(SavedRoutine.is_revealed.is_(True))
        query = filter_query_by_window_id(query, SavedRoutine, window.id)
        for saved in query.order_by(SavedRoutine.id.asc()).all():
            found.append((window, saved))
    return found


def _entries(saved_routine_id):
    from blueprints.routine_management.models import Routine

    return Routine.query.filter_by(saved_routine_id=saved_routine_id).all()


def _catalog_names():
    from blueprints.course_management.models import Course
    from extensions import db

    names = {}
    rows = db.session.query(Course.course_code, Course.course_name).all()
    for code, name in rows:
        key = _normalize_course_code(code)
        if key and key not in names and name:
            names[key] = name
    return names


def _registration_codes(student, window_id):
    from blueprints.course_management.models import StudentCourseRegistration

    query = StudentCourseRegistration.query.filter(
        StudentCourseRegistration.student_id == student.id,
        StudentCourseRegistration.status != 'archived',
    )
    query = filter_query_by_window_id(query, StudentCourseRegistration, window_id)
    codes = []
    names = {}
    for reg in query.all():
        code = str(reg.course_code or '').strip()
        if not code:
            continue
        codes.append(code)
        key = _normalize_course_code(code)
        if key and reg.course_name:
            names[key] = reg.course_name
    return codes, names


def _assigned_parts(teacher, window_id):
    from blueprints.course_management.models import CourseSessionAssignment
    from blueprints.routine_management.models import AssignedCourse

    parts = []
    seen = set()

    def add(code, part):
        code = str(code or '').strip()
        if not code:
            return
        label = str(part or 'Full').strip() or 'Full'
        key = (_normalize_course_code(code), label)
        if key in seen:
            return
        seen.add(key)
        parts.append({'code': code, 'part': label})

    session_query = CourseSessionAssignment.query.filter_by(teacher_id=teacher.id)
    session_query = filter_query_by_window_id(session_query, CourseSessionAssignment, window_id)
    for assignment in session_query.all():
        course = getattr(assignment, 'course', None)
        add(getattr(course, 'course_code', ''), _section_part(assignment.section))

    assigned_query = AssignedCourse.query.filter_by(teacher_id=teacher.id)
    assigned_query = filter_query_by_window_id(assigned_query, AssignedCourse, window_id)
    for assignment in assigned_query.all():
        course = getattr(assignment, 'course', None)
        add(getattr(course, 'course_code', ''), getattr(assignment, 'part', None) or 'Full')
    return parts


def _section_part(section):
    section = str(section or '').strip()
    if section in ('A', 'B'):
        return f'Part {section}'
    return 'Full'


def _teacher_shorts(teacher):
    if teacher is None:
        return set()
    shorts = set()
    for value in (getattr(teacher, 'call_sign', None), getattr(teacher, 'short_name', None)):
        text = str(value or '').strip().lower()
        if text:
            shorts.add(text)
    return shorts


def _include_teacher_slot(row, teacher, shorts, parts):
    if _taught_by_teacher(row, teacher, shorts):
        return True
    if _slot_has_teacher_identity(row):
        return False
    return _matches_assigned_part(row, parts)


def _include_student_slot(row, codes):
    routine_code = getattr(row, 'course_code', None)
    if not str(routine_code or '').strip():
        return False
    return any(_course_codes_match(routine_code, code) for code in codes)


def _taught_by_teacher(row, teacher, shorts):
    teacher_id = getattr(row, 'teacher_id', None)
    if teacher is not None and teacher_id and int(teacher_id) == int(teacher.id):
        return True
    if shorts and (_short_tokens(getattr(row, 'teacher_short_name', '')) & shorts):
        return True
    return False


def _slot_has_teacher_identity(row):
    if getattr(row, 'teacher_id', None):
        return True
    return bool(str(getattr(row, 'teacher_short_name', '') or '').strip())


def _matches_assigned_part(row, parts):
    item_part = str(getattr(row, 'part', None) or '').strip()
    is_shared = bool(getattr(row, 'is_shared', False)) or item_part == 'Shared'
    routine_code = getattr(row, 'course_code', None)
    for part in parts:
        if not _course_codes_match(routine_code, part['code']):
            continue
        assigned = str(part.get('part') or 'Full').strip() or 'Full'
        if is_shared:
            return True
        if assigned in ('Full', 'Shared'):
            if (not item_part) or item_part in ('Full', 'Shared'):
                return True
            continue
        if (not item_part) or item_part == 'Full':
            continue
        if assigned == item_part:
            return True
    return False


def _short_tokens(value):
    text = str(value or '').replace(',', '/')
    return {part.strip().lower() for part in text.split('/') if part.strip()}


def _normalize_course_code(code):
    return ' '.join(str(code or '').strip().lower().split())


def _course_codes_match(routine_code, my_code):
    """Same matching rules as the routine page's my-courses filter."""
    left = _normalize_course_code(routine_code)
    right = _normalize_course_code(my_code)
    if not left or not right:
        return False
    if left == right or left.endswith(right) or right.endswith(left):
        return True
    left_parts = [part for part in left.split(' ') if part]
    right_parts = [part for part in right.split(' ') if part]
    if len(left_parts) >= 2 and len(right_parts) >= 2:
        return ' '.join(left_parts[-2:]) == ' '.join(right_parts[-2:])
    return False


def _class_dict(row, saved, window, catalog_names, registration_names):
    course_code = str(getattr(row, 'course_code', None) or '').strip()
    custom_name = str(getattr(row, 'custom_course_name', None) or '').strip()
    is_custom = bool(getattr(row, 'is_custom', False))
    start, end, compact = _slot_bounds(getattr(row, 'time_slot', None))
    return {
        'day': _canon_day(getattr(row, 'day', None)),
        'time': str(getattr(row, 'time_slot', None) or '').strip(),
        'time_compact': compact,
        'start': start,
        'end': end,
        'course_code': course_code,
        'course_name': _lookup_course_name(
            course_code, registration_names, catalog_names, custom_name, is_custom,
        ),
        'room': str(getattr(row, 'room_number', None) or '').strip(),
        'teacher': str(getattr(row, 'teacher_short_name', None) or '').strip(),
        'part': str(getattr(row, 'part', None) or '').strip(),
        'shared': bool(getattr(row, 'is_shared', False)),
        'year': str(getattr(row, 'year', None) or '').strip(),
        'term': str(getattr(row, 'term', None) or '').strip(),
        'routine_id': saved.id,
        'routine_name': saved.name or saved.year,
        'window_id': window.id,
        'window_name': window.name,
    }


def _lookup_course_name(code, registration_names, catalog_names, custom_name, is_custom):
    if is_custom and custom_name:
        return custom_name
    if not code:
        return custom_name
    for source in (registration_names, catalog_names):
        key = _normalize_course_code(code)
        if key in source and source[key]:
            return source[key]
        for other, name in source.items():
            if name and _course_codes_match(code, other):
                return name
    return custom_name


def _canon_day(value):
    text = str(value or '').strip()
    mapped = {
        'sunday': 'Sunday',
        'monday': 'Monday',
        'tuesday': 'Tuesday',
        'wednesday': 'Wednesday',
        'thursday': 'Thursday',
        'friday': 'Friday',
        'saturday': 'Saturday',
    }
    return mapped.get(text.lower(), text)


def _clock_minutes(hour, minute, ampm):
    hour = int(hour)
    minute = int(minute)
    if ampm:
        hour = hour % 12
        if ampm.upper() == 'PM':
            hour += 12
    return hour * 60 + minute


def _hhmm(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _slot_bounds(slot):
    match = _SLOT_RE.search(str(slot or ''))
    if not match:
        return '', '', ''
    start_ampm = (match.group(3) or '').upper()
    end_ampm = (match.group(6) or '').upper()
    # A trailing AM/PM often applies to both sides: "09:10 - 10:00 AM".
    if not start_ampm:
        start_ampm = end_ampm
    if not end_ampm:
        end_ampm = start_ampm
    start_minutes = _clock_minutes(match.group(1), match.group(2), start_ampm)
    end_minutes = _clock_minutes(match.group(4), match.group(5), end_ampm)
    left = f'{int(match.group(1))}:{match.group(2)}'
    right = f'{int(match.group(4))}:{match.group(5)}'
    if start_ampm and end_ampm and start_ampm == end_ampm:
        compact = f'{left}–{right} {start_ampm}'
    elif start_ampm or end_ampm:
        compact = f'{left} {start_ampm}'.strip() + '–' + f'{right} {end_ampm}'.strip()
    else:
        compact = f'{left}–{right}'
    return _hhmm(start_minutes), _hhmm(end_minutes), compact


def _class_sort_key(item):
    day_index = DAY_ORDER.get(item['day'].lower(), 99)
    start = item['start']
    if start and ':' in start:
        hour, minute = start.split(':', 1)
        try:
            minutes = int(hour) * 60 + int(minute)
        except ValueError:
            minutes = 24 * 60 + 1
    else:
        minutes = 24 * 60 + 1
    return (day_index, minutes, item['course_code'], item['room'])


def _utc_iso(value):
    if not value:
        return None
    if getattr(value, 'tzinfo', None) is None:
        return value.isoformat(timespec='seconds') + 'Z'
    return value.isoformat(timespec='seconds')
