"""Fill outline fields from curriculum/calendar without an AI call."""
from math import ceil

from utils.ai.curriculum_anchor import build_curriculum_anchor, flatten_curriculum_topic_slots, _syllabus_locked


def fill_part_a_from_context(context, generation_options=None):
    """CLO/summary/objectives come from curriculum; AI is not needed for Part A."""
    course = (context or {}).get('course') or {}
    session = (context or {}).get('session') or {}
    constraints = (context or {}).get('constraints') or {}
    opts = generation_options if isinstance(generation_options, dict) else {}
    delivery = (opts.get('delivery_type') or session.get('course_delivery_type') or 'theory').lower()
    credit = course.get('credit') or ''

    if delivery == 'sessional':
        contact = f'{credit} hours per week (practical / clinic / field)' if credit else 'Practical sessions as scheduled'
        cie, smee = '70', '30'
    else:
        contact = f'{credit} hours per week (lecture + discussion)' if credit else 'As scheduled'
        cie = str(constraints.get('cie_marks_default') or '40')
        smee = str(constraints.get('smee_marks_default') or '60')

    year = session.get('year') or ''
    term = session.get('term') or ''
    section = session.get('section') or ''
    payload = {
        'prerequisites': 'As specified in the curriculum / previous term courses.',
        'contact_hours': contact,
        'cie_marks': cie,
        'smee_marks': smee,
        'credit_value': str(credit or ''),
        'course_type': course.get('core_optional') or course.get('course_type') or 'Core',
        'level_term_section': ' / '.join(p for p in (year, term, section) if p),
    }
    return payload


def local_content_summary(context):
    return build_curriculum_anchor(context).get('course_content_summary') or {'sectionA': [], 'sectionB': []}


def default_mark_tables(generation_options=None, delivery='theory'):
    plan = (generation_options or {}).get('assessment_plan') or []
    delivery = (delivery or 'theory').lower()

    def _split(total, items, label):
        rows = []
        if not items:
            return [{'category': label, 'marks': total}]
        counts = [max(1, int(item.get('count') or 1)) for item in items]
        weight = sum(counts) or 1
        leftover = total
        for idx, item in enumerate(items):
            marks = leftover if idx == len(items) - 1 else max(1, round(total * counts[idx] / weight))
            leftover -= marks
            rows.append({'category': f'{item["name"]} × {item["count"]}', 'marks': max(1, marks)})
        return rows

    if delivery == 'sessional':
        cie = [{'category': 'Attendance / Class Participation', 'marks': 10}]
        cie.extend(_split(60, plan, 'Sessional Assessment'))
        smee = [{'category': 'Viva voce', 'marks': 30}]
        return cie, smee, '70', '30'

    cie = [{'category': 'Attendance', 'marks': 10}]
    cie.extend(_split(30, plan, 'Class Tests / Assignments'))
    smee = [{'category': 'Written Examination', 'marks': 60}]
    return cie, smee, '40', '60'


def _flatten_topics(context):
    return flatten_curriculum_topic_slots(context)


def _working_dates(context, total_classes=None):
    dates = list(((context or {}).get('calendar') or {}).get('working_dates') or [])
    if total_classes and len(dates) > total_classes:
        return dates[:total_classes]
    return dates


def _week_number(value):
    try:
        return int(str(value or '').replace('Week', '').strip() or 0)
    except (TypeError, ValueError):
        return 0


def build_lesson_plan_skeleton(context, generation_options=None):
    """One row per class; Date is the week's range, not a single day."""
    from utils.ai.calendar_utils import format_week_date_range, group_working_dates_into_weeks

    opts = generation_options if isinstance(generation_options, dict) else {}
    constraints = (context or {}).get('constraints') or {}
    try:
        total = int(opts.get('total_classes') or constraints.get('total_classes') or 0)
    except (TypeError, ValueError):
        total = 0
    try:
        cpw = max(1, int(opts.get('classes_per_week') or constraints.get('classes_per_week') or 3))
    except (TypeError, ValueError):
        cpw = 3

    dates = _working_dates(context)
    weeks = group_working_dates_into_weeks(dates)
    if not weeks:
        week_count = max(1, ceil((total or 14) / cpw))
        weeks = [None] * week_count

    topics = _flatten_topics(context)
    topic_idx = 0
    slots = []
    week_num = 0
    max_weeks = 18

    while True:
        if total and len(slots) >= total:
            break
        if week_num >= max_weeks:
            break
        if week_num < len(weeks):
            days = weeks[week_num]
        elif total:
            days = None
        else:
            break
        week_num += 1
        date_range = format_week_date_range(days) if days else f'Week {week_num}'
        rows_this_week = min(cpw, total - len(slots)) if total else cpw
        for _ in range(rows_this_week):
            if topic_idx < len(topics):
                topic_row = topics[topic_idx]
            elif topics:
                last = topics[-1]
                last_name = (last.get('topic') or '').strip()
                if _syllabus_locked(opts):
                    topic_row = {
                        'topic': f'Review of {last_name}' if last_name else last_name,
                        'clo_alignment': last.get('clo_alignment') or '',
                    }
                else:
                    topic_row = {
                        'topic': 'Revision / Buffer',
                        'clo_alignment': last.get('clo_alignment') or '',
                    }
            else:
                topic_row = {'topic': 'Revision / Buffer' if not _syllabus_locked(opts) else '', 'clo_alignment': ''}
            topic_idx += 1
            slots.append({
                'week': f'Week {week_num}',
                'date': date_range,
                'topic': topic_row.get('topic') or '',
                'outcome': '',
                'activities': '',
                'teaching_assessment': 'Lecture, discussion',
                'clo_alignment': topic_row.get('clo_alignment') or '',
            })

    names = []
    for item in opts.get('assessment_plan') or []:
        names.extend([item['name']] * int(item.get('count') or 1))
    if names and slots:
        n = len(slots)
        used = set()
        for i, name in enumerate(names):
            pos = int((i + 1) * n / (len(names) + 1))
            pos = min(max(pos, 0), n - 1)
            if pos in used and pos + 1 < n:
                pos += 1
            used.add(pos)
            slots[pos]['teaching_assessment'] = f'{name}; lecture/discussion'
    return slots


def merge_weekly_notes_into_skeleton(skeleton, weekly_notes, generation_options=None):
    """Copy AI week-level notes onto class rows. Keep skeleton week/date ranges."""
    notes = weekly_notes if isinstance(weekly_notes, list) else []
    if not skeleton:
        return notes

    locked = _syllabus_locked(generation_options)
    text_keys = ('outcome', 'activities', 'teaching_assessment', 'clo_alignment')
    if not locked:
        text_keys = ('topic',) + text_keys

    # Already per-class (model ignored weekly instruction). Never copy date.
    if len(notes) >= max(8, int(len(skeleton) * 0.7)):
        merged = []
        for idx, slot in enumerate(skeleton):
            src = notes[idx] if idx < len(notes) else {}
            row = dict(slot)
            for key in text_keys:
                val = src.get(key)
                if val:
                    row[key] = val
            merged.append(row)
        return merged

    by_week = {}
    for row in notes:
        if not isinstance(row, dict):
            continue
        week = _week_number(row.get('week'))
        if week:
            by_week[week] = row

    ordered = [row for row in notes if isinstance(row, dict)]
    out = [dict(slot) for slot in skeleton]
    week_offsets = {}
    for row in out:
        week = _week_number(row.get('week'))
        note = by_week.get(week)
        if not note and ordered:
            note = ordered[min(max(week - 1, 0), len(ordered) - 1)]
        if not note:
            continue
        for key in ('outcome', 'activities', 'teaching_assessment', 'clo_alignment'):
            val = note.get(key)
            if val:
                row[key] = val
        if locked:
            continue
        topics = note.get('topics')
        if isinstance(topics, list) and topics:
            idx = week_offsets.get(week, 0)
            if idx < len(topics) and topics[idx]:
                row['topic'] = str(topics[idx])
            week_offsets[week] = idx + 1
        elif note.get('topic'):
            row['topic'] = str(note.get('topic'))
    return out


def fill_part_b_locally(context, generation_options=None):
    session = (context or {}).get('session') or {}
    opts = generation_options if isinstance(generation_options, dict) else {}
    delivery = (opts.get('delivery_type') or session.get('course_delivery_type') or 'theory').lower()
    cie, smee, cie_marks, smee_marks = default_mark_tables(opts, delivery=delivery)
    return {
        'course_content_summary': local_content_summary(context),
        'lesson_plan': build_lesson_plan_skeleton(context, opts),
        'cie_breakdown': cie,
        'smee_breakdown': smee,
        'cie_marks': cie_marks,
        'smee_marks': smee_marks,
    }


_DEFAULT_GRADING = [
    {'range': '80-100', 'grade': 'A+'},
    {'range': '75-79', 'grade': 'A'},
    {'range': '70-74', 'grade': 'A-'},
    {'range': '65-69', 'grade': 'B+'},
    {'range': '60-64', 'grade': 'B'},
    {'range': '55-59', 'grade': 'B-'},
    {'range': '50-54', 'grade': 'C+'},
    {'range': '45-49', 'grade': 'C'},
    {'range': '40-44', 'grade': 'D'},
    {'range': '00-39', 'grade': 'F'},
]


def _clo_numbers(context):
    clos = ((context or {}).get('course') or {}).get('clos') or []
    numbers = []
    for idx, clo in enumerate(clos, start=1):
        if isinstance(clo, dict):
            numbers.append(clo.get('number') or idx)
        else:
            numbers.append(idx)
    return numbers or [1]


def fill_part_c_locally(context, generation_options=None):
    opts = generation_options if isinstance(generation_options, dict) else {}
    session = (context or {}).get('session') or {}
    delivery = (opts.get('delivery_type') or session.get('course_delivery_type') or 'theory').lower()
    plan = opts.get('assessment_plan') or []
    clo_nums = _clo_numbers(context)

    techniques = []
    for item in plan:
        count = max(1, int(item.get('count') or 1))
        for n in range(1, count + 1):
            label = item['name'] if count == 1 else f'{item["name"]} {n}'
            row = {'strategy': label, 'total_marks': 10}
            for clo in clo_nums[:4]:
                row[f'clo{clo}'] = 10 if clo == clo_nums[0] else ''
            techniques.append(row)
    if not techniques:
        techniques = [{'strategy': 'Class Test', 'total_marks': 10, 'clo1': 10}]

    if delivery == 'sessional':
        strategy = {
            'attendance_percent': 10,
            'ca_assessment_percent': 60,
            'viva_percent': 30,
            'ca_components': [item['name'] for item in plan] or ['Sessional Report', 'Presentation'],
            'strategy_points': [
                'Participate in every practical/clinic session.',
                'Submit reports on the scheduled date.',
                'Viva covers the full sessional syllabus.',
            ],
        }
        make_up = 'Missed practical work may be repeated only with prior approval of the course teacher.'
        rubrics = [
            {
                'type': 'Sessional Report',
                'criteria': 'Accuracy and completeness',
                'excellent': 'Complete, accurate, well organised',
                'good': 'Mostly complete with minor gaps',
                'satisfactory': 'Basic coverage',
                'poor': 'Incomplete or inaccurate',
            },
            {
                'type': 'Viva',
                'criteria': 'Understanding and communication',
                'excellent': 'Clear, confident, precise answers',
                'good': 'Sound answers with small gaps',
                'satisfactory': 'Partial understanding',
                'poor': 'Unable to explain core points',
            },
        ]
    else:
        strategy = {
            'attendance_percent': 10,
            'ca_percent': 30,
            'final_exam_percent': 60,
            'attendance_comment': 'Minimum mark is 4 for 60% attendance',
            'ca_comment': 'Best assessments as per departmental policy',
            'final_exam_comment': 'Section A and B combined',
        }
        make_up = 'A missed class test may be retaken only with documented cause and teacher approval.'
        rubrics = [
            {
                'type': 'Assignment',
                'criteria': 'Analysis and referencing',
                'excellent': 'Original, well cited analysis',
                'good': 'Clear analysis, adequate sources',
                'satisfactory': 'Descriptive with limited analysis',
                'poor': 'Off-topic or uncited',
            }
        ]

    return {
        'assessment_strategy': strategy,
        'assessment_techniques': techniques,
        'rubrics': rubrics,
        'grading_policy': list(_DEFAULT_GRADING),
        'evaluation_policy': {
            'grading_system': 'Khulna University letter-grade system.',
            'make_up_procedures': make_up,
        },
        'make_up_procedures': make_up,
    }


def fill_part_d_locally(context, generation_options=None):
    course = (context or {}).get('course') or {}
    name = course.get('course_name') or ((context or {}).get('session') or {}).get('course_name') or 'this course'
    snippets = ((context or {}).get('uploaded_materials') or {}).get('snippets') or []
    from_files = []
    for row in snippets:
        title = (row.get('file_name') or '').strip()
        if title:
            from_files.append(title)

    textbooks = from_files[:4] or [
        f'Prescribed materials for {name} as listed in the curriculum.',
    ]
    return {
        'textbooks': textbooks,
        'reference_books': [
            'Relevant statutes, rules, and reported cases as assigned in class.',
        ],
        'other_resources': [
            'Lecture notes, handouts, and LMS uploads.',
        ],
        'course_file_components': [
            'Course outline',
            'Lesson plan',
            'Assessment records',
            'Sample scripts / reports',
        ],
        'other_issues': {
            'class_discussion': 'Students are expected to prepare assigned materials and take part in discussion.',
            'general_expectations': 'Attend regularly, meet deadlines, and maintain professional conduct.',
            'communication': 'Contact the course teacher during notified office hours or by official email.',
            'academic_honesty': 'Plagiarism, collusion, and unfair means will be dealt with under university rules.',
        },
    }


def fill_part_cd_locally(context, generation_options=None):
    payload = {}
    payload.update(fill_part_c_locally(context, generation_options))
    payload.update(fill_part_d_locally(context, generation_options))
    return payload
