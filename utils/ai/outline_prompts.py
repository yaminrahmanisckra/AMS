"""Prompt templates for full and per-part Course Outline generation."""
import json

from utils.ai.curriculum_anchor import build_curriculum_anchor, curriculum_grounding_rules
from utils.ai.outline_examples import FEW_SHOT_BY_PART
from utils.tenant import current_tenant


def _localize_outline_text(text: str) -> str:
    from utils.tenant import current_tenant
    t = current_tenant()
    return (
        text.replace('Khulna University Law Discipline', t.display_with_university)
            .replace('KU Law Discipline', t.name)
            .replace('Law Discipline', t.name)
    )


def _compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str)


OUTLINE_PART_FIELDS = {
    'A': [
        'course_objectives', 'course_summary', 'prerequisites', 'contact_hours',
        'cie_marks', 'smee_marks', 'credit_value', 'course_type', 'level_term_section',
        'clo_data', 'plo_mapping',
    ],
    'B': [
        'course_content_summary', 'lesson_plan', 'cie_breakdown', 'smee_breakdown',
    ],
    'C': [
        'assessment_strategy', 'assessment_techniques', 'rubrics', 'grading_policy',
        'evaluation_policy', 'make_up_procedures',
    ],
    'D': [
        'textbooks', 'reference_books', 'other_resources', 'course_file_components', 'other_issues',
    ],
}
OUTLINE_PART_FIELDS['CD'] = OUTLINE_PART_FIELDS['C'] + OUTLINE_PART_FIELDS['D']

PART_MAX_TOKENS = {
    'A': 800,
    'B': 2500,
    'C': 3500,
    'D': 2500,
    'CD': 6000,
    'full': 5000,
}

OUTLINE_JSON_SCHEMA = {
    'course_objectives': ['string'],
    'course_summary': 'string',
    'prerequisites': 'string',
    'contact_hours': 'string',
    'cie_marks': 'string',
    'smee_marks': 'string',
    'credit_value': 'string',
    'course_type': 'string',
    'level_term_section': 'string',
    'clo_data': [{'number': 1, 'description': 'string', 'plos': ['PLO 1']}],
    'plo_mapping': {'CLO 1': {'PLO 1': 3}},
    'course_content_summary': {
        'sectionA': [{'topic': 'string', 'selected': True, 'num_classes': 1}],
        'sectionB': [{'topic': 'string', 'selected': True, 'num_classes': 1}],
    },
    'lesson_plan': [{
        'week': 'Week 1',
        'date': '20-24 July 2025',
        'topic': 'string',
        'outcome': 'string',
        'activities': 'string',
        'teaching_assessment': 'string',
        'clo_alignment': 'CLO 1',
    }],
    'assessment_strategy': {
        'attendance_percent': 10,
        'ca_percent': 30,
        'final_exam_percent': 60,
        'attendance_marks': [{'range': 'Above 90%', 'marks': '10'}],
        'strategy_points': ['string'],
        'ca_assessment_percent': 60,
        'viva_percent': 30,
        'ca_components': ['Assignment', 'Presentation', 'Quiz test'],
        'ca_components_other': 'string',
    },
    'assessment_techniques': [{'strategy': 'string', 'total_marks': 10, 'clo1': 10}],
    'rubrics': [{'type': 'string', 'criteria': 'string', 'excellent': 'string', 'good': 'string', 'satisfactory': 'string', 'poor': 'string'}],
    'grading_policy': [{'range': '80-100', 'grade': 'A+'}],
    'evaluation_policy': {'grading_system': 'string', 'make_up_procedures': 'string'},
    'cie_breakdown': [{'category': 'string', 'marks': 10}],
    'smee_breakdown': [{'category': 'string', 'marks': 60}],
    'textbooks': ['string'],
    'reference_books': ['string'],
    'other_resources': ['string'],
    'course_file_components': ['string'],
    'make_up_procedures': 'string',
    'other_issues': {
        'class_discussion': 'string',
        'general_expectations': 'string',
        'communication': 'string',
        'academic_honesty': 'string',
    },
}

PART_DESCRIPTIONS = {
    'A': 'Part A — Introduction (objectives, summary, prerequisites, contact hours, marks, CLOs, PLO mapping)',
    'B': 'Part B — Course content (weekly teaching notes for dated class slots)',
    'C': 'Part C — Assessment (strategy, techniques, rubrics, grading policy, evaluation)',
    'D': 'Part D — Learning resources (textbooks, references, course file components, policies)',
    'CD': 'Parts C+D — Assessment and learning resources',
}


def _schema_for_part(part, generation_options=None):
    from utils.ai.curriculum_anchor import _syllabus_locked
    if part == 'B':
        week = {
            'week': 1,
            'date_range': '20-24 July 2025',
            'classes_this_week': 4,
            'outcome': 'string',
            'activities': 'string',
            'teaching_assessment': 'string',
            'clo_alignment': 'CLO 1',
        }
        if not _syllabus_locked(generation_options):
            week['topics'] = ['elaboration of syllabus topic 1']
        return {'weeks': [week]}
    fields = OUTLINE_PART_FIELDS.get(part, [])
    return {key: OUTLINE_JSON_SCHEMA[key] for key in fields if key in OUTLINE_JSON_SCHEMA}


def slim_context_for_part(context, part):
    """Send only the fields this part needs — the full context was repeated 4×."""
    context = context or {}
    session = dict(context.get('session') or {})
    course = context.get('course') or {}
    calendar = context.get('calendar') or {}
    constraints = context.get('constraints') or {}
    part = str(part or 'full').upper()

    slim_session = {
        'course_code': session.get('course_code'),
        'course_name': session.get('course_name'),
        'academic_session': session.get('academic_session'),
        'year': session.get('year'),
        'term': session.get('term'),
        'section': session.get('section'),
        'course_delivery_type': session.get('course_delivery_type'),
        'teacher_name': session.get('teacher_name'),
    }
    slim_calendar = {
        'semester_start': calendar.get('semester_start'),
        'semester_end': calendar.get('semester_end'),
        'working_days': calendar.get('working_days'),
        'holidays': calendar.get('holidays') or [],
        'weekend_rule': calendar.get('weekend_rule'),
    }

    if part == 'B':
        clos = []
        for clo in course.get('clos') or []:
            if isinstance(clo, dict):
                clos.append({
                    'number': clo.get('number') or clo.get('id'),
                    'description': (clo.get('description') or clo.get('text') or '')[:180],
                })
            else:
                clos.append(str(clo)[:180])
        return {
            'session': slim_session,
            'course': {
                'credit': course.get('credit'),
                'clos': clos,
            },
            'calendar': slim_calendar,
            'week_slots': _week_slot_summary(context),
            'constraints': {
                'classes_per_week': constraints.get('classes_per_week'),
                'total_classes': constraints.get('total_classes'),
                'language': 'English only',
            },
        }

    if part in ('C', 'CD'):
        clos = []
        for clo in course.get('clos') or []:
            if isinstance(clo, dict):
                clos.append({
                    'number': clo.get('number') or clo.get('id'),
                    'description': (clo.get('description') or clo.get('text') or '')[:180],
                })
            else:
                clos.append(str(clo)[:180])
        out = {
            'session': slim_session,
            'course': {
                'credit': course.get('credit'),
                'core_optional': course.get('core_optional'),
                'clos': clos,
            },
            'constraints': {
                'cie_marks_default': constraints.get('cie_marks_default'),
                'smee_marks_default': constraints.get('smee_marks_default'),
                'language': 'English only',
            },
        }
        if part == 'CD':
            rag = context.get('uploaded_materials') or {}
            snippets = (rag.get('snippets') or [])[:3]
            if snippets:
                out['uploaded_materials'] = {
                    'snippets': [
                        {
                            'file_name': row.get('file_name'),
                            'excerpt': (row.get('excerpt') or '')[:500],
                        }
                        for row in snippets
                    ]
                }
        return out

    if part == 'D':
        rag = context.get('uploaded_materials') or {}
        snippets = (rag.get('snippets') or [])[:3]
        out = {
            'session': slim_session,
            'course': {
                'course_name': course.get('course_name'),
                'rationale': (course.get('rationale') or '')[:500],
            },
        }
        if snippets:
            out['uploaded_materials'] = {
                'snippets': [
                    {
                        'file_name': row.get('file_name'),
                        'excerpt': (row.get('excerpt') or '')[:500],
                    }
                    for row in snippets
                ]
            }
        return out

    # Part A / full fallback
    curriculator = context.get('curriculator') or {}
    return {
        'session': slim_session,
        'course': {
            'course_code': course.get('course_code'),
            'course_name': course.get('course_name'),
            'credit': course.get('credit'),
            'core_optional': course.get('core_optional'),
            'rationale': course.get('rationale'),
            'clos': course.get('clos'),
        },
        'calendar': slim_calendar,
        'constraints': constraints,
        'curriculator': {
            'suggested_plo_mapping': curriculator.get('suggested_plo_mapping'),
        } if curriculator.get('suggested_plo_mapping') else {},
    }


def _week_slot_summary(context):
    """One compact object per academic week (date range, class count, syllabus topics)."""
    from utils.ai.calendar_utils import format_week_date_range, group_working_dates_into_weeks
    from utils.ai.curriculum_anchor import flatten_curriculum_topic_slots

    dates = ((context or {}).get('calendar') or {}).get('working_dates') or []
    cpw = ((context or {}).get('constraints') or {}).get('classes_per_week') or 3
    total = ((context or {}).get('constraints') or {}).get('total_classes')
    try:
        cpw = max(1, int(cpw))
    except (TypeError, ValueError):
        cpw = 3
    try:
        total = int(total) if total else 0
    except (TypeError, ValueError):
        total = 0

    grouped = group_working_dates_into_weeks(dates)
    topics = flatten_curriculum_topic_slots(context)
    topic_idx = 0
    weeks = []
    classes_used = 0
    for idx, days in enumerate(grouped, start=1):
        if total and classes_used >= total:
            break
        rows = cpw if not total else min(cpw, total - classes_used)
        week_topics = []
        for _ in range(rows):
            if topic_idx < len(topics):
                week_topics.append(topics[topic_idx].get('topic') or '')
                topic_idx += 1
            elif topics:
                last_name = (topics[-1].get('topic') or '').strip()
                week_topics.append(f'Review of {last_name}' if last_name else '')
            else:
                week_topics.append('')
        weeks.append({
            'week': idx,
            'date_range': format_week_date_range(days),
            'classes_this_week': rows,
            'topics': week_topics,
        })
        classes_used += rows
    return weeks


def slim_prior_parts(prior_parts, part):
    prior_parts = prior_parts or {}
    if not prior_parts or str(part).upper() in ('A', 'D'):
        return {}
    a = prior_parts.get('A') or {}
    clos = []
    for clo in a.get('clo_data') or []:
        if isinstance(clo, dict):
            clos.append({
                'number': clo.get('number'),
                'description': (clo.get('description') or '')[:120],
            })
    return {'A': {'clo_data': clos}} if clos else {}


def build_outline_prompt(context, part='full', few_shot=True, prior_parts=None, generation_options=None):
    """
    Build system and user prompts.
    part: 'full', 'A', 'B', 'C', 'D', or 'CD'
    """
    from utils.ai.outline_guidelines import build_guidelines_block
    from utils.ai.curriculum_anchor import _syllabus_locked

    part = 'full' if part == 'full' else str(part).upper()
    prompt_context = context if part == 'full' else slim_context_for_part(context, part)
    prior_parts = slim_prior_parts(prior_parts, part)
    context_json = _compact_json(prompt_context)
    guidelines_block = build_guidelines_block(generation_options, part=part)
    anchor = build_curriculum_anchor(context)
    curriculum_rules = curriculum_grounding_rules(anchor, part=part, generation_options=generation_options)
    use_style_examples = few_shot and part == 'full' and not (anchor.get('has_clos') and anchor.get('has_content'))
    locked = _syllabus_locked(generation_options)

    schedule_rules = []
    assessment_rules = []
    if generation_options and part in ('B', 'full'):
        total = generation_options.get('total_classes')
        cpw = generation_options.get('classes_per_week')
        if total and cpw:
            if locked:
                schedule_rules.append(
                    f'- week_slots lists each academic week with date_range, classes_this_week, and syllabus topics '
                    f'({total} classes at {cpw}/week). Date is a week range, never a single day. '
                    'Return ONE object per week in "weeks". Do not invent or rename topics.'
                )
            else:
                schedule_rules.append(
                    f'- week_slots lists each academic week with a date_range, classes_this_week, and syllabus topics '
                    f'({total} classes at {cpw}/week). Date is a week range, never a single day. '
                    'Return ONE object per week in "weeks". topics[] may elaborate week_slots.topics '
                    '(sub-topics or case names) with classes_this_week items; do not add unrelated subjects.'
                )
        plan = generation_options.get('assessment_plan') or []
        if plan:
            breakdown = ', '.join(f'{item["name"]}×{item["count"]}' for item in plan)
            schedule_rules.append(f'- Mention these assessments in teaching_assessment across different weeks: {breakdown}.')

    if generation_options and part in ('C', 'CD', 'full'):
        plan = generation_options.get('assessment_plan') or []
        ac = generation_options.get('assessment_count')
        if plan:
            breakdown = ', '.join(f'{item["name"]}×{item["count"]}' for item in plan)
            assessment_rules.append(f'- assessment_techniques breakdown: {breakdown}.')
        if ac:
            assessment_rules.append(f'- assessment_techniques: exactly {ac} items using those names.')

    if part == 'full':
        schema_json = _compact_json(OUTLINE_JSON_SCHEMA)
        part_label = 'complete course outline (Parts A–D)'
        rules = curriculum_rules + schedule_rules + assessment_rules + [
            '- Write ALL output in English.',
        ]
        few_shot_block = ''
        if use_style_examples:
            examples = {k: FEW_SHOT_BY_PART[k] for k in ('A', 'B', 'C', 'D')}
            few_shot_block = '\n\nSTYLE ONLY:\n' + _compact_json(examples)
    else:
        if part not in OUTLINE_PART_FIELDS:
            raise ValueError(f'Invalid outline part: {part}')
        schema_json = _compact_json(_schema_for_part(part, generation_options))
        part_label = PART_DESCRIPTIONS[part]
        rules = curriculum_rules + schedule_rules + assessment_rules + [
            f'- Generate ONLY the schema keys for {part_label}.',
            '- Write ALL output in English.',
        ]
        if part == 'B':
            if locked:
                rules.append(
                    '- Do not output lesson_plan or course_content_summary. '
                    'Only "weeks" with week, date_range, classes_this_week, outcome, activities, '
                    'teaching_assessment, clo_alignment. Do not invent or rename topics.'
                )
            else:
                rules.append(
                    '- Do not output lesson_plan or course_content_summary. '
                    'Only "weeks" with week, date_range, classes_this_week, topics[], outcome, activities, '
                    'teaching_assessment, clo_alignment. topics[] may elaborate week_slots.topics only.'
                )
            if (generation_options or {}).get('detail_level') == 'detailed':
                rules.append('- Each week: a specific learning outcome and a concrete in-class activity.')
            else:
                rules.append('- Keep outcome/activities to 1–2 short sentences each.')
        if part in ('C', 'CD'):
            rules.append('- assessment_techniques must reference curriculum CLO numbers.')
            rules.append('- Keep every string under 160 characters. Rubric cells: 8 words max.')
        if part in ('D', 'CD'):
            if locked:
                rules.append('- textbooks/references may use uploaded_materials; do not invent curriculum topics or books.')
            else:
                rules.append('- textbooks/references may use uploaded_materials; extra readings must tie to syllabus themes.')
            rules.append('- 4–8 short textbook/reference lines; other_issues: 1–2 sentences each.')
        if part == 'CD':
            rules.append('- Return one compact JSON object. Do not truncate mid-string.')
        few_shot_block = ''
        if use_style_examples and part in FEW_SHOT_BY_PART:
            few_shot_block = f'\n\nSTYLE ONLY for Part {part}:\n' + _compact_json(FEW_SHOT_BY_PART[part])

    prior_block = ''
    if prior_parts:
        prior_block = '\n\nALREADY GENERATED (CLO numbers only):\n' + _compact_json(prior_parts)

    guidelines_section = f'\n\n{guidelines_block}\n' if guidelines_block else ''

    system = (
        f'You are an expert academic course outline author for {current_tenant().display_with_university}. '
        'Return STRICT JSON only. No markdown. English only. Be concise. '
        'Never put raw line breaks inside strings.'
    )
    few_shot_block = _localize_outline_text(few_shot_block)
    user = (
        f'Create {part_label} JSON for this course.\n\n'
        f'CONTEXT:\n{context_json}\n'
        f'{guidelines_section}\n'
        f'SCHEMA:\n{schema_json}\n\n'
        'Rules:\n' + '\n'.join(rules) + few_shot_block + prior_block
    )
    return system, user
