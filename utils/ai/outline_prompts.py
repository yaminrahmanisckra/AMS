"""Prompt templates for full and per-part Course Outline generation."""
import json

from utils.ai.curriculum_anchor import build_curriculum_anchor, curriculum_grounding_rules
from utils.ai.outline_examples import FEW_SHOT_BY_PART

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
        'week': 1,
        'date': 'YYYY-MM-DD or week range',
        'topic': 'string',
        'outcome': 'string',
        'teaching_assessment': 'string',
        'clo_alignment': 'CLO 1',
    }],
    'assessment_strategy': {
        'attendance_percentage': 5,
        'ca_percentage': 35,
        'final_exam_percentage': 60,
        'attendance_marks': 5,
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
    'B': 'Part B — Course content (topics, weekly lesson plan, CIE/SMEE breakdown tables)',
    'C': 'Part C — Assessment (strategy, techniques, rubrics, grading policy, evaluation)',
    'D': 'Part D — Learning resources (textbooks, references, course file components, policies)',
}


def _schema_for_part(part):
    fields = OUTLINE_PART_FIELDS.get(part, [])
    return {key: OUTLINE_JSON_SCHEMA[key] for key in fields if key in OUTLINE_JSON_SCHEMA}


def build_outline_prompt(context, part='full', few_shot=True, prior_parts=None, generation_options=None):
    """
    Build system and user prompts.
    part: 'full', 'A', 'B', 'C', or 'D'
    prior_parts: dict of already-generated part payloads (for continuity in multi-part jobs)
    generation_options: delivery type, language, custom instructions, etc.
    """
    from utils.ai.outline_guidelines import build_guidelines_block

    context_json = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    prior_parts = prior_parts or {}
    guidelines_block = build_guidelines_block(generation_options)
    anchor = build_curriculum_anchor(context)
    curriculum_rules = curriculum_grounding_rules(anchor)
    use_style_examples = few_shot and not (anchor.get('has_clos') and anchor.get('has_content'))

    schedule_rules = []
    if generation_options:
        total = generation_options.get('total_classes')
        cpw = generation_options.get('classes_per_week')
        if total:
            schedule_rules.append(
                f'- lesson_plan: total class sessions MUST equal {total} (teacher-provided semester total).'
            )
        if cpw:
            schedule_rules.append(
                f'- lesson_plan: schedule up to {cpw} class sessions per week (teacher-provided).'
            )
        if total and cpw:
            schedule_rules.append(
                f'- Distribute all curriculum topics across weeks without exceeding {total} total classes '
                f'at ~{cpw} classes/week; include assessment slots within this limit.'
            )
            schedule_rules.append(
                f'- lesson_plan: generate exactly {total} rows (one per class session); '
                f'assign the same week number to up to {cpw} consecutive rows.'
            )
            schedule_rules.append(
                '- Spread assessments across weeks in teaching_assessment: quiz, class test, assignment, '
                'presentation, or discussion — at least one assessment activity every 2–3 weeks; '
                'never schedule all CIE assessments only in the last week.'
            )

    assessment_rules = []
    if generation_options:
        plan = generation_options.get('assessment_plan') or []
        ac = generation_options.get('assessment_count')
        if ac or plan:
            if plan:
                breakdown = ', '.join(f'{item["name"]}×{item["count"]}' for item in plan)
                assessment_rules.append(
                    f'- Assessment plan from teacher: {breakdown} (total {ac}).'
                )
            if ac:
                assessment_rules.append(
                    f'- Part C assessment_techniques: exactly {ac} rows matching this breakdown.'
                )
            assessment_rules.append(
                '- Schedule each assessment in lesson_plan teaching_assessment on different weeks.'
            )

    if part == 'full':
        schema_json = json.dumps(OUTLINE_JSON_SCHEMA, ensure_ascii=False, indent=2)
        part_label = 'complete course outline (Parts A–D)'
        rules = curriculum_rules + schedule_rules + assessment_rules + [
            '- cie_marks + smee_marks should total 100 (typically 40/60).',
            '- lesson_plan weeks must fit between semester_start and semester_end.',
            '- Use realistic assessment_techniques linked to curriculum CLOs.',
            '- Write ALL output in English.',
        ]
        few_shot_block = ''
        if use_style_examples:
            examples = {k: FEW_SHOT_BY_PART[k] for k in ('A', 'B', 'C', 'D')}
            few_shot_block = (
                '\n\nSTYLE ONLY (do NOT copy example topics/CLOs — use curriculum CONTEXT):\n'
                + json.dumps(examples, ensure_ascii=False, indent=2)
            )
    else:
        part = part.upper()
        if part not in OUTLINE_PART_FIELDS:
            raise ValueError(f'Invalid outline part: {part}')
        schema_json = json.dumps(_schema_for_part(part), ensure_ascii=False, indent=2)
        part_label = PART_DESCRIPTIONS[part]
        rules = curriculum_rules + schedule_rules + assessment_rules + [
            f'- Generate ONLY {part_label} fields listed in the schema.',
            '- Do not include fields from other parts.',
            '- Write ALL output in English.',
        ]
        if part == 'B':
            rules.append('- lesson_plan: schedule ONLY curriculum topics from course_content_summary; no new topics.')
            rules.append('- lesson_plan: one row per class session; weave formative assessments into teaching_assessment across different weeks.')
        if part == 'C':
            plan = (generation_options or {}).get('assessment_plan') or []
            ac = (generation_options or {}).get('assessment_count')
            if plan:
                breakdown = ', '.join(f'{item["name"]}×{item["count"]}' for item in plan)
                rules.append(f'- assessment_techniques breakdown: {breakdown}.')
            if ac:
                rules.append(
                    f'- assessment_techniques: generate exactly {ac} items using teacher-specified names and counts.'
                )
            rules.append('- assessment_techniques must reference CLOs from Part A (curriculum CLOs).')
        if part == 'D':
            rules.append('- textbooks/references may use uploaded_materials; do not invent curriculum topics.')
        if part == 'B' and prior_parts.get('A'):
            rules.append('- lesson_plan clo_alignment must use CLO numbers from Part A.')
        few_shot_block = ''
        if use_style_examples and part in FEW_SHOT_BY_PART:
            few_shot_block = (
                f'\n\nSTYLE ONLY for Part {part} (do NOT copy example content):\n'
                + json.dumps(FEW_SHOT_BY_PART[part], ensure_ascii=False, indent=2)
            )

    prior_block = ''
    if prior_parts:
        prior_block = (
            '\n\nALREADY GENERATED (keep consistent with these):\n'
            + json.dumps(prior_parts, ensure_ascii=False, indent=2, default=str)
        )

    guidelines_section = ''
    if guidelines_block:
        guidelines_section = f'\n\n{guidelines_block}\n'

    system = (
        'You are an expert academic course outline author for Khulna University Law Discipline. '
        'Generate course outline content as STRICT JSON only. '
        'CURRICULUM DATA IS MANDATORY: rationale, CLOs, and course content must come from CONTEXT — never invent substitutes. '
        'Use academic calendar dates for lesson_plan scheduling. '
        'Write ALL outline content in English. '
        'Follow GENERATION GUIDELINES when present. '
        'Return ONLY valid JSON matching the schema keys. No markdown fences.'
    )
    user = (
        f'Create {part_label} JSON for this course.\n\n'
        f'CONTEXT:\n{context_json}\n'
        f'{guidelines_section}\n'
        f'REQUIRED JSON SHAPE (example types):\n{schema_json}\n\n'
        'Rules:\n' + '\n'.join(rules) + few_shot_block + prior_block
    )
    return system, user
