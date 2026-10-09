"""AI evaluation of a submitted written assignment, using the admin-configured provider."""
import json
from decimal import Decimal, ROUND_HALF_UP

from utils.ai.socrates import clip, score_out_of_ten


INCOMPLETE_EVALUATION_MESSAGE = 'এআই মূল্যায়ন অসম্পূর্ণ ছিল। আবার চেষ্টা করুন।'

_CRITERIA = ('argument', 'evidence', 'structure', 'clarity', 'relevance')

EVALUATION_SYSTEM_PROMPT = (
    'You are an academic evaluator reviewing a university written assignment. '
    'Assess only the submitted student writing. Use only the text given; do not invent '
    'sources, facts, or behaviour that are not in the writing.\n\n'
    'All criterion scores are out of 10. Use half-marks only: 0, 0.5, 1, 1.5, … 10. '
    'Never use other decimals.\n'
    'Score each criterion:\n'
    '- argument: reasoning and a clear position\n'
    '- evidence: facts, examples, authority, or sources actually used in the text\n'
    '- structure: organisation and flow\n'
    '- clarity: how clearly the writing is expressed\n'
    '- relevance: how directly it answers the teacher\'s instructions\n\n'
    'Also produce: strengths (2-4 short bullet strings), weaknesses (2-4 short bullet strings), '
    'a 3-5 sentence overall summary, and suggested_score out of 10 (half-marks only) consistent '
    'with the criterion scores.\n'
    'Write the summary, strengths, and weaknesses in the language the student mainly used '
    '(Bangla or English).\n'
    'Integrity hints such as focus loss, paste counts, or an AI-style flag are suspicions only. '
    'Do not treat them as proof of misconduct, and mention them only when they are present.\n'
    'Return JSON only, matching the schema in the user message.'
)


def scale_to_marks(score_out_of_ten, marks_out_of):
    """Map a 0–10 half-mark score onto the assignment's mark scale, still in half steps."""
    if score_out_of_ten is None:
        return None
    try:
        out_of = Decimal(str(int(marks_out_of)))
    except (TypeError, ValueError):
        out_of = Decimal('10')
    if out_of <= 0:
        out_of = Decimal('10')
    raw = Decimal(str(score_out_of_ten)) / Decimal('10') * out_of
    halves = (raw * 2).to_integral_value(rounding=ROUND_HALF_UP)
    return float(halves / 2)


def _string_list(value):
    if not isinstance(value, list):
        text = str(value or '').strip()
        return [text] if text else []
    return [str(item).strip() for item in value if str(item or '').strip()]


def evaluate_writing(*, title, instructions, course_label, marks_out_of, pieces, integrity_notes=None):
    """Return a normalized evaluation dict. pieces are {author, text} for submitted writing."""
    from utils.ai.client import generate_outline_json_with_meta
    from utils.ai.outline_parser import extract_json_from_response
    from utils.ai.session_utils import reset_db_session

    sections = []
    for piece in pieces or []:
        text = (piece.get('text') or '').strip()
        if not text:
            continue
        author = (piece.get('author') or 'Student').strip()
        sections.append(f'{author}:\n{text}')
    writing = '\n\n'.join(sections).strip()
    if not writing:
        raise ValueError('মূল্যায়নের জন্য জমা দেওয়া কোনো লেখা পাওয়া যায়নি।')

    user_payload = {
        'task': 'written_assignment_evaluation',
        'course': course_label or '',
        'title': title or '',
        'teacher_instructions': clip(instructions or '', 800),
        'marks_out_of': int(marks_out_of or 10),
        'integrity_hints': integrity_notes or [],
        'writing': clip(writing, 12000),
        'output_schema': {
            'scores': {key: 0 for key in _CRITERIA},
            'strengths': ['string'],
            'weaknesses': ['string'],
            'summary': 'string',
            'suggested_score': 0,
        },
    }
    meta = generate_outline_json_with_meta(
        EVALUATION_SYSTEM_PROMPT,
        clip(json.dumps(user_payload, ensure_ascii=False), limit=16000),
        max_tokens=2000,
    )
    reset_db_session()
    try:
        payload = extract_json_from_response(meta.get('text') or '')
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(INCOMPLETE_EVALUATION_MESSAGE) from exc
    if not isinstance(payload, dict):
        raise ValueError(INCOMPLETE_EVALUATION_MESSAGE)

    raw_scores = payload.get('scores') if isinstance(payload.get('scores'), dict) else {}
    scores = {}
    for key in _CRITERIA:
        value = score_out_of_ten(raw_scores.get(key))
        if value is not None:
            scores[key] = value
    suggested = score_out_of_ten(payload.get('suggested_score'))
    evaluation = {
        'scores': scores,
        'strengths': _string_list(payload.get('strengths')),
        'weaknesses': _string_list(payload.get('weaknesses')),
        'summary': str(payload.get('summary') or '').strip(),
        'suggested_score': suggested,
        'suggested_mark': scale_to_marks(suggested, marks_out_of),
        'marks_out_of': int(marks_out_of or 10),
        'provider': meta.get('provider'),
        'model_name': meta.get('model_name'),
    }
    if not evaluation['summary'] and not scores:
        raise ValueError(INCOMPLETE_EVALUATION_MESSAGE)
    return evaluation
