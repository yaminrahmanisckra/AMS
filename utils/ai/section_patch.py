"""In-place AI patches: understand the teacher, then edit the form."""
import json
import re

from utils.ai.client import AIClientError, generate_outline_json_with_meta
from utils.ai.outline_parser import extract_json_from_response
from utils.ai.session_utils import reset_db_session
from utils.tenant import current_tenant

PATCH_SECTIONS = {
    'overview': {
        'keys': ('course_summary', 'prerequisites', 'clo_data'),
        'lock_topics': False,
    },
    'lesson_plan': {'keys': ('lesson_plan',), 'lock_topics': True},
    'assessment_techniques': {'keys': ('assessment_techniques',), 'lock_topics': False},
    'cie': {'keys': ('cie_breakdown',), 'lock_topics': False},
    'smee': {'keys': ('smee_breakdown',), 'lock_topics': False},
    'assessment': {
        'keys': (
            'assessment_strategy', 'rubrics', 'grading_policy',
            'make_up_procedures', 'other_issues',
        ),
        'lock_topics': False,
    },
    'resources': {
        'keys': (
            'textbooks', 'reference_books', 'other_resources',
            'course_file_components',
        ),
        'lock_topics': False,
    },
}

_OTHER_ISSUE_FIELDS = (
    'class_discussion', 'general_expectations', 'communication', 'academic_honesty',
)

_RESOURCE_FIELDS = (
    'textbooks', 'reference_books', 'other_resources', 'course_file_components',
)

_OVERVIEW_FIELDS = ('course_summary', 'prerequisites', 'clo_data')

_LESSON_TEXT_FIELDS = ('outcome', 'activities', 'teaching_assessment', 'clo_alignment')

_ASSESS_HINTS = (
    (re.compile(r'quiz|কুইজ', re.I), 'Quiz'),
    (re.compile(r'class\s*test|ক্লাস\s*টেস্ট|ক্লাসটেস্ট', re.I), 'Class Test'),
    (re.compile(r'assignment|অ্যাসাইনমেন্ট|এসাইনমেন্ট|অ্যাসাইনমেন্ট', re.I), 'Assignment'),
    (re.compile(r'presentation|প্রেজেন্টেশন|উপস্থাপনা', re.I), 'Presentation'),
    (re.compile(r'viva|ভাইভা|মৌখিক', re.I), 'Viva'),
    (re.compile(r'discussion|ডিসকাশন|আলোচনা', re.I), 'Discussion'),
)

# Most-specific aliases first. Maps spoken/written names to a form field + section.
_FIELD_ALIASES = (
    (re.compile(r'academic honesty|একাডেমিক হনেস্টি|একাডেমিক সততা|\bhonesty\b|সততা নীতি', re.I),
     'academic_honesty', 'assessment'),
    (re.compile(r'general expectations|সাধারণ প্রত্যাশা', re.I),
     'general_expectations', 'assessment'),
    (re.compile(r'class discussion|participation|ক্লাস ডিসকাশন|অংশগ্রহণ', re.I),
     'class_discussion', 'assessment'),
    (re.compile(r'communication with|course teachers|শিক্ষকের সাথে যোগাযোগ|যোগাযোগ', re.I),
     'communication', 'assessment'),
    (re.compile(r'other issues|অন্যান্য বিষয়', re.I),
     'other_issues', 'assessment'),
    (re.compile(r'reference books?|রেফারেন্স বই', re.I),
     'reference_books', 'resources'),
    (re.compile(r'textbooks?|পাঠ্যবই|বইয়ের তালিকা', re.I),
     'textbooks', 'resources'),
    (re.compile(r'other resources|অন্যান্য রিসোর্স|অনলাইন রিসোর্স', re.I),
     'other_resources', 'resources'),
    (re.compile(r'course file|কোর্স ফাইল', re.I),
     'course_file_components', 'resources'),
    (re.compile(r'course summary|কোর্স সামারি|কোর্সের সারাংশ|rationale|সারাংশ লিখ', re.I),
     'course_summary', 'overview'),
    (re.compile(r'prerequisite|পূর্বশর্ত', re.I),
     'prerequisites', 'overview'),
    (re.compile(r'clo\s*alignment|ক্লো ম্যাপিং', re.I),
     'clo_alignment', 'lesson_plan'),
    (re.compile(r'course learning outcomes?|\bclos?\b(?!\s*alignment)|লার্নিং আউটকাম', re.I),
     'clo_data', 'overview'),
    (re.compile(r'make[- ]?up|মেকআপ', re.I),
     'make_up_procedures', 'assessment'),
    (re.compile(r'grading policy|গ্রেডিং', re.I),
     'grading_policy', 'assessment'),
    (re.compile(r'rubrics?|রুব্রিক', re.I),
     'rubrics', 'assessment'),
    (re.compile(r'assessment technique', re.I),
     'assessment_techniques', 'assessment_techniques'),
    (re.compile(r'\bcie\b', re.I),
     'cie_breakdown', 'cie'),
    (re.compile(r'\bsmee\b', re.I),
     'smee_breakdown', 'smee'),
    (re.compile(r'আউটকাম|(?<!learning )(?<!learning-)(?<!lesson )\boutcomes?\b', re.I),
     'outcome', 'lesson_plan'),
    (re.compile(r'অ্যাকটিভিটি|\bactivities\b|শ্রেণিকক্ষের কাজ', re.I),
     'activities', 'lesson_plan'),
    (re.compile(r'teaching.?assessment|শিক্ষণ.?মূল্যায়ন', re.I),
     'teaching_assessment', 'lesson_plan'),
)

_REWRITE_FIELDS = (
    set(_LESSON_TEXT_FIELDS)
    | set(_OTHER_ISSUE_FIELDS)
    | set(_RESOURCE_FIELDS)
    | set(_OVERVIEW_FIELDS)
    | {
        'other_issues', 'assessment_techniques', 'cie_breakdown', 'smee_breakdown',
        'assessment_strategy', 'rubrics', 'grading_policy', 'make_up_procedures',
    }
)

_PART_A_HINT = re.compile(
    r'part\s*a|পার্ট\s*a|course summary|কোর্স সামারি|prerequisite|পূর্বশর্ত',
    re.I,
)
_PART_C_HINT = re.compile(
    r'part\s*c|পার্ট\s*c|'
    r'other issues|অন্যান্য বিষয়|'
    r'class discussion|participation|'
    r'general expectations|সাধারণ প্রত্যাশা|'
    r'communication with|academic honesty|একাডেমিক হনেস্টি',
    re.I,
)
_PART_D_HINT = re.compile(
    r'part\s*d|পার্ট\s*d|'
    r'textbooks?|reference books?|other resources|course file|'
    r'বইয়ের তালিকা|পাঠ্যবই',
    re.I,
)
_LESSON_WEEK_HINT = re.compile(r'(?:week|সপ্তাহ)\s*[:\-–]?\s*\d|lesson plan', re.I)
_EMPTY_ONLY_HINT = re.compile(
    r'খালি|empty|blank|যা নেই|যা খালি|শুধু খালি|fill empty|only empty|missing',
    re.I,
)
_CONCISE_HINT = re.compile(r'সংক্ষেপে|brief|concise|short|ছোট করে', re.I)
_DETAILED_HINT = re.compile(r'বিস্তারিত|detailed|elaborate|দীর্ঘ|বড় করে', re.I)
_ONLY_HINT = re.compile(r'শুধু|শুধুমাত্র|\bonly\b|কেবল', re.I)

_MAX_INSTRUCTION = 1200


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str)


def _slice_current(current, keys):
    out = {}
    current = current if isinstance(current, dict) else {}
    for key in keys:
        if key in current:
            out[key] = current[key]
    return out


def _week_num(value):
    match = re.search(r'(\d+)', str(value or ''))
    return int(match.group(1)) if match else None


def _as_int_list(values):
    out = []
    for item in values or []:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            out.append(item)
            continue
        num = _week_num(item)
        if num:
            out.append(num)
    return out


def _week_catalog(plan):
    seen = []
    used = set()
    for row in plan or []:
        if not isinstance(row, dict):
            continue
        num = _week_num(row.get('week'))
        if not num or num in used:
            continue
        used.add(num)
        seen.append({'week': num, 'topic': (row.get('topic') or '')[:90]})
    return seen


def _plan_weeks(plan):
    return sorted({n for n in (_week_num(row.get('week')) for row in plan or [] if isinstance(row, dict)) if n})


def _append_label(text, label):
    current = (text or '').strip()
    if not label:
        return current
    if re.search(r'(?:^|[,;/ ]|\b)' + re.escape(label) + r'(?:\b|$|[,;/ ])', current, re.I):
        return current
    return (current + ', ' + label).strip(', ') if current else label


def _named_fields(text):
    """Exact form fields named in the instruction, most specific first."""
    found = []
    seen = set()
    for pattern, field, _section in _FIELD_ALIASES:
        if field in seen:
            continue
        if pattern.search(text or ''):
            seen.add(field)
            found.append(field)
    return found


def _section_for_field(field):
    for _pattern, name, section in _FIELD_ALIASES:
        if name == field:
            return section
    if field in PATCH_SECTIONS:
        return field
    if field in _OTHER_ISSUE_FIELDS or field == 'other_issues':
        return 'assessment'
    if field in _RESOURCE_FIELDS:
        return 'resources'
    if field in _OVERVIEW_FIELDS:
        return 'overview'
    if field in _LESSON_TEXT_FIELDS:
        return 'lesson_plan'
    return None


def _explicit_section_from_text(text):
    """Map an instruction to a form section when the teacher names it."""
    t = text or ''
    if re.search(r'part\s*d|পার্ট\s*d', t, re.I):
        return 'resources'
    if re.search(r'part\s*c|পার্ট\s*c', t, re.I):
        return 'assessment'
    if re.search(r'part\s*a|পার্ট\s*a', t, re.I):
        return 'overview'
    named = _named_fields(t)
    if named:
        mapped = _section_for_field(named[0])
        if mapped and not (_LESSON_WEEK_HINT.search(t) and mapped != 'lesson_plan'):
            if mapped == 'lesson_plan' and _PART_C_HINT.search(t):
                return 'assessment'
            return mapped
    if _PART_C_HINT.search(t) and not _LESSON_WEEK_HINT.search(t):
        return 'assessment'
    if _PART_D_HINT.search(t) and not re.search(r'part\s*c', t, re.I):
        return 'resources'
    if _PART_A_HINT.search(t) and not _LESSON_WEEK_HINT.search(t):
        return 'overview'
    if re.search(r'\bcie\b', t, re.I) and not re.search(r'part\s*[acd]', t, re.I):
        return 'cie'
    if re.search(r'\bsmee\b', t, re.I) and not re.search(r'part\s*[acd]', t, re.I):
        return 'smee'
    if re.search(r'assessment technique', t, re.I):
        return 'assessment_techniques'
    if _LESSON_WEEK_HINT.search(t) and not re.search(r'part\s*[acd]', t, re.I):
        return 'lesson_plan'
    return None


def _mentions_other_issues(text):
    return bool(re.search(
        r'class discussion|participation|general expectations|'
        r'communication with|academic honesty|other issues|'
        r'একাডেমিক হনেস্টি|সাধারণ প্রত্যাশা',
        text or '',
        re.I,
    ))


def _wants_empty_only(text):
    return bool(_EMPTY_ONLY_HINT.search(text or ''))


def _style_hint(text):
    if _CONCISE_HINT.search(text or ''):
        return 'concise'
    if _DETAILED_HINT.search(text or ''):
        return 'detailed'
    return 'standard'


def _resolve_section(instruction, requested, model_section=None):
    """Prefer a named part/field; otherwise keep the teacher's dropdown."""
    explicit = _explicit_section_from_text(instruction)
    requested = (requested or '').strip().lower()
    guessed = (model_section or '').strip().lower()
    if explicit:
        return explicit
    if requested in PATCH_SECTIONS:
        if guessed == 'lesson_plan' and requested != 'lesson_plan' and not _LESSON_WEEK_HINT.search(instruction or ''):
            return requested
        if guessed in PATCH_SECTIONS and guessed != requested:
            # Model may guess, but without an explicit cue keep the dropdown.
            return requested
        return requested
    if guessed in PATCH_SECTIONS:
        return guessed
    return 'lesson_plan'


def _other_issue_targets(fields, instruction):
    named = [f for f in (fields or []) if f in _OTHER_ISSUE_FIELDS]
    if named:
        return named
    from_text = [f for f in _named_fields(instruction) if f in _OTHER_ISSUE_FIELDS]
    if from_text:
        return from_text
    if 'other_issues' in (fields or []) or _mentions_other_issues(instruction):
        return list(_OTHER_ISSUE_FIELDS)
    return []


def _keys_for_rewrite(section, fields):
    spec_keys = list(PATCH_SECTIONS[section]['keys'])
    if not fields:
        return spec_keys
    mapped = []
    for field in fields:
        key = 'other_issues' if field in _OTHER_ISSUE_FIELDS else field
        if key == 'clo_data' and section == 'overview':
            key = 'clo_data'
        if key in spec_keys and key not in mapped:
            mapped.append(key)
    return mapped or spec_keys


def _parse_json_obj(text):
    raw = extract_json_from_response(text or '')
    if isinstance(raw, dict):
        return raw
    raise ValueError('AI-এর উত্তর ব্যবহারযোগ্য JSON ছিল না। আবার প্রয়োগ চাপুন।')


def _call_json(system, user, max_tokens):
    reset_db_session()
    meta = generate_outline_json_with_meta(system, user, max_tokens=max_tokens)
    reset_db_session()
    return _parse_json_obj(meta.get('text') or ''), meta


def _context_block(context):
    context = context if isinstance(context, dict) else {}
    code = (context.get('course_code') or '').strip()
    title = (context.get('course_title') or '').strip()
    summary = (context.get('course_summary') or '').strip()[:700]
    clos = context.get('clos') or []
    topics = context.get('topics') or []
    lines = []
    if code or title:
        lines.append(f'Course: {code} {title}'.strip())
    if summary:
        lines.append(f'Summary: {summary}')
    if clos:
        lines.append('CLOs: ' + ' | '.join(str(x)[:140] for x in clos[:8]))
    if topics:
        lines.append('Sample topics: ' + ' | '.join(str(x)[:80] for x in topics[:8]))
    return '\n'.join(lines)


def _fallback_rewrite_fields(section, text):
    named = _named_fields(text)
    scoped = [f for f in named if _section_for_field(f) == section]
    if scoped:
        return scoped
    if section == 'assessment' and _mentions_other_issues(text):
        return _other_issue_targets([], text) or ['other_issues']
    if section == 'assessment':
        return ['other_issues'] if re.search(r'পূরণ|fill|লিখ', text or '', re.I) else list(PATCH_SECTIONS['assessment']['keys'])
    if section == 'resources':
        return list(PATCH_SECTIONS['resources']['keys'])
    if section == 'overview':
        return ['course_summary'] if not named else scoped
    if section == 'cie':
        return ['cie_breakdown']
    if section == 'smee':
        return ['smee_breakdown']
    if section == 'assessment_techniques':
        return ['assessment_techniques']
    return []


def _fallback_intent(instruction, requested, plan):
    """Regex backup if the model cannot classify the sentence."""
    text = instruction or ''
    section = _resolve_section(text, requested)

    if section != 'lesson_plan':
        return {
            'understood': True,
            'section': section,
            'weeks': [],
            'week_hint': None,
            'all_weeks': False,
            'add_teaching': [],
            'add_activities': [],
            'rewrite_fields': _fallback_rewrite_fields(section, text),
            'apply_to': 'all_rows',
            'fill_empty_only': _wants_empty_only(text),
            'style': _style_hint(text),
            'summary_bn': instruction[:80],
            'ask_bn': '',
        }

    labels = [label for pattern, label in _ASSESS_HINTS if pattern.search(text)]
    if _mentions_other_issues(text) and 'Discussion' in labels and not _LESSON_WEEK_HINT.search(text):
        labels = [x for x in labels if x != 'Discussion']
    weeks = []
    for match in re.finditer(
        r'(?:week|সপ্তাহ)\s*[:\-–]?\s*(\d+(?:\s*(?:ও|,|/|and|&)\s*\d+)*)',
        text,
        re.I,
    ):
        weeks.extend(int(num) for num in re.findall(r'\d+', match.group(1)))
    all_weeks = bool(re.search(
        r'প্রতি\s*সপ্তাহ|each\s*week|every\s*week|সব\s*সপ্তাহ|সবগুলো|সকল|পুরো|all\s+rows|all\s+classes|entire',
        text,
        re.I,
    ))
    rewrite = [f for f in _named_fields(text) if f in _LESSON_TEXT_FIELDS]
    add_teaching = [x for x in labels if x != 'Discussion']
    add_activities = ['Discussion'] if 'Discussion' in labels else []
    hint = None
    if re.search(r'মাঝামাঝি|মাঝখানে|mid', text, re.I):
        hint = 'middle'
    elif re.search(r'শেষ|last|final week', text, re.I):
        hint = 'last'
    elif re.search(r'শুরু|প্রথম|first week', text, re.I):
        hint = 'first'
    if not (labels or rewrite or weeks or all_weeks or hint):
        return {
            'understood': False,
            'section': requested if requested in PATCH_SECTIONS else 'lesson_plan',
            'ask_bn': 'কী বদলাতে চান আর একটু স্পষ্ট করুন। যেমন: কোন সপ্তাহে কুইজ, নাকি শুধু Academic Honesty পূরণ?',
        }
    return {
        'understood': True,
        'section': 'lesson_plan',
        'weeks': weeks,
        'week_hint': hint,
        'all_weeks': all_weeks,
        'add_teaching': add_teaching,
        'add_activities': add_activities,
        'rewrite_fields': rewrite,
        'apply_to': 'all_classes_in_week' if all_weeks or rewrite else 'last_class_of_week',
        'fill_empty_only': _wants_empty_only(text),
        'style': _style_hint(text),
        'summary_bn': instruction[:80],
    }


def _interpret_intent(instruction, requested, current_outline):
    plan = (current_outline or {}).get('lesson_plan') or []
    catalog = _week_catalog(plan)
    named = _named_fields(instruction)
    try:
        org = current_tenant().display_with_university
    except Exception:
        org = 'this university'
    system = (
        f'You interpret a university teacher instruction for {org}. '
        'The teacher may write Bangla, English, or mixed. Understand fine-grained intent. '
        'Return STRICT JSON only.'
    )
    user = (
        'Teacher instruction:\n'
        f'{instruction}\n\n'
        f'UI section selected: {requested}\n'
        f'Fields already named in the instruction: {_compact(named)}\n'
        f'Lesson-plan weeks: {_compact(catalog)[:2500]}\n\n'
        'Map the instruction to this JSON:\n'
        '{'
        '"understood": true, '
        f'"section": "{requested or "lesson_plan"}", '
        '"weeks": [], '
        '"week_hint": null, '
        '"all_weeks": false, '
        '"add_teaching": [], '
        '"add_activities": [], '
        '"rewrite_fields": [], '
        '"apply_to": "last_class_of_week", '
        '"fill_empty_only": false, '
        '"style": "standard", '
        '"summary_bn": "", '
        '"ask_bn": ""'
        '}\n\n'
        'Rules:\n'
        '- section: overview | lesson_plan | assessment_techniques | cie | smee | assessment | resources\n'
        '- Honor UI section selected unless the instruction clearly names a different part '
        '(e.g. "Part A", "Part C", "Part D", "week 5 quiz", "Academic Honesty").\n'
        '- overview (Part A): course_summary, prerequisites, clo_data.\n'
        '- Part C (assessment) Other Issues: class_discussion, general_expectations, '
        'communication, academic_honesty. Those are NEVER lesson_plan.\n'
        '- Part D (resources): textbooks, reference_books, other_resources, course_file_components.\n'
        '- rewrite_fields must be the SMALLEST set that satisfies the request. '
        'If they named one field, return only that field. '
        '"শুধু Academic Honesty" => ["academic_honesty"], not all of Part C.\n'
        '- "Class Discussion/Participation" in Part C => assessment, rewrite_fields '
        '["class_discussion"]. Do NOT treat it as weekly lesson-plan Discussion.\n'
        '- Weekly "প্রতি সপ্তাহে discussion" still means lesson_plan add_activities.\n'
        '- weeks: explicit week numbers only. "সপ্তাহ ৫ ও ৮" => [5,8]\n'
        '- week_hint: first | middle | last | null\n'
        '- add_teaching labels in English: Quiz, Class Test, Assignment, Presentation, Viva\n'
        '- fill_empty_only=true if they asked to fill blanks / খালি fields only.\n'
        '- style: concise | detailed | standard\n'
        '- apply_to: last_class_of_week | all_classes_in_week | all_rows\n'
        '- Quiz/test placement in a numbered week is lesson_plan, never Part C\n'
        '- If unclear, understood=false and ask_bn is a short Bangla question\n'
        '- summary_bn: one Bangla sentence of what you understood\n\n'
        'Examples:\n'
        '"সপ্তাহ ৫-এ কুইজ দাও" => section lesson_plan, weeks [5], add_teaching ["Quiz"]\n'
        '"মাঝামাঝি একটা অ্যাসাইনমেন্ট" => week_hint middle, add_teaching ["Assignment"]\n'
        '"প্রতি সপ্তাহে আলোচনা রাখো" => all_weeks true, add_activities ["Discussion"]\n'
        '"খালি আউটকামগুলো সংক্ষেপে লিখে দাও" => rewrite_fields ["outcome"], fill_empty_only true, style concise\n'
        '"শুধু Academic Honesty পূরণ করো" => section assessment, rewrite_fields ["academic_honesty"]\n'
        '"Part C-এর Class Discussion এবং Academic Honesty পূরণ করো" => assessment, '
        'rewrite_fields ["class_discussion","academic_honesty"]\n'
        '"Part D-এর textbooks লিখে দাও" => resources, rewrite_fields ["textbooks"]\n'
        '"Course Summary আরও একাডেমিক করো" => overview, rewrite_fields ["course_summary"]\n'
        '"বইয়ের তালিকা সাজাও" => resources, rewrite_fields ["textbooks"]\n'
    )
    try:
        raw, meta = _call_json(system, user, 900)
    except (AIClientError, json.JSONDecodeError, ValueError):
        return _fallback_intent(instruction, requested, plan), {'text': ''}

    intent = {
        'understood': bool(raw.get('understood', True)),
        'section': str(raw.get('section') or requested or 'lesson_plan').strip().lower(),
        'weeks': _as_int_list(raw.get('weeks')),
        'week_hint': (raw.get('week_hint') or None),
        'all_weeks': bool(raw.get('all_weeks')),
        'add_teaching': [str(x).strip() for x in (raw.get('add_teaching') or []) if str(x).strip()],
        'add_activities': [str(x).strip() for x in (raw.get('add_activities') or []) if str(x).strip()],
        'rewrite_fields': [
            str(x).strip() for x in (raw.get('rewrite_fields') or [])
            if str(x).strip() in _REWRITE_FIELDS
        ],
        'apply_to': str(raw.get('apply_to') or 'last_class_of_week').strip(),
        'fill_empty_only': bool(raw.get('fill_empty_only')) or _wants_empty_only(instruction),
        'style': str(raw.get('style') or _style_hint(instruction)).strip().lower(),
        'summary_bn': str(raw.get('summary_bn') or '').strip(),
        'ask_bn': str(raw.get('ask_bn') or '').strip(),
    }
    if intent['section'] not in PATCH_SECTIONS:
        intent['section'] = requested if requested in PATCH_SECTIONS else 'lesson_plan'
    intent['section'] = _resolve_section(instruction, requested, intent['section'])
    named_scoped = [f for f in named if _section_for_field(f) == intent['section'] or f in _OTHER_ISSUE_FIELDS]
    if named_scoped:
        if _ONLY_HINT.search(instruction or '') or intent['section'] != 'lesson_plan':
            merged = []
            for field in named_scoped + intent['rewrite_fields']:
                if field not in merged:
                    merged.append(field)
            # Named fields win over a coarse "other_issues" blob.
            if any(f in _OTHER_ISSUE_FIELDS for f in named_scoped):
                merged = [f for f in merged if f != 'other_issues'] or merged
            intent['rewrite_fields'] = merged
    if intent['section'] == 'assessment' and _mentions_other_issues(instruction):
        targets = _other_issue_targets(intent['rewrite_fields'], instruction)
        if targets:
            intent['rewrite_fields'] = targets
        elif not intent['rewrite_fields']:
            intent['rewrite_fields'] = ['other_issues']
    if intent['week_hint'] not in ('first', 'middle', 'last', None):
        hint = str(intent['week_hint'] or '').lower()
        intent['week_hint'] = hint if hint in ('first', 'middle', 'last') else None
    if intent['apply_to'] not in ('last_class_of_week', 'all_classes_in_week', 'all_rows'):
        intent['apply_to'] = 'last_class_of_week'
    if intent['style'] not in ('concise', 'detailed', 'standard'):
        intent['style'] = _style_hint(instruction)
    if intent['rewrite_fields'] and not intent['weeks'] and not intent['week_hint'] and intent['section'] == 'lesson_plan':
        intent['all_weeks'] = True
        intent['apply_to'] = 'all_rows'
    return intent, meta


def _resolve_weeks(intent, plan):
    nums = _plan_weeks(plan)
    if intent.get('all_weeks'):
        return nums, True
    weeks = list(intent.get('weeks') or [])
    hint = intent.get('week_hint')
    if not weeks and hint == 'first' and nums:
        weeks = [nums[0]]
    elif not weeks and hint == 'last' and nums:
        weeks = [nums[-1]]
    elif not weeks and hint == 'middle' and nums:
        weeks = [nums[len(nums) // 2]]
    elif not weeks and (intent.get('add_teaching') or intent.get('add_activities')) and nums:
        weeks = [nums[len(nums) // 2]]
    return weeks, False


def _target_indexes(plan, weeks, all_weeks, apply_to):
    last_by_week = {}
    indexes = []
    for idx, row in enumerate(plan or []):
        if not isinstance(row, dict):
            continue
        week_no = _week_num(row.get('week'))
        if not all_weeks and weeks and week_no not in weeks:
            continue
        if apply_to == 'last_class_of_week' and week_no is not None:
            last_by_week[week_no] = idx
        else:
            indexes.append(idx)
    if apply_to == 'last_class_of_week':
        return list(last_by_week.values())
    return indexes


def _length_rule(style):
    if style == 'concise':
        return 'Keep each value to 1 short sentence.'
    if style == 'detailed':
        return 'Write 3-5 precise academic sentences per field.'
    return 'Keep each value to 1-2 short sentences.'


def _rewrite_one_batch(plan, chunk, fields, instruction, context=None, fill_empty_only=False, style='standard'):
    """Rewrite one slice of lesson-plan rows. `i` must stay the original row index."""
    items = []
    for idx in chunk:
        row = plan[idx]
        item = {'i': idx, 'week': row.get('week') or '', 'topic': (row.get('topic') or '')[:180]}
        skip_row = True
        for field in fields:
            value = row.get(field) or ''
            if fill_empty_only and str(value).strip():
                continue
            item[field] = value
            skip_row = False
        if not skip_row:
            items.append(item)
    if not items:
        return {}
    ctx = _context_block(context)
    system = (
        'Rewrite only the requested lesson-plan fields. English academic style. '
        f'{_length_rule(style)} Return STRICT JSON. '
        'Return one object for EVERY input row. Copy the same numeric "i" from each input row. '
        'Match the actual course subject and the row topic. Do not invent a different discipline.'
    )
    user = (
        f'Teacher request: {instruction}\n'
        f'{ctx}\n'
        f'Fields to rewrite: {", ".join(fields)}\n'
        'Do not change week or topic. Do not invent a new subject.\n'
        f'You must return {len(items)} rows. Keep each "i" exactly as given.\n'
        f'ROWS:\n{_compact(items)}\n\n'
        'Return {"rows":[{"i":<same i>,"outcome":"...","activities":"..."}]} '
        'with every input row included. Omit fields you were not asked to change.'
    )
    raw, _meta = _call_json(system, user, 4500)
    chunk_set = set(item['i'] for item in items)
    updates = {}
    returned = raw.get('rows') or []
    for pos, item in enumerate(returned):
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get('i'))
        except (TypeError, ValueError):
            idx = items[pos]['i'] if pos < len(items) else None
        if idx not in chunk_set:
            idx = items[pos]['i'] if pos < len(items) else None
        if idx is None:
            continue
        patch = {}
        for field in fields:
            if fill_empty_only and str((plan[idx] or {}).get(field) or '').strip():
                continue
            value = item.get(field)
            if value not in (None, ''):
                patch[field] = str(value).strip()
        if patch:
            updates[idx] = patch
    return updates


def _rewrite_lesson_fields(plan, indexes, fields, instruction, context=None, fill_empty_only=False, style='standard'):
    if not indexes or not fields:
        return {}
    updates = {}
    batch_size = 8
    unique_indexes = []
    seen = set()
    for idx in indexes:
        if idx in seen or idx < 0 or idx >= len(plan):
            continue
        seen.add(idx)
        unique_indexes.append(idx)
    for start in range(0, len(unique_indexes), batch_size):
        chunk = unique_indexes[start:start + batch_size]
        try:
            updates.update(_rewrite_one_batch(
                plan, chunk, fields, instruction, context, fill_empty_only, style,
            ))
        except (AIClientError, json.JSONDecodeError, ValueError):
            continue
    missing = [idx for idx in unique_indexes if idx not in updates]
    if fill_empty_only:
        missing = [
            idx for idx in missing
            if any(not str((plan[idx] or {}).get(field) or '').strip() for field in fields)
        ]
    if missing:
        for start in range(0, len(missing), max(4, batch_size // 2)):
            chunk = missing[start:start + max(4, batch_size // 2)]
            try:
                updates.update(_rewrite_one_batch(
                    plan, chunk, fields, instruction, context, fill_empty_only, style,
                ))
            except (AIClientError, json.JSONDecodeError, ValueError):
                continue
    return updates


def _is_empty_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return not any(not _is_empty_value(v) for v in value.values())
    if isinstance(value, list):
        return not any(not _is_empty_value(v) for v in value)
    return False


def _merge_other_issues(raw, targets):
    src = raw.get('other_issues') if isinstance(raw.get('other_issues'), dict) else {}
    merged = {}
    for field in targets or _OTHER_ISSUE_FIELDS:
        value = src.get(field)
        if value in (None, ''):
            value = raw.get(field)
        if value not in (None, ''):
            merged[field] = str(value).strip()
    return merged or None


def _rewrite_section_payload(section, snapshot, instruction, fields, context=None, fill_empty_only=False, style='standard'):
    keys = _keys_for_rewrite(section, fields)
    other_targets = []
    if section == 'assessment':
        other_targets = _other_issue_targets(fields, instruction)
        if other_targets:
            keys = ['other_issues']
    slim = {key: snapshot.get(key) for key in keys}
    if section == 'assessment' and 'rubrics' in slim and 'other_issues' in keys:
        slim.pop('rubrics', None)

    if fill_empty_only:
        if 'other_issues' in keys:
            current = slim.get('other_issues') if isinstance(slim.get('other_issues'), dict) else {}
            other_targets = [
                field for field in (other_targets or list(_OTHER_ISSUE_FIELDS))
                if _is_empty_value(current.get(field))
            ]
            if not other_targets:
                raise ValueError('এই ফিল্ডগুলো ইতিমধ্যে পূরণ আছে। খালি ফিল্ড নেই, অথবা পুরোটা বদলাতে চাইলে «খালি» না লিখে আবার দিন।')
        else:
            slim = {key: value for key, value in slim.items() if _is_empty_value(value)}
            keys = list(slim.keys())
            if not keys:
                raise ValueError('এই অংশে খালি ফিল্ড নেই। পুরোটা বদলাতে চাইলে «খালি» না লিখে আবার দিন।')

    ctx = _context_block(context)
    length = _length_rule(style)
    extra = ''
    if 'other_issues' in keys:
        extra = (
            '\nFor other_issues return an object with ONLY these keys: '
            + ', '.join(other_targets or _OTHER_ISSUE_FIELDS)
            + '. Each value should be course-specific policy text. '
            'Do not copy generic boilerplate that ignores this course.\n'
        )
    if 'textbooks' in keys or 'reference_books' in keys:
        extra += (
            '\nBook lists must match this course subject. Use academic citation style '
            '(Author, Title, Publisher, Year). Prefer well-known works in that field. '
            'HTML <p> or <br> is allowed for Part D rich fields.\n'
        )
    if 'clo_data' in keys:
        extra += (
            '\nclo_data is a list of {number, description, plos}. Keep existing PLO tags '
            'unless asked to change them. Improve or fill descriptions only.\n'
        )
    if 'course_summary' in keys:
        extra += '\ncourse_summary: 1 short academic paragraph for THIS course.\n'

    system = (
        'Edit this university course-outline section to follow the teacher exactly. '
        'Write formal academic English that matches the named course. '
        f'{length} Return STRICT JSON with only the keys you changed. '
        'Never wipe unrelated fields. If only one field was requested, return only that field. '
        'Do not invent a different subject.'
    )
    user = (
        f'Teacher request: {instruction}\n'
        f'{ctx}\n'
        f'Allowed keys: {", ".join(keys)}\n'
        f'{extra}'
        f'CURRENT:\n{_compact(slim)[:8000]}\n'
        'Keep lists a similar length. No markdown fences.'
    )
    raw, _meta = _call_json(system, user, 3500 if style == 'detailed' else 3000)
    payload = {}
    for key in keys:
        if key == 'other_issues':
            merged = _merge_other_issues(raw if isinstance(raw, dict) else {}, other_targets)
            if merged:
                payload['other_issues'] = merged
            continue
        if key in raw and raw[key] not in (None, ''):
            if fill_empty_only and not _is_empty_value(snapshot.get(key)):
                continue
            payload[key] = raw[key]
    return payload


def _apply_lesson_intent(plan, intent, instruction, context=None):
    plan = [dict(row) for row in (plan or []) if isinstance(row, dict)]
    weeks, all_weeks = _resolve_weeks(intent, plan)
    apply_to = intent.get('apply_to') or 'last_class_of_week'
    rewrite_only = bool(intent.get('rewrite_fields')) and not (
        intent.get('add_teaching') or intent.get('add_activities') or intent.get('weeks') or intent.get('week_hint')
    )
    if rewrite_only or (intent.get('rewrite_fields') and (all_weeks or intent.get('all_weeks'))):
        apply_to = 'all_rows'
        all_weeks = True
    indexes = _target_indexes(plan, weeks, all_weeks or intent.get('all_weeks'), apply_to)
    if not indexes:
        indexes = list(range(len(plan)))

    changed = 0
    for idx in indexes:
        row = plan[idx]
        before = dict(row)
        for label in intent.get('add_teaching') or []:
            row['teaching_assessment'] = _append_label(row.get('teaching_assessment') or '', label)
        for label in intent.get('add_activities') or []:
            row['activities'] = _append_label(row.get('activities') or '', label)
        if row != before:
            changed += 1

    rewrite_fields = [
        field for field in (intent.get('rewrite_fields') or [])
        if field in _LESSON_TEXT_FIELDS
    ]
    if rewrite_fields:
        try:
            updates = _rewrite_lesson_fields(
                plan, indexes, rewrite_fields, instruction,
                context=context,
                fill_empty_only=bool(intent.get('fill_empty_only')),
                style=intent.get('style') or 'standard',
            )
        except (AIClientError, json.JSONDecodeError, ValueError):
            updates = {}
        for idx, patch in updates.items():
            if 0 <= idx < len(plan):
                plan[idx].update(patch)
                changed += 1

    if not changed:
        return None, 0
    return {'lesson_plan': plan}, changed


def _summarize(intent, changed):
    text = (intent.get('summary_bn') or '').strip()
    if text and changed:
        return f'{text} ({changed}টি সারি)।'
    if text:
        return text
    if changed:
        return f'Lesson Plan-এ {changed}টি সারি হালনাগাদ হয়েছে।'
    return 'এই অংশ হালনাগাদ হয়েছে।'


def _extract_context(current_outline, context):
    merged = {}
    if isinstance(current_outline, dict):
        nested = current_outline.get('_context')
        if isinstance(nested, dict):
            merged.update(nested)
        if current_outline.get('course_summary') and not merged.get('course_summary'):
            merged['course_summary'] = current_outline.get('course_summary')
        clos = current_outline.get('clo_data')
        if isinstance(clos, list) and not merged.get('clos'):
            merged['clos'] = [
                f"CLO {item.get('number') or i + 1}: {(item.get('description') or '')[:160]}"
                for i, item in enumerate(clos) if isinstance(item, dict)
            ]
    if isinstance(context, dict):
        merged.update({k: v for k, v in context.items() if v not in (None, '', [])})
    return merged


def patch_outline_section(section, instruction, current_outline, allow_topic_change=False, context=None):
    """Understand the teacher instruction, then return a partial form payload."""
    instruction = (instruction or '').strip()
    if not instruction:
        raise ValueError('কী বদলাতে চান এক বাক্যে লিখুন।')
    if len(instruction) > _MAX_INSTRUCTION:
        instruction = instruction[:_MAX_INSTRUCTION]

    requested = (section or 'lesson_plan').strip().lower()
    current_outline = current_outline if isinstance(current_outline, dict) else {}
    context = _extract_context(current_outline, context)
    intent, meta = _interpret_intent(instruction, requested, current_outline)

    if not intent.get('understood'):
        raise ValueError(intent.get('ask_bn') or 'নির্দেশনাটা আর একটু স্পষ্ট করুন। কোন সপ্তাহে কী করতে হবে?')

    section = intent.get('section') or requested
    spec = PATCH_SECTIONS.get(section)
    if not spec:
        raise ValueError('অজানা সেকশন। Lesson Plan বেছে নিয়ে আবার লিখুন।')

    snapshot = _slice_current(current_outline, spec['keys'])
    if 'lesson_plan' in spec['keys'] and not (snapshot.get('lesson_plan') or current_outline.get('lesson_plan')):
        raise ValueError('আগে ১৪ নম্বরে Generate Plan চাপুন, তারপর এআই দিয়ে সাজান।')
    if 'lesson_plan' in spec['keys'] and not snapshot.get('lesson_plan'):
        snapshot['lesson_plan'] = current_outline.get('lesson_plan') or []

    if section == 'lesson_plan':
        payload, changed = _apply_lesson_intent(
            snapshot.get('lesson_plan') or [], intent, instruction, context=context,
        )
        if not payload:
            raise ValueError(
                'বুঝেছি, কিন্তু ফর্মে প্রয়োগ করার মতো পরিবর্তন পাইনি। '
                + (intent.get('summary_bn') or 'সপ্তাহ ও কাজটা আরেকবার লিখুন।')
            )
        return payload, meta, {
            'section': section,
            'summary': _summarize(intent, changed),
            'changed': changed,
        }

    rewrite_fields = intent.get('rewrite_fields') or _fallback_rewrite_fields(section, instruction)
    try:
        payload = _rewrite_section_payload(
            section, snapshot, instruction, rewrite_fields,
            context=context,
            fill_empty_only=bool(intent.get('fill_empty_only')),
            style=intent.get('style') or 'standard',
        )
    except (AIClientError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(str(exc) or 'এই সেকশন হালনাগাদ করা যায়নি। আবার চেষ্টা করুন।')
    if not payload:
        raise ValueError('এআই এই সেকশনে পরিবর্তন ফেরত দেয়নি। নির্দেশনা আরেকভাবে লিখুন।')
    return payload, meta, {
        'section': section,
        'summary': intent.get('summary_bn') or 'এই অংশ হালনাগাদ হয়েছে।',
        'changed': 1,
    }
