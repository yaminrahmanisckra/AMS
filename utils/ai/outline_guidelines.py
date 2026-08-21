"""Customizable generation guidelines for Theory vs Sessional course outlines."""
import json
import os

from flask import current_app

DELIVERY_THEORY = 'theory'
DELIVERY_SESSIONAL = 'sessional'

LANGUAGE_OPTIONS = {
    'en': 'ইংরেজি (আন্তর্জাতিক একাডেমিক স্টাইল)',
    'bn': 'বাংলা (সহজ বাংলায় লিখুন)',
    'mixed': 'মিশ্র (শিরোনাম ইংরেজি, ব্যাখ্যা বাংলা)',
}

DETAIL_OPTIONS = {
    'concise': 'সংক্ষিপ্ত — মূল বিষয়, কম বিস্তারিত',
    'standard': 'স্ট্যান্ডার্ড — {discipline} সাধারণ ফরম্যাট',
    'detailed': 'বিস্তারিত — প্রতিটি সপ্তাহে বেশি কার্যক্রম ও উদাহরণ',
}


def _detail_option_label(key):
    from utils.tenant import current_tenant
    raw = DETAIL_OPTIONS.get(key, key)
    if isinstance(raw, str) and '{discipline}' in raw:
        return raw.format(discipline=current_tenant().name)
    return raw

ASSESSMENT_TYPE_OPTIONS = {
    'class_test': 'Class Test',
    'quiz': 'Quiz',
    'assignment': 'Assignment',
    'presentation': 'Presentation',
    'term_paper': 'Term Paper',
    'case_brief': 'Case Brief / Case Analysis',
    'sessional_report': 'Sessional Report',
    'viva': 'Viva',
}

DEFAULT_ASSESSMENT_COUNT = {
    DELIVERY_THEORY: 4,
    DELIVERY_SESSIONAL: 3,
}

DEFAULT_ASSESSMENT_PLAN = {
    DELIVERY_THEORY: [
        {'type': 'class_test', 'name': 'Class Test', 'count': 2},
        {'type': 'quiz', 'name': 'Quiz', 'count': 1},
        {'type': 'assignment', 'name': 'Assignment', 'count': 1},
    ],
    DELIVERY_SESSIONAL: [
        {'type': 'sessional_report', 'name': 'Sessional Report', 'count': 1},
        {'type': 'viva', 'name': 'Viva', 'count': 1},
        {'type': 'presentation', 'name': 'Presentation', 'count': 1},
    ],
}

INTENT_CHIP_OPTIONS = {
    'class_test': {'label': 'Class Test', 'kind': 'assessment', 'type': 'class_test'},
    'quiz': {'label': 'Quiz', 'kind': 'assessment', 'type': 'quiz'},
    'assignment': {'label': 'Assignment', 'kind': 'assessment', 'type': 'assignment'},
    'presentation': {'label': 'Presentation', 'kind': 'assessment', 'type': 'presentation'},
    'viva': {'label': 'Viva', 'kind': 'assessment', 'type': 'viva'},
    'weekly_discussion': {'label': 'প্রতি সপ্তাহে discussion', 'kind': 'style'},
    'bangladesh_context': {'label': 'Bangladesh context', 'kind': 'style'},
    'landmark_cases': {'label': 'Landmark cases', 'kind': 'expand'},
    'practical_clinic': {'label': 'Practical / clinic', 'kind': 'style'},
    'spread_assessments': {'label': 'মূল্যায়ন ছড়িয়ে দাও', 'kind': 'style'},
}

INTENT_CHIP_RULES = {
    'weekly_discussion': 'Include a class discussion activity each week.',
    'bangladesh_context': 'Use Bangladesh legal or academic context in examples.',
    'landmark_cases_locked': 'Mention landmark cases only as examples of existing syllabus topics; do not add new topics.',
    'landmark_cases': 'You may add landmark case names as elaborations of syllabus topics.',
    'practical_clinic': 'Include practical, clinic, or field activities.',
    'spread_assessments': 'Spread assessments across the semester; do not cluster them in the last weeks.',
}


def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ('0', 'false', 'off', 'no'):
        return False
    if text in ('1', 'true', 'on', 'yes'):
        return True
    return default


def normalize_intent_chips(raw_chips):
    allowed = set(INTENT_CHIP_OPTIONS)
    out = []
    seen = set()
    for item in raw_chips or []:
        key = str(item or '').strip().lower()
        if key in allowed and key not in seen:
            out.append(key)
            seen.add(key)
        if len(out) >= 20:
            break
    return out


def normalize_assessment_plan(raw_plan=None, delivery=DELIVERY_THEORY):
    """Parse teacher assessment plan: type, display name, count per type."""
    plan = []
    for item in raw_plan or []:
        if not isinstance(item, dict):
            continue
        try:
            count = int(item.get('count', 1) or 1)
        except (TypeError, ValueError):
            count = 1
        count = max(1, min(count, 12))
        type_key = (item.get('type') or '').strip().lower()
        name = (item.get('name') or '').strip()
        if type_key == 'custom':
            if not name:
                continue
        elif type_key in ASSESSMENT_TYPE_OPTIONS:
            name = name or ASSESSMENT_TYPE_OPTIONS[type_key]
        elif name:
            type_key = 'custom'
        else:
            continue
        plan.append({'type': type_key, 'name': name, 'count': count})
    if not plan:
        plan = [dict(x) for x in DEFAULT_ASSESSMENT_PLAN.get(delivery, DEFAULT_ASSESSMENT_PLAN[DELIVERY_THEORY])]
    return plan


def assessment_plan_summary(plan):
    """Expand plan to flat type list and total count."""
    total = sum(item.get('count', 0) for item in plan)
    expanded = []
    for item in plan:
        expanded.extend([item['name']] * int(item.get('count', 1)))
    return total, expanded


def _defaults_path():
    try:
        base = current_app.root_path
    except RuntimeError:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    return os.path.join(base, 'instance', 'ai_outline_defaults.json')


def load_admin_defaults():
    """Department-wide default instructions (editable in Admin → AI Settings)."""
    path = _defaults_path()
    if not os.path.exists(path):
        return {'theory': '', 'sessional': '', 'global': ''}
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return {
                'theory': (data.get('theory') or '').strip(),
                'sessional': (data.get('sessional') or '').strip(),
                'global': (data.get('global') or '').strip(),
            }
    except (json.JSONDecodeError, OSError, TypeError):
        pass
    return {'theory': '', 'sessional': '', 'global': ''}


def save_admin_defaults(theory='', sessional='', global_notes=''):
    path = _defaults_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        'theory': (theory or '').strip(),
        'sessional': (sessional or '').strip(),
        'global': (global_notes or '').strip(),
    }
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return payload


def builtin_delivery_guidelines(delivery_type):
    """Built-in rules that differ between Theory and Sessional courses."""
    if delivery_type == DELIVERY_SESSIONAL:
        return [
            'Sessional course: practical/clinic/field work, reports, viva — not lecture-heavy theory.',
            'Marks: Attendance 10, CA 60, Viva 30.',
        ]
    return [
        'Theory course: lecture, discussion, written exam.',
        'CIE 40 / SMEE 60 unless the curriculum says otherwise.',
    ]


def normalize_generation_options(raw=None, session=None, course_data=None):
    """Merge request options with session type and admin defaults."""
    raw = raw if isinstance(raw, dict) else {}
    admin = load_admin_defaults()

    detected = (getattr(session, 'course_type', None) or '').strip().lower()
    if detected not in (DELIVERY_THEORY, DELIVERY_SESSIONAL):
        curriculum_type = (getattr(course_data, 'course_type', None) or '').strip().lower()
        if 'sessional' in curriculum_type or 'practical' in curriculum_type:
            detected = DELIVERY_SESSIONAL
        else:
            detected = DELIVERY_THEORY

    delivery = (raw.get('delivery_type') or detected or DELIVERY_THEORY).strip().lower()
    if delivery not in (DELIVERY_THEORY, DELIVERY_SESSIONAL):
        delivery = DELIVERY_THEORY

    language = 'en'

    detail = (raw.get('detail_level') or 'standard').strip().lower()
    if detail not in DETAIL_OPTIONS:
        detail = 'standard'

    custom = (raw.get('custom_instructions') or '').strip()
    use_admin_defaults = raw.get('use_admin_defaults', True)
    if use_admin_defaults is False:
        admin_block = ''
    else:
        parts = [admin.get('global', '')]
        parts.append(admin.get(delivery, ''))
        admin_block = '\n'.join(p for p in parts if p).strip()

    merged_custom = '\n\n'.join(p for p in (admin_block, custom) if p).strip()
    syllabus_lock = _as_bool(raw.get('syllabus_lock', True), default=True)
    intent_chips = normalize_intent_chips(raw.get('intent_chips'))

    def _pos_int(key):
        try:
            val = int(raw.get(key))
            return val if val > 0 else None
        except (TypeError, ValueError):
            return None

    allowed_types = set(ASSESSMENT_TYPE_OPTIONS.keys())
    raw_plan = raw.get('assessment_plan')
    if not raw_plan and raw.get('assessment_types'):
        raw_plan = [{'type': t, 'count': 1} for t in raw.get('assessment_types') or [] if str(t).strip() in allowed_types]
    if not raw_plan:
        chip_plan = []
        for chip in intent_chips:
            meta = INTENT_CHIP_OPTIONS.get(chip) or {}
            if meta.get('kind') == 'assessment' and meta.get('type') in allowed_types:
                chip_plan.append({'type': meta['type'], 'count': 1})
        if chip_plan:
            raw_plan = chip_plan
    assessment_plan = normalize_assessment_plan(raw_plan, delivery=delivery)
    assessment_count, assessment_types = assessment_plan_summary(assessment_plan)

    return {
        'delivery_type': delivery,
        'delivery_type_detected': detected,
        'language': language,
        'detail_level': detail,
        'custom_instructions': merged_custom,
        'teacher_custom_only': custom,
        'use_admin_defaults': bool(use_admin_defaults),
        'syllabus_lock': syllabus_lock,
        'intent_chips': intent_chips,
        'total_classes': _pos_int('total_classes'),
        'classes_per_week': _pos_int('classes_per_week'),
        'assessment_plan': assessment_plan,
        'assessment_count': assessment_count,
        'assessment_types': assessment_types,
    }


def build_guidelines_block(options, part=None):
    """Text block injected into AI prompts. Keep short; part-specific."""
    if not options:
        return ''

    part = (part or '').upper()
    delivery = options.get('delivery_type', DELIVERY_THEORY)
    locked = _as_bool(options.get('syllabus_lock', True), default=True)
    lines = [
        f'Mode: {delivery.upper()}. Language: English. Detail: {options.get("detail_level") or "standard"}.',
        'Syllabus lock: ON — use curriculum topics only.' if locked else
        'Syllabus lock: OFF — you may elaborate syllabus topics with sub-topics or cases; do not add unrelated subjects.',
    ]
    if part in ('', 'FULL', 'B', 'C', 'CD'):
        for rule in builtin_delivery_guidelines(delivery):
            lines.append(f'- {rule}')

    chips = options.get('intent_chips') or []
    chip_lines = []
    for chip in chips:
        if chip == 'landmark_cases':
            chip_lines.append(INTENT_CHIP_RULES['landmark_cases_locked' if locked else 'landmark_cases'])
        elif chip in INTENT_CHIP_RULES:
            chip_lines.append(INTENT_CHIP_RULES[chip])
    if chip_lines:
        lines.append('Teacher intent:')
        for rule in chip_lines:
            lines.append(f'- {rule}')

    if part in ('', 'FULL', 'C', 'CD'):
        assessment_count = options.get('assessment_count')
        assessment_plan = options.get('assessment_plan') or []
        if assessment_plan:
            lines.append('Assessments: ' + ', '.join(f'{item["name"]}×{item["count"]}' for item in assessment_plan))
        if assessment_count:
            lines.append(f'assessment_techniques must have exactly {assessment_count} items.')

    if part in ('', 'FULL', 'B'):
        total_classes = options.get('total_classes')
        classes_per_week = options.get('classes_per_week')
        if total_classes or classes_per_week:
            bits = []
            if total_classes:
                bits.append(f'{total_classes} classes')
            if classes_per_week:
                bits.append(f'{classes_per_week}/week')
            lines.append(
                'Schedule: ' + ', '.join(bits)
                + '. Date field is the week range (e.g. 20-24 July 2025), not a single day. '
                'Each week has classes_per_week rows sharing that range.'
            )

    custom = (options.get('custom_instructions') or '').strip()
    if custom:
        lines.append('Extra instructions:')
        lines.append(custom[:1200])

    return '\n'.join(lines)


def preset_instructions(delivery_type):
    """Quick-fill templates for the generation modal (no extra-content injection)."""
    if delivery_type == DELIVERY_SESSIONAL:
        return (
            'প্রতি সপ্তাহে অন্তত একটি hands-on কার্যক্রম লিখুন।\n'
            'মূল্যায়ন: Sessional Report ৬০, Sessional Viva ৩০, Attendance ১০।\n'
            'রুব্রিক্স practical skill ও presentation-এর উপর ভিত্তি করে হবে।'
        )
    return (
        'সপ্তাহভিত্তিক lesson plan ক্যালেন্ডারের working days মেনে চলবে।\n'
        'Date ফিল্ডে সপ্তাহের রেঞ্জ থাকবে (যেমন 20-24 July 2025), নির্দিষ্ট এক দিন নয়।\n'
        'প্রতি ক্লাস সেশন = lesson plan-এ এক সারি; সপ্তাহে classes_per_week পর্যন্ত একই date range।\n'
        'quiz, class test, assignment বিভিন্ন সপ্তাহে teaching_assessment-এ ছড়িয়ে দিন — শেষ সপ্তাহে সব নয়।\n'
        'CIE ৪০ + SMEE ৬০; assessment_techniques প্রতিটি CLO-র সাথে লিংক করুন।\n'
        'কোর্স কন্টেন্ট কারিকুলামের topic তালিকা অনুসরণ করবে।'
    )
