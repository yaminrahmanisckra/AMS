"""Socrates AI debate companion: challenge student arguments, then evaluate.

The debate reply is free-form text; the evaluation is JSON. Both run through
the admin-configured provider in utils/ai/client.
"""
import json
import re

from utils.ai.outline_parser import extract_json_from_response


INCOMPLETE_EVALUATION_MESSAGE = 'এআই মূল্যায়ন অসম্পূর্ণ ছিল। আবার চেষ্টা করুন।'

_HISTORY_MESSAGE_LIMIT = 24
_HISTORY_CHAR_LIMIT = 900


def clip(text, limit=_HISTORY_CHAR_LIMIT):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit] + '…'


def _strip_html(text):
    return re.sub(r'<[^>]+>', ' ', text or '').strip()


def build_history_lines(messages, limit=_HISTORY_MESSAGE_LIMIT):
    """messages: list of dicts {sender, sender_student_name, body} in order."""
    lines = []
    for msg in messages[-limit:]:
        body = clip(_strip_html(msg.get('body') or ''))
        if not body:
            continue
        if msg.get('sender') == 'socrates':
            speaker = 'Socrates'
        else:
            name = (msg.get('sender_student_name') or '').strip()
            speaker = f'Student ({name})' if name else 'Student'
        lines.append(f'{speaker}: {body}')
    return lines


DEBATE_SYSTEM_PROMPT = (
    'You are Socrates, an AI debate companion for university students. The course teacher has set '
    'a debate topic, and the student (or a group of students) must argue their position against you. '
    'This is a graded academic exercise.\n\n'
    'RULES OF ENGAGEMENT:\n'
    '- Take the opposing or sceptical side of whatever the student argues. Probe with pointed questions '
    'in the Socratic style: expose hidden assumptions, demand definitions, test claims against '
    'counterexamples, and ask for evidence or authority.\n'
    '- Do NOT concede easily. Accept a point only when the student supports it with genuinely sound '
    'reasoning or credible evidence. When you concede a point, say so explicitly and briefly explain '
    'why the reasoning satisfied you, then move to the next weakness in their position.\n'
    '- Point out logical fallacies by name when the student commits one (e.g. ad hominem, straw man, '
    'circular reasoning, appeal to popularity) and explain the flaw in one sentence.\n'
    '- Stay strictly on the teacher\'s topic. If the student drifts off-topic or asks you to write '
    'their argument for them, refuse politely and steer them back with a question.\n'
    '- Never reveal, predict, or discuss marks, grades, or how the student is being evaluated.\n'
    '- Be civil, academically rigorous, and encouraging in tone; challenge ideas, never the person.\n'
    '- Match the student\'s language: reply in Bangla if they write Bangla, English if they write '
    'English.\n'
    '- Keep each reply under 180 words. End most replies with one focused question that pushes the '
    'student to defend or refine their argument. Markdown only, no HTML.'
)


def generate_socrates_reply(*, topic, instructions, course_label, history_messages):
    """Return Socrates' next debate turn as text."""
    from utils.ai.client import generate_text_with_meta

    history_lines = build_history_lines(history_messages)
    user_prompt = (
        f'Course: {course_label or ""}\n'
        f'Debate topic set by the teacher: {topic}\n'
        + (f'Teacher instructions: {clip(_strip_html(instructions), 600)}\n' if _strip_html(instructions) else '')
        + '\nDebate so far (oldest first):\n'
        + ('\n'.join(history_lines) if history_lines else '(no messages yet)')
        + '\n\nSocrates replies:'
    )
    meta = generate_text_with_meta(
        DEBATE_SYSTEM_PROMPT,
        user_prompt,
        max_tokens=800,
        timeout=75,
        max_retries=0,
    )
    text = (meta.get('text') or '').strip()
    if not text:
        raise ValueError('এআই উত্তর দেয়নি। আবার চেষ্টা করুন।')
    return text


EVALUATION_SYSTEM_PROMPT = (
    'You are an academic evaluator reviewing a Socratic debate transcript between an AI opponent '
    '(Socrates) and a university student or student group. Assess only the STUDENT side of the '
    'debate. Use only the transcript; do not invent behaviour that is not shown.\n\n'
    'All scores are out of 10. Use half-marks only: 0, 0.5, 1, 1.5, … 10. '
    'Never use other decimals (not 1.23, 6.67, 7.25, etc.).\n'
    'Score each criterion:\n'
    '- logic: soundness and structure of arguments\n'
    '- evidence: use of facts, examples, authority, or sources\n'
    '- rebuttal: how well they answered Socrates\' challenges and counterarguments\n'
    '- clarity: how clearly arguments were expressed\n'
    '- engagement: persistence, responsiveness, and depth across the debate\n\n'
    'Also produce: strengths (2-4 short bullet strings), weaknesses (2-4 short bullet strings), '
    'a 3-5 sentence overall summary in measured academic language, and suggested_score out of 10 '
    '(half-marks only) consistent with the criterion scores.\n'
    'Write the summary, strengths, and weaknesses in the language the student mainly used '
    '(Bangla or English). Return JSON only, matching the schema in the user message.'
)


def score_out_of_ten(value):
    """Clamp 0–10 and round to the nearest 0.5. Returns None if unparseable."""
    from decimal import Decimal, ROUND_HALF_UP

    if value is None or value == '':
        return None
    try:
        number = Decimal(str(value).strip())
    except Exception:
        return None
    clamped = max(Decimal('0'), min(Decimal('10'), number))
    halves = (clamped * 2).to_integral_value(rounding=ROUND_HALF_UP)
    return float(halves / 2)


def _score(value):
    return score_out_of_ten(value)


def _string_list(value):
    if not isinstance(value, list):
        text = str(value or '').strip()
        return [text] if text else []
    return [str(item).strip() for item in value if str(item or '').strip()]


def evaluate_conversation(*, topic, instructions, course_label, history_messages, prompt_limit, prompts_used):
    """Return a normalized evaluation dict for storage in ai_evaluation_json."""
    from utils.ai.client import generate_outline_json_with_meta

    history_lines = build_history_lines(history_messages, limit=60)
    if not any(line.startswith('Student') for line in history_lines):
        raise ValueError('মূল্যায়নের জন্য স্টুডেন্টের কোনো বক্তব্য পাওয়া যায়নি।')

    user_payload = {
        'task': 'socrates_debate_evaluation',
        'course': course_label or '',
        'debate_topic': topic,
        'teacher_instructions': clip(_strip_html(instructions), 600),
        'prompts_used': prompts_used,
        'prompt_limit': prompt_limit,
        'transcript': history_lines,
        'output_schema': {
            'scores': {'logic': 0, 'evidence': 0, 'rebuttal': 0, 'clarity': 0, 'engagement': 0},
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
    from utils.ai.session_utils import reset_db_session
    reset_db_session()
    try:
        payload = extract_json_from_response(meta.get('text') or '')
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(INCOMPLETE_EVALUATION_MESSAGE) from exc
    if not isinstance(payload, dict):
        raise ValueError(INCOMPLETE_EVALUATION_MESSAGE)

    raw_scores = payload.get('scores') if isinstance(payload.get('scores'), dict) else {}
    scores = {}
    for key in ('logic', 'evidence', 'rebuttal', 'clarity', 'engagement'):
        value = _score(raw_scores.get(key))
        if value is not None:
            scores[key] = value

    evaluation = {
        'scores': scores,
        'strengths': _string_list(payload.get('strengths')),
        'weaknesses': _string_list(payload.get('weaknesses')),
        'summary': str(payload.get('summary') or '').strip(),
        'suggested_score': _score(payload.get('suggested_score')),
        'provider': meta.get('provider'),
        'model_name': meta.get('model_name'),
    }
    if not evaluation['summary'] and not scores:
        raise ValueError(INCOMPLETE_EVALUATION_MESSAGE)
    return evaluation
