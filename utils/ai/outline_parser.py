"""Validate and normalize AI outline JSON for save_course_outline."""
import json

from utils.ai.curriculum_anchor import normalize_content_summary


def _ensure_list(value, default=None):
    if default is None:
        default = []
    if value is None:
        return default
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else default
        except json.JSONDecodeError:
            return [value] if value.strip() else default
    return default


def _ensure_dict(value, default=None):
    if default is None:
        default = {}
    if value is None:
        return default
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else default
        except json.JSONDecodeError:
            return default
    return default


def extract_json_from_response(text):
    """Parse JSON from model output, stripping markdown fences if present."""
    if not text:
        raise ValueError('Empty AI response')
    cleaned = text.strip()
    if cleaned.startswith('```'):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        cleaned = '\n'.join(lines).strip()
    return json.loads(cleaned)


def normalize_assessment_strategy(strategy):
    """Normalize AI/manual assessment_strategy for forms and PDF export."""
    if not isinstance(strategy, dict):
        return {}
    out = dict(strategy)

    att = out.get('attendance_marks')
    if att is not None and not isinstance(att, (list, tuple)):
        if isinstance(att, (int, float)) and not out.get('attendance_percent'):
            out['attendance_percent'] = att
        out['attendance_marks'] = []
    elif isinstance(att, list):
        cleaned = []
        for item in att:
            if isinstance(item, dict):
                cleaned.append(item)
            elif item is not None:
                cleaned.append({'range': str(item), 'marks': ''})
        out['attendance_marks'] = cleaned

    for old_key, new_key in (
        ('attendance_percentage', 'attendance_percent'),
        ('ca_percentage', 'ca_percent'),
        ('final_exam_percentage', 'final_exam_percent'),
    ):
        if old_key in out and out.get(new_key) in (None, ''):
            out[new_key] = out[old_key]

    points = out.get('strategy_points')
    if isinstance(points, str):
        out['strategy_points'] = [ln.strip() for ln in points.splitlines() if ln.strip()]
    elif isinstance(points, list):
        out['strategy_points'] = [str(p).strip() for p in points if str(p).strip()]
    elif points is not None:
        out['strategy_points'] = [str(points).strip()] if str(points).strip() else []

    comps = out.get('ca_components')
    if isinstance(comps, list):
        cleaned_comps = []
        for item in comps:
            if isinstance(item, dict):
                name = str(item.get('name') or '').strip()
                if name and item.get('selected', True):
                    cleaned_comps.append(name)
            elif item is not None:
                name = str(item).strip()
                if name:
                    cleaned_comps.append(name)
        other = str(out.get('ca_components_other') or '').strip()
        if other and other not in cleaned_comps:
            cleaned_comps.append(other)
        out['ca_components'] = cleaned_comps
    elif isinstance(comps, str) and comps.strip():
        out['ca_components'] = [ln.strip() for ln in comps.splitlines() if ln.strip()]
    elif comps is not None:
        out['ca_components'] = []

    if 'rubrics_enabled' in out:
        val = out.get('rubrics_enabled')
        if isinstance(val, str):
            out['rubrics_enabled'] = val.strip().lower() in ('1', 'true', 'yes', 'on')
        else:
            out['rubrics_enabled'] = bool(val)

    for flag_key in ('assessment_techniques_enabled', 'cie_enabled', 'smee_enabled'):
        if flag_key in out:
            val = out.get(flag_key)
            if isinstance(val, str):
                out[flag_key] = val.strip().lower() in ('1', 'true', 'yes', 'on')
            else:
                out[flag_key] = bool(val)

    return out


def _serialize_course_content_summary(payload):
    """Store course_content_summary as JSON text; extract classes_a/classes_b for save route."""
    if not isinstance(payload, dict) or 'course_content_summary' not in payload:
        return payload

    summary = payload.get('course_content_summary')
    if isinstance(summary, str) and summary.strip():
        try:
            summary = json.loads(summary)
        except json.JSONDecodeError:
            return payload
    if not isinstance(summary, dict):
        return payload
    summary = normalize_content_summary(summary)
    classes_a = []
    classes_b = []
    for item in summary.get('sectionA', []) or []:
        try:
            classes_a.append(max(1, int(item.get('num_classes', 1) or 1)))
        except (TypeError, ValueError):
            classes_a.append(1)
    for item in summary.get('sectionB', []) or []:
        try:
            classes_b.append(max(1, int(item.get('num_classes', 1) or 1)))
        except (TypeError, ValueError):
            classes_b.append(1)
    if classes_a:
        payload['classes_a'] = classes_a
    if classes_b:
        payload['classes_b'] = classes_b
    payload['course_content_summary'] = json.dumps(summary, ensure_ascii=False)
    return payload


def finalize_outline_payload_for_save(payload):
    """Ensure AI outline payload is compatible with save_course_outline (SQLite text columns)."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    _serialize_course_content_summary(out)
    if 'assessment_strategy' in out and isinstance(out['assessment_strategy'], dict):
        out['assessment_strategy'] = normalize_assessment_strategy(out['assessment_strategy'])
    return out


def normalize_outline_payload(raw):
    """Map AI output to save_course_outline-compatible dict."""
    if not isinstance(raw, dict):
        raise ValueError('AI output must be a JSON object')

    payload = {}

    list_fields = [
        'course_objectives', 'clo_data', 'lesson_plan', 'assessment_techniques',
        'rubrics', 'grading_policy', 'cie_breakdown', 'smee_breakdown',
        'textbooks', 'reference_books', 'other_resources', 'course_file_components',
    ]
    text_fields = [
        'course_summary', 'prerequisites', 'contact_hours', 'cie_marks', 'smee_marks',
        'credit_value', 'course_type', 'level_term_section', 'make_up_procedures',
    ]
    dict_fields = [
        'plo_mapping', 'assessment_strategy', 'evaluation_policy', 'other_issues',
        'course_content_summary',
    ]

    for field in list_fields:
        if field in raw:
            payload[field] = _ensure_list(raw.get(field))
    for field in text_fields:
        if field in raw and raw.get(field) is not None:
            payload[field] = str(raw.get(field))
    for field in dict_fields:
        if field in raw:
            payload[field] = _ensure_dict(raw.get(field))

    _serialize_course_content_summary(payload)

    if 'plo_mapping' in payload and isinstance(payload['plo_mapping'], dict):
        payload['plo_mapping'] = payload['plo_mapping']
    if 'evaluation_policy' in payload and isinstance(payload['evaluation_policy'], dict):
        payload['evaluation_policy'] = payload['evaluation_policy']
    if 'assessment_strategy' in payload and isinstance(payload['assessment_strategy'], dict):
        payload['assessment_strategy'] = normalize_assessment_strategy(payload['assessment_strategy'])
    if 'other_issues' in payload and isinstance(payload['other_issues'], dict):
        payload['other_issues'] = payload['other_issues']

    if not payload:
        raise ValueError('AI response contained no usable outline fields')
    return payload


def merge_outline_payloads(*payloads):
    """Merge multiple part payloads into one save_course_outline dict (later keys win)."""
    merged = {}
    for payload in payloads:
        if not payload:
            continue
        if not isinstance(payload, dict):
            raise ValueError('Each outline payload must be a dict')
        for key, value in payload.items():
            if value is None:
                continue
            merged[key] = value
    if not merged:
        raise ValueError('No outline fields to merge')
    return finalize_outline_payload_for_save(merged)
