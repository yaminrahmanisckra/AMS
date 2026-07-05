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
    'standard': 'স্ট্যান্ডার্ড — KU Law Discipline সাধারণ ফরম্যাট',
    'detailed': 'বিস্তারিত — প্রতিটি সপ্তাহে বেশি কার্যক্রম ও উদাহরণ',
}

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
            'এটি **Sessional (ব্যবহারিক/ক্লিনিক্যাল)** কোর্স — Theory কোর্সের মতো লিখবেন না।',
            'মূল ফোকাস: হাতে-কলমে কাজ, মূল্যায়ন রিপোর্ট, ভাইভা, ফিল্ড/ল্যাব/ক্লিনিক অভিজ্ঞতা।',
            'Part C-তে sessional_report ও sessional_viva ভিত্তিক মূল্যায়ন স্পষ্ট করুন (যেমন: রিপোর্ট ৬০, ভাইভা ৩০, উপস্থিতি ১০)।',
            'lesson_plan-এ প্রতি সপ্তাহে practical exercise, demonstration, field visit, বা clinic activity উল্লেখ করুন।',
            'লেকচার-ভিত্তিক দীর্ঘ theory chapter তালিকা এড়িয়ে কাজ-ভিত্তিক সেশন পরিকল্পনা দিন।',
            'textbooks-এ practical manual, guideline, বা hands-on resource যোগ করুন।',
        ]
    return [
        'এটি **Theory** কোর্স — ক্লাসরুম লেকচার, আলোচনা, ও লিখিত পরীক্ষা-কেন্দ্রিক আউটলাইন।',
        'Part A: contact hours লেকচার + discussion হিসাবে লিখুন; CIE ৪০ / SMEE ৬০ (বা কারিকুলাম অনুযায়ী)।',
        'Part B: সপ্তাহভিত্তিক lesson_plan-এ topic, reading, teaching method, formative assessment থাকবে।',
        'Part B: প্রতিটি ক্লাস সেশন = lesson_plan-এ এক সারি; সপ্তাহে classes_per_week পর্যন্ত সারি একই week নম্বরে।',
        'Part B: quiz, class test, assignment, presentation বিভিন্ন সপ্তাহে teaching_assessment-এ ছড়িয়ে দিন — শেষ সপ্তাহে সব নয়।',
        'Part C: class test, assignment, attendance, final written exam — CLO-এর সাথে ম্যাপ করুন।',
        'Sessional report/viva শুধু Sessional কোর্সে প্রযোজ্য; Theory-তে ব্যবহার করবেন না।',
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
        'total_classes': _pos_int('total_classes'),
        'classes_per_week': _pos_int('classes_per_week'),
        'assessment_plan': assessment_plan,
        'assessment_count': assessment_count,
        'assessment_types': assessment_types,
    }


def build_guidelines_block(options):
    """Text block injected into AI prompts."""
    if not options:
        return ''

    delivery = options.get('delivery_type', DELIVERY_THEORY)
    lines = [
        '=== GENERATION GUIDELINES (follow strictly) ===',
        f'Course delivery mode: {delivery.upper()}',
        'Language: English only (all outline text, headings, lesson plan, and assessment descriptions).',
        f'Detail level: {DETAIL_OPTIONS.get(options.get("detail_level"), options.get("detail_level"))}',
    ]
    if options.get('delivery_type_detected') and options['delivery_type_detected'] != delivery:
        lines.append(
            f'Note: session default is {options["delivery_type_detected"]}; teacher overrode to {delivery}.'
        )

    lines.append('')
    lines.append('Delivery-specific rules:')
    lines.extend(f'- {rule}' for rule in builtin_delivery_guidelines(delivery))

    assessment_count = options.get('assessment_count')
    assessment_plan = options.get('assessment_plan') or []
    if assessment_count or assessment_plan:
        lines.append('')
        lines.append('Teacher-specified assessments (MANDATORY for Part C and lesson_plan):')
        if assessment_plan:
            for item in assessment_plan:
                lines.append(f'- {item["name"]} × {item["count"]}')
        if assessment_count:
            lines.append(f'- Total formative/CIE assessments: {assessment_count}')
        lines.append(
            f'- assessment_techniques must list exactly {assessment_count} items matching the breakdown above.'
        )
        lines.append('- Schedule each assessment instance in lesson_plan teaching_assessment on different weeks.')
        lines.append('- Use the exact assessment names from the teacher plan (including custom types).')

    total_classes = options.get('total_classes')
    classes_per_week = options.get('classes_per_week')
    if total_classes or classes_per_week:
        lines.append('')
        lines.append('Teacher-provided class schedule (MANDATORY for lesson_plan):')
        if total_classes:
            lines.append(f'- Total classes in semester: {total_classes}')
        if classes_per_week:
            lines.append(f'- Classes per week: {classes_per_week}')
        lines.append('- lesson_plan MUST use exactly these numbers; distribute curriculum topics across weeks accordingly.')
        lines.append('- One lesson_plan row = one class session; same week number for up to classes_per_week rows.')
        lines.append('- Spread quiz/class test/assignment/presentation across different weeks in teaching_assessment (not all in final week).')
        if assessment_plan:
            type_labels = [f'{item["name"]}×{item["count"]}' for item in assessment_plan]
            lines.append(f'- Assessment breakdown for lesson_plan: {", ".join(type_labels)}.')
        lines.append('- Do not exceed total_classes; fit all topic classes + assessments within this limit.')

    custom = (options.get('custom_instructions') or '').strip()
    if custom:
        lines.append('')
        lines.append('Additional instructions from teacher/admin:')
        lines.append(custom)

    lines.append('=== END GUIDELINES ===')
    return '\n'.join(lines)


def preset_instructions(delivery_type):
    """Quick-fill templates for the generation modal."""
    if delivery_type == DELIVERY_SESSIONAL:
        return (
            'প্রতি সপ্তাহে অন্তত একটি hands-on কার্যক্রম লিখুন।\n'
            'মূল্যায়ন: Sessional Report ৬০, Sessional Viva ৩০, Attendance ১০।\n'
            'রুব্রিক্স practical skill ও presentation-এর উপর ভিত্তি করে হবে।\n'
            'বাংলা আইনি প্রসঙ্গে উদাহরণ দিন যেখানে প্রাসঙ্গিক।'
        )
    return (
        'সপ্তাহভিত্তিক lesson plan ক্যালেন্ডারের working days মেনে চলবে।\n'
        'প্রতি ক্লাস সেশন = lesson plan-এ এক সারি; সপ্তাহে classes_per_week পর্যন্ত একই week।\n'
        'quiz, class test, assignment বিভিন্ন সপ্তাহে teaching_assessment-এ ছড়িয়ে দিন — শেষ সপ্তাহে সব নয়।\n'
        'CIE ৪০ + SMEE ৬০; assessment_techniques প্রতিটি CLO-র সাথে লিংক করুন।\n'
        'কোর্স কন্টেন্ট কারিকুলামের topic তালিকা অনুসরণ করবে।\n'
        'ল্যান্ডমার্ক case ও Bangladesh context যোগ করুন।'
    )
