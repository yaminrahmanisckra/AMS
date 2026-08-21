"""In-place AI patches: understand the teacher, then edit the form."""
import json
import re

from utils.ai.client import AIClientError, generate_outline_json_with_meta
from utils.ai.outline_parser import extract_json_from_response
from utils.ai.session_utils import reset_db_session
from utils.tenant import current_tenant

PATCH_SECTIONS = {
    'lesson_plan': {'keys': ('lesson_plan',), 'lock_topics': True},
    'assessment_techniques': {'keys': ('assessment_techniques',), 'lock_topics': False},
    'cie': {'keys': ('cie_breakdown',), 'lock_topics': False},
    'smee': {'keys': ('smee_breakdown',), 'lock_topics': False},
    'assessment': {
        'keys': ('assessment_strategy', 'rubrics', 'grading_policy', 'make_up_procedures'),
        'lock_topics': False,
    },
    'resources': {
        'keys': ('textbooks', 'reference_books', 'other_resources', 'other_issues'),
        'lock_topics': False,
    },
}

_ASSESS_HINTS = (
    (re.compile(r'quiz|কুইজ', re.I), 'Quiz'),
    (re.compile(r'class\s*test|ক্লাস\s*টেস্ট|ক্লাসটেস্ট', re.I), 'Class Test'),
    (re.compile(r'assignment|অ্যাসাইনমেন্ট|এসাইনমেন্ট|অ্যাসাইনমেন্ট', re.I), 'Assignment'),
    (re.compile(r'presentation|প্রেজেন্টেশন|উপস্থাপনা', re.I), 'Presentation'),
    (re.compile(r'viva|ভাইভা|মৌখিক', re.I), 'Viva'),
    (re.compile(r'discussion|ডিসকাশন|আলোচনা', re.I), 'Discussion'),
)

_REWRITE_FIELDS = {
    'outcome', 'activities', 'teaching_assessment', 'clo_alignment',
    'textbooks', 'reference_books', 'other_resources', 'other_issues',
    'assessment_techniques', 'cie_breakdown', 'smee_breakdown',
    'assessment_strategy', 'rubrics', 'grading_policy', 'make_up_procedures',
}


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


def _fallback_intent(instruction, requested, plan):
    """Regex backup if the model cannot classify the sentence."""
    text = instruction or ''
    labels = [label for pattern, label in _ASSESS_HINTS if pattern.search(text)]
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
    rewrite = []
    if re.search(r'আউটকাম|outcome', text, re.I):
        rewrite.append('outcome')
    if re.search(r'অ্যাকটিভিটি|activities|কাজ', text, re.I):
        rewrite.append('activities')
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
            'section': requested,
            'ask_bn': 'কী বদলাতে চান আর একটু স্পষ্ট করুন। যেমন: কোন সপ্তাহে কুইজ, নাকি আউটকাম লিখতে হবে?',
        }
    return {
        'understood': True,
        'section': 'lesson_plan' if (labels or rewrite or weeks or all_weeks or hint) else requested,
        'weeks': weeks,
        'week_hint': hint,
        'all_weeks': all_weeks,
        'add_teaching': add_teaching,
        'add_activities': add_activities,
        'rewrite_fields': rewrite,
        'apply_to': 'all_classes_in_week' if all_weeks or rewrite else 'last_class_of_week',
        'summary_bn': instruction[:80],
    }


def _interpret_intent(instruction, requested, current_outline):
    plan = (current_outline or {}).get('lesson_plan') or []
    catalog = _week_catalog(plan)
    try:
        org = current_tenant().display_with_university
    except Exception:
        org = 'this university'
    system = (
        f'You interpret a university teacher instruction for {org}. '
        'The teacher may write Bangla, English, or mixed. Understand the meaning. '
        'Return STRICT JSON only.'
    )
    user = (
        'Teacher instruction:\n'
        f'{instruction}\n\n'
        f'UI section selected: {requested}\n'
        f'Lesson-plan weeks: {_compact(catalog)[:2500]}\n\n'
        'Map the instruction to this JSON:\n'
        '{'
        '"understood": true, '
        '"section": "lesson_plan", '
        '"weeks": [], '
        '"week_hint": null, '
        '"all_weeks": false, '
        '"add_teaching": [], '
        '"add_activities": [], '
        '"rewrite_fields": [], '
        '"apply_to": "last_class_of_week", '
        '"summary_bn": "", '
        '"ask_bn": ""'
        '}\n\n'
        'Rules:\n'
        '- section: lesson_plan | assessment_techniques | cie | smee | assessment | resources\n'
        '- weeks: explicit week numbers only. "সপ্তাহ ৫ ও ৮" => [5,8]\n'
        '- week_hint: first | middle | last | null (use when they say মাঝামাঝি/শেষে/শুরুতে)\n'
        '- add_teaching labels in English: Quiz, Class Test, Assignment, Presentation, Viva\n'
        '- class discussion / আলোচনা => add_activities: ["Discussion"]\n'
        '- rewrite_fields if they asked to write/improve text: outcome, activities, teaching_assessment, textbooks, ...\n'
        '- apply_to: last_class_of_week (one class in that week) OR all_classes_in_week OR all_rows\n'
        '- Quiz/test placement is ALWAYS lesson_plan, never Part C\n'
        '- If unclear, understood=false and ask_bn is a short Bangla question\n'
        '- summary_bn: one Bangla sentence of what you understood\n\n'
        'Examples:\n'
        '"সপ্তাহ ৫-এ কুইজ দাও" => understood true, section lesson_plan, weeks [5], add_teaching ["Quiz"]\n'
        '"মাঝামাঝি একটা অ্যাসাইনমেন্ট" => week_hint middle, add_teaching ["Assignment"]\n'
        '"প্রতি সপ্তাহে আলোচনা রাখো" => all_weeks true, add_activities ["Discussion"], apply_to all_classes_in_week\n'
        '"আউটকামগুলো সংক্ষেপে লিখে দাও" => rewrite_fields ["outcome"], all_weeks true, apply_to all_rows\n'
        '"শেষের দিকে ভিভা" => week_hint last, add_teaching ["Viva"]\n'
        '"বইয়ের তালিকা সাজাও" => section resources, rewrite_fields ["textbooks"]\n'
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
        'summary_bn': str(raw.get('summary_bn') or '').strip(),
        'ask_bn': str(raw.get('ask_bn') or '').strip(),
    }
    if intent['section'] not in PATCH_SECTIONS:
        intent['section'] = requested if requested in PATCH_SECTIONS else 'lesson_plan'
    if intent['week_hint'] not in ('first', 'middle', 'last', None):
        hint = str(intent['week_hint'] or '').lower()
        intent['week_hint'] = hint if hint in ('first', 'middle', 'last') else None
    if intent['apply_to'] not in ('last_class_of_week', 'all_classes_in_week', 'all_rows'):
        intent['apply_to'] = 'last_class_of_week'
    if intent['rewrite_fields'] and not intent['weeks'] and not intent['week_hint']:
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


def _rewrite_one_batch(plan, chunk, fields, instruction):
    """Rewrite one slice of lesson-plan rows. `i` must stay the original row index."""
    items = []
    for idx in chunk:
        row = plan[idx]
        item = {'i': idx, 'week': row.get('week') or '', 'topic': (row.get('topic') or '')[:180]}
        for field in fields:
            item[field] = row.get(field) or ''
        items.append(item)
    system = (
        'Rewrite only the requested lesson-plan fields. English academic style. '
        'Keep each value to 1-2 short sentences. Return STRICT JSON. '
        'Return one object for EVERY input row. Copy the same numeric "i" from each input row.'
    )
    user = (
        f'Teacher request: {instruction}\n'
        f'Fields to rewrite: {", ".join(fields)}\n'
        'Do not change week or topic. Do not invent a new subject.\n'
        f'You must return {len(items)} rows. Keep each "i" exactly as given.\n'
        f'ROWS:\n{_compact(items)}\n\n'
        'Return {"rows":[{"i":<same i>,"outcome":"...","activities":"..."}]} '
        'with every input row included.'
    )
    raw, _meta = _call_json(system, user, 4500)
    chunk_set = set(chunk)
    updates = {}
    returned = raw.get('rows') or []
    for pos, item in enumerate(returned):
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get('i'))
        except (TypeError, ValueError):
            idx = chunk[pos] if pos < len(chunk) else None
        if idx not in chunk_set:
            idx = chunk[pos] if pos < len(chunk) else None
        if idx is None:
            continue
        patch = {}
        for field in fields:
            value = item.get(field)
            if value not in (None, ''):
                patch[field] = str(value).strip()
        if patch:
            updates[idx] = patch
    return updates


def _rewrite_lesson_fields(plan, indexes, fields, instruction):
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
            updates.update(_rewrite_one_batch(plan, chunk, fields, instruction))
        except (AIClientError, json.JSONDecodeError, ValueError):
            continue
    missing = [idx for idx in unique_indexes if idx not in updates]
    if missing:
        for start in range(0, len(missing), max(4, batch_size // 2)):
            chunk = missing[start:start + max(4, batch_size // 2)]
            try:
                updates.update(_rewrite_one_batch(plan, chunk, fields, instruction))
            except (AIClientError, json.JSONDecodeError, ValueError):
                continue
    return updates


def _rewrite_section_payload(section, snapshot, instruction, fields):
    spec = PATCH_SECTIONS[section]
    keys = [key for key in spec['keys'] if key in fields or not fields]
    if not keys:
        keys = list(spec['keys'])
    slim = {key: snapshot.get(key) for key in keys}
    if section == 'assessment' and 'rubrics' in slim and 'rubrics' not in fields:
        slim.pop('rubrics', None)
    system = (
        'Edit this course-outline section to follow the teacher. '
        'Return STRICT JSON with only the keys you changed.'
    )
    user = (
        f'Teacher request: {instruction}\n'
        f'Allowed keys: {", ".join(keys)}\n'
        f'CURRENT:\n{_compact(slim)[:8000]}\n'
        'Keep lists a similar length. No markdown.'
    )
    raw, _meta = _call_json(system, user, 3000)
    payload = {}
    for key in keys:
        if key in raw and raw[key] not in (None, ''):
            payload[key] = raw[key]
    return payload


def _apply_lesson_intent(plan, intent, instruction):
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
        if field in ('outcome', 'activities', 'teaching_assessment', 'clo_alignment')
    ]
    if rewrite_fields:
        try:
            updates = _rewrite_lesson_fields(plan, indexes, rewrite_fields, instruction)
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


def patch_outline_section(section, instruction, current_outline, allow_topic_change=False):
    """Understand the teacher instruction, then return a partial form payload."""
    instruction = (instruction or '').strip()
    if not instruction:
        raise ValueError('কী বদলাতে চান এক বাক্যে লিখুন।')
    if len(instruction) > 500:
        instruction = instruction[:500]

    requested = (section or 'lesson_plan').strip().lower()
    current_outline = current_outline if isinstance(current_outline, dict) else {}
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
        payload, changed = _apply_lesson_intent(snapshot.get('lesson_plan') or [], intent, instruction)
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

    rewrite_fields = intent.get('rewrite_fields') or list(spec['keys'])
    try:
        payload = _rewrite_section_payload(section, snapshot, instruction, rewrite_fields)
    except (AIClientError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(str(exc) or 'এই সেকশন হালনাগাদ করা যায়নি। আবার চেষ্টা করুন।')
    if not payload:
        raise ValueError('এআই এই সেকশনে পরিবর্তন ফেরত দেয়নি। নির্দেশনা আরেকভাবে লিখুন।')
    return payload, meta, {
        'section': section,
        'summary': intent.get('summary_bn') or 'এই অংশ হালনাগাদ হয়েছে।',
        'changed': 1,
    }
