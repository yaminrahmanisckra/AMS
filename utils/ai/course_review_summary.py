"""Course Review comment summaries from student feedback and peer observation."""
import json

from utils.ai.client import generate_outline_json_with_meta
from utils.ai.outline_parser import extract_json_from_response


def clip(text, limit=8000):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit] + '\n…[truncated]'


def collect_student_comments(session_id):
    from blueprints.class_management.models import StudentFeedbackLink, StudentFeedbackResponse

    links = StudentFeedbackLink.query.filter_by(session_id=session_id).all()
    comments = []
    for link in links:
        responses = StudentFeedbackResponse.query.filter_by(feedback_link_id=link.id).all()
        for row in responses:
            try:
                payload = json.loads(row.payload or '{}')
            except (json.JSONDecodeError, TypeError):
                continue
            section_d = payload.get('section_d') if isinstance(payload, dict) else None
            if not isinstance(section_d, dict):
                continue
            item = {}
            for key in ('likes', 'challenges', 'suggestions'):
                value = (section_d.get(key) or '').strip()
                if value:
                    item[key] = value
            if item:
                comments.append(item)
    return comments


def collect_peer_comments(session_id):
    from blueprints.class_management.models import EvaluationSubmission

    rows = EvaluationSubmission.query.filter_by(session_id=session_id).all()
    comments = []
    for row in rows:
        text = (row.comments_observer or '').strip()
        if text:
            comments.append(text)
    return comments


def summarize_course_review(session, sources='student', extra_fields=False):
    wanted = (sources or 'student').strip().lower()
    student_comments = collect_student_comments(session.id) if wanted in ('student', 'both') else []
    peer_comments = collect_peer_comments(session.id) if wanted in ('peer', 'both') else []

    if wanted == 'student' and not student_comments:
        raise ValueError('স্টুডেন্ট ওপেন-টেক্সট মন্তব্য পাওয়া যায়নি।')
    if wanted == 'peer' and not peer_comments:
        raise ValueError('পিয়ার পর্যবেক্ষণ মন্তব্য পাওয়া যায়নি।')
    if wanted == 'both' and not student_comments and not peer_comments:
        raise ValueError('সারাংশের জন্য কোনো মন্তব্য পাওয়া যায়নি।')

    fields = ['comment_student_questionnaires', 'comment_external_examiners']
    if extra_fields:
        fields.extend([
            'comment_curriculum',
            'comment_assessment',
            'comment_enhancement',
            'comment_future_changes',
        ])

    system_prompt = (
        'You summarize qualitative course-review comments for a faculty course review form. '
        'Use only the supplied comments. Never mention numeric grades or Likert scores. '
        'Write concise academic English (or Bangla if the comments are Bangla). Return JSON only.'
    )
    user_prompt = json.dumps({
        'task': 'course_review_comment_summary',
        'course': {
            'code': getattr(session, 'course_code', None),
            'name': getattr(session, 'course_name', None),
        },
        'student_comments': student_comments,
        'peer_observer_comments': peer_comments,
        'fill_keys': fields,
        'hints': {
            'comment_student_questionnaires': 'Themes from student likes/challenges/suggestions.',
            'comment_external_examiners': 'Themes from peer classroom observation comments.',
            'comment_future_changes': 'Actionable suggestions from student comments if present.',
        },
    }, ensure_ascii=False)

    meta = generate_outline_json_with_meta(system_prompt, clip(user_prompt), max_tokens=1800)
    payload = extract_json_from_response(meta.get('text') or '')
    if not isinstance(payload, dict):
        raise ValueError('এআই সারাংশ অসম্পূর্ণ ছিল।')
    return {key: (payload.get(key) or '').strip() for key in fields if (payload.get(key) or '').strip()}
