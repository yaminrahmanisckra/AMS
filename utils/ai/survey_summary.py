"""SAR Head comment-theme summaries. Ratings stay numeric and off-model."""
import json
import statistics

from utils.ai.client import generate_outline_json_with_meta
from utils.ai.outline_parser import extract_json_from_response
from utils.tenant import load_survey_pack


def clip(text, limit=10000):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit] + '\n…[truncated]'


def _payload_dict(row):
    raw = getattr(row, 'payload', None)
    if isinstance(raw, dict):
        return raw
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _text_question_meta(survey_type):
    pack = load_survey_pack(survey_type) or {}
    labels = {}
    text_keys = []
    rating_keys = []
    for section in pack.get('sections') or []:
        section_type = (section.get('type') or '').strip().lower()
        for q in section.get('questions') or []:
            key = q.get('key')
            if not key:
                continue
            labels[key] = q.get('text') or key
            if section_type == 'text':
                text_keys.append(key)
            elif section_type == 'rating':
                rating_keys.append(key)
    return text_keys, rating_keys, labels


def _is_number(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    text = str(value or '').strip()
    if not text:
        return False
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


def collect_comments_and_ratings(survey_type, responses):
    text_keys, rating_keys, labels = _text_question_meta(survey_type)
    comments = []
    rating_values = {key: [] for key in rating_keys}

    skip_id_keys = {'name', 'batch', 'graduation_year', 'csrf_token', 'form_version'}

    for row in responses:
        payload = _payload_dict(row)
        if not payload:
            continue
        for key, value in payload.items():
            if key in skip_id_keys:
                continue
            if key in rating_keys or (_is_number(value) and key not in text_keys):
                try:
                    rating_values.setdefault(key, []).append(float(value))
                except (TypeError, ValueError):
                    pass
                continue
            if isinstance(value, str) and value.strip() and (key in text_keys or (not _is_number(value) and len(value.strip()) >= 8)):
                comments.append({
                    'key': key,
                    'label': labels.get(key) or key,
                    'text': value.strip(),
                })

        # Alumni legacy open fields when payload is empty/partial
        for attr, label in (
            ('beneficial_course_activity', 'Beneficial course/activity'),
            ('improvement_suggestions', 'Improvement suggestions'),
            ('additional_comments', 'Additional comments'),
        ):
            extra = (getattr(row, attr, None) or '').strip()
            if extra:
                comments.append({'key': attr, 'label': label, 'text': extra})

    rating_means = {}
    for key, values in rating_values.items():
        if not values:
            continue
        rating_means[key] = {
            'label': labels.get(key) or key,
            'mean': round(statistics.mean(values), 2),
            'n': len(values),
        }
    return comments, rating_means


def summarize_survey_comments(survey_type, responses):
    comments, rating_means = collect_comments_and_ratings(survey_type, responses)
    if not comments:
        return {
            'themes': [],
            'notes': 'মন্তব্য নেই',
            'rating_means': rating_means,
            'comment_count': 0,
        }

    system_prompt = (
        'You are summarizing anonymous survey open-ended comments for a university Self-Assessment Report. '
        'Use only the comments. Do not mention or infer numeric ratings. '
        'Return JSON with themes (title, summary, quotes). Mix Bangla/English to match the comments.'
    )
    user_prompt = json.dumps({
        'survey_type': survey_type,
        'comments': comments[:80],
        'output_schema': {
            'themes': [{'title': '', 'summary': '', 'quotes': ['']}],
            'notes': '',
        },
    }, ensure_ascii=False)

    meta = generate_outline_json_with_meta(system_prompt, clip(user_prompt), max_tokens=2500)
    payload = extract_json_from_response(meta.get('text') or '')
    if not isinstance(payload, dict):
        payload = {}
    return {
        'themes': payload.get('themes') or [],
        'notes': payload.get('notes') or '',
        'rating_means': rating_means,
        'comment_count': len(comments),
    }
