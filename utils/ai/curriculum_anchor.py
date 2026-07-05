"""Bind AI outline output to curriculum rationale, CLOs, and content (no hallucination)."""
import json
import re


def _topic_text(item):
    if isinstance(item, dict):
        return (item.get('content') or item.get('topic') or item.get('text') or '').strip()
    return str(item or '').strip()


def _parse_hours(item, default=1):
    if not isinstance(item, dict):
        return default
    raw = item.get('hrs') or item.get('num_classes') or item.get('hours')
    if raw in (None, ''):
        return default
    try:
        return max(1, int(float(str(raw).strip())))
    except (TypeError, ValueError):
        return default


def curriculum_content_to_outline_section(items):
    """Map curriculum content rows → outline sectionA/B items."""
    result = []
    for item in items or []:
        topic = _topic_text(item)
        if not topic:
            continue
        hrs = ''
        clo = ''
        if isinstance(item, dict):
            hrs = str(item.get('hrs') or item.get('hours') or '').strip()
            clo = str(item.get('clo') or item.get('clos') or '').strip()
        result.append({
            'topic': topic,
            'content': topic,
            'hrs': hrs,
            'clo': clo,
            'selected': True,
            'num_classes': _parse_hours(item if isinstance(item, dict) else {}, default=1),
        })
    return result


def _parse_plos(clo_entry):
    if not isinstance(clo_entry, dict):
        return []
    plo_raw = clo_entry.get('plos') or clo_entry.get('plo') or ''
    if isinstance(plo_raw, list):
        return [str(p).strip() for p in plo_raw if str(p).strip()]
    if not isinstance(plo_raw, str) or not plo_raw.strip():
        return []
    parts = re.split(r'[,;/]+', plo_raw)
    plos = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if token.upper().startswith('PLO'):
            plos.append(token.upper().replace('PLO', 'PLO ').replace('  ', ' ').strip())
        else:
            plos.append(f'PLO {token}')
    return plos


def curriculum_clos_to_outline_clos(clos):
    """Map curriculum CLO list → outline clo_data."""
    result = []
    for idx, clo in enumerate(clos or [], start=1):
        if isinstance(clo, str):
            desc = clo.strip()
            plos = []
        elif isinstance(clo, dict):
            desc = (clo.get('text') or clo.get('description') or '').strip()
            plos = _parse_plos(clo)
        else:
            continue
        if not desc:
            continue
        result.append({'number': idx, 'description': desc, 'plos': plos})
    return result


def build_curriculum_anchor(context):
    """Extract canonical curriculum fields from generation context."""
    course = (context or {}).get('course') or {}
    section_a = curriculum_content_to_outline_section(course.get('content_section_a'))
    section_b = curriculum_content_to_outline_section(course.get('content_section_b'))
    clos = curriculum_clos_to_outline_clos(course.get('clos'))
    rationale = (course.get('rationale') or '').strip()
    return {
        'rationale': rationale,
        'clo_data': clos,
        'course_content_summary': {
            'sectionA': section_a,
            'sectionB': section_b,
        },
        'has_rationale': bool(rationale),
        'has_clos': bool(clos),
        'has_content': bool(section_a or section_b),
    }


def curriculum_grounding_rules(anchor):
    """Prompt rules: curriculum is source of truth."""
    rules = [
        '=== CURRICULUM SOURCE OF TRUTH (MANDATORY) ===',
        'Do NOT invent course rationale, CLOs, or topic lists.',
        'Use ONLY context.course.rationale, context.course.clos, context.course.content_section_a/b.',
        'course_summary MUST be the curriculum rationale (light copy-edit only; same meaning).',
        'clo_data MUST use exact CLO descriptions from curriculum; do not add/remove/reword CLOs.',
        'course_content_summary sectionA/sectionB topics MUST match curriculum content topics exactly (field topic = curriculum content text).',
        'lesson_plan topics MUST come from those curriculum topics only — schedule them across weeks; do not add new subjects.',
        'lesson_plan: one row per class session; up to classes_per_week rows share the same week number.',
        'Spread formative assessments (quiz, class test, assignment briefing/submission, presentation) across different weeks in teaching_assessment — mix with lecture/discussion; never put all assessments only in the final week.',
        'course_objectives may be bullet summaries of the CLO descriptions, not new objectives.',
        'You may generate: lesson_plan timing, assessment tables, rubrics, textbooks, policies — but NOT substitute curriculum content.',
        'If curriculator PLO mapping exists, use it for plo_mapping only.',
        '=== END CURRICULUM RULES ===',
    ]
    if anchor.get('has_rationale'):
        rules.insert(2, f'Curriculum rationale provided ({len(anchor["rationale"])} chars) — use as course_summary.')
    if anchor.get('has_clos'):
        rules.insert(3, f'Curriculum CLO count: {len(anchor["clo_data"])} — output exactly this many CLOs.')
    if anchor.get('has_content'):
        a_count = len(anchor['course_content_summary'].get('sectionA') or [])
        b_count = len(anchor['course_content_summary'].get('sectionB') or [])
        rules.insert(4, f'Curriculum topics: sectionA={a_count}, sectionB={b_count} — copy all.')
    return rules


def _merge_topic_classes(canonical, ai_section):
    """Keep curriculum topic text; keep AI num_classes only when topic matches."""
    if not canonical:
        return canonical or []
    ai_by_topic = {}
    for item in ai_section or []:
        if isinstance(item, dict):
            key = _topic_text(item).lower()
            if key:
                ai_by_topic[key] = item
    merged = []
    for canon in canonical:
        key = canon['topic'].strip().lower()
        ai_item = ai_by_topic.get(key)
        num = canon.get('num_classes', 1)
        if ai_item:
            num = _parse_hours(ai_item, default=num)
        merged.append({
            'topic': canon['topic'],
            'content': canon['topic'],
            'hrs': canon.get('hrs', ''),
            'clo': canon.get('clo', ''),
            'selected': True,
            'num_classes': num,
        })
    return merged


def _normalize_content_summary_item(item):
    """Ensure PDF/form fields: content, topic, selected."""
    if not isinstance(item, dict):
        return item
    topic = _topic_text(item)
    out = dict(item)
    if topic:
        out['content'] = topic
        out['topic'] = topic
    if out.get('selected') is None:
        out['selected'] = True
    return out


def normalize_content_summary(summary):
    """Normalize sectionA/B items for save, PDF, and UI."""
    if isinstance(summary, str) and summary.strip():
        summary = _normalize_content_summary_field(summary)
    if not isinstance(summary, dict):
        return {'sectionA': [], 'sectionB': []}
    section_a = [_normalize_content_summary_item(i) for i in (summary.get('sectionA') or [])]
    section_b = [_normalize_content_summary_item(i) for i in (summary.get('sectionB') or [])]
    return {'sectionA': section_a, 'sectionB': section_b}


def resolve_course_content_summary(stored_summary, course_data=None, classes_data=None):
    """Use saved summary or fall back to curriculum; merge class counts for PDF/UI."""
    summary = normalize_content_summary(_normalize_content_summary_field(stored_summary))
    section_a = summary.get('sectionA') or []
    section_b = summary.get('sectionB') or []

    if not section_a and course_data and getattr(course_data, 'content_section_a', None):
        try:
            raw = course_data.content_section_a
            raw = json.loads(raw) if isinstance(raw, str) else raw
            section_a = curriculum_content_to_outline_section(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    if not section_b and course_data and getattr(course_data, 'content_section_b', None):
        try:
            raw = course_data.content_section_b
            raw = json.loads(raw) if isinstance(raw, str) else raw
            section_b = curriculum_content_to_outline_section(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    classes_data = classes_data if isinstance(classes_data, dict) else {}
    for idx, item in enumerate(section_a):
        if isinstance(item, dict) and idx < len(classes_data.get('section_a', [])):
            item['num_classes'] = classes_data['section_a'][idx]
    for idx, item in enumerate(section_b):
        if isinstance(item, dict) and idx < len(classes_data.get('section_b', [])):
            item['num_classes'] = classes_data['section_b'][idx]

    return {'sectionA': section_a, 'sectionB': section_b}


def _normalize_content_summary_field(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def anchor_payload_to_curriculum(payload, context):
    """Overwrite AI-invented rationale/CLO/content with curriculum data."""
    anchor = build_curriculum_anchor(context)
    out = dict(payload or {})

    if anchor['rationale']:
        out['course_summary'] = anchor['rationale']

    if anchor['clo_data']:
        out['clo_data'] = [dict(c) for c in anchor['clo_data']]
        out['course_objectives'] = [c['description'] for c in anchor['clo_data'] if c.get('description')]

    section_a = anchor['course_content_summary'].get('sectionA') or []
    section_b = anchor['course_content_summary'].get('sectionB') or []
    if section_a or section_b:
        summary = _normalize_content_summary_field(out.get('course_content_summary'))
        if section_a:
            summary['sectionA'] = _merge_topic_classes(section_a, summary.get('sectionA'))
        if section_b:
            summary['sectionB'] = _merge_topic_classes(section_b, summary.get('sectionB'))
        out['course_content_summary'] = summary
        from utils.ai.outline_parser import _serialize_course_content_summary
        _serialize_course_content_summary(out)

    return out


def validate_curriculum_ready(context):
    """Raise ValueError with Bengali message if curriculum fields missing."""
    anchor = build_curriculum_anchor(context)
    missing = []
    if not anchor['has_rationale']:
        missing.append('Rationale')
    if not anchor['has_clos']:
        missing.append('CLO')
    if not anchor['has_content']:
        missing.append('Course Content (Section A/B)')
    if missing:
        code = (context.get('course') or {}).get('course_code') or ''
        raise ValueError(
            f'কারিকুলামে {", ".join(missing)} খালি আছে ({code})। '
            'Course Management → Curricula → Course Information-এ যোগ করুন। '
            'AI নিজে থেকে rationale/CLO/content বানাবে না।'
        )
    return anchor
