"""Local stats for the IQAC student-feedback report (no AI call)."""
from datetime import datetime
from types import SimpleNamespace

from utils.ai.feedback_report import (
    anonymize_comment,
    build_feedback_dataset,
    compute_item_statistics,
    likert_score,
    _prompt_comments,
)


def test_likert_score_maps_labels_and_numbers():
    assert likert_score('Strongly disagree') == 1
    assert likert_score('Disagree') == 2
    assert likert_score('Neutral') == 3
    assert likert_score('Agree') == 4
    assert likert_score('Strongly Agree') == 5
    assert likert_score(4) == 4
    assert likert_score('') is None
    assert likert_score('not sure') is None


def test_item_statistics_mean_sd_and_favourable():
    stats = compute_item_statistics([5, 5, 4, 1, 2])
    assert stats['n'] == 5
    assert stats['mean'] == 3.4
    assert stats['favourable_pct'] == 60.0
    assert stats['high_sd'] is True


def test_item_statistics_empty():
    stats = compute_item_statistics([])
    assert stats['n'] == 0
    assert stats['mean'] is None
    assert stats['favourable_pct'] is None


def test_anonymize_comment_strips_identifiers():
    text = anonymize_comment('Email me at a@b.com roll no 210101 and 01712345678')
    assert 'a@b.com' not in text
    assert '210101' not in text
    assert '01712345678' not in text
    assert '[email removed]' in text
    assert '[identifier removed]' in text
    assert '[phone removed]' in text


def test_build_dataset_computes_overall_mean_and_comments(app, class_session_w1):
    from blueprints.class_management.models import Session

    with app.app_context():
        session = Session.query.get(class_session_w1['session_id'])
        link = SimpleNamespace(title='Jurisprudence Feedback')
        payload = {
            'section_a': {
                'course_structure': 'Agree',
                'course_goals': 'Strongly Agree',
                'course_content_guidance': 'Agree',
                'course_interest': 'Neutral',
            },
            'section_b': {
                'course_plan_discussed': 'Agree',
                'guidelines_received': 'Agree',
                'assessment_helpful': 'Disagree',
                'feedback_timely': 'Disagree',
                'teaching_methods': ['Lectures (including online lectures)'],
            },
            'section_c': {
                'study_time': '> 2 – 3 hrs/wk',
                'attendance_percent': '80-100%',
                'effort_focus': ['Solving problems.'],
            },
            'section_d': {
                'likes': 'Clear lectures',
                'challenges': 'Feedback arrived late',
                'suggestions': 'Return scripts sooner',
            },
        }
        row = SimpleNamespace(payload=payload, submitted_at=datetime(2026, 5, 16, 11, 7))
        dataset = build_feedback_dataset(session, link, [row], enrolled_count=2)

    assert dataset['response_count'] == 1
    assert dataset['enrolled_count'] == 2
    assert dataset['response_rate'] == 50.0
    assert dataset['indicative_only'] is True
    assert dataset['comment_count'] == 1
    assert dataset['comments'][0]['challenges'] == 'Feedback arrived late'
    items = {item['item']: item for item in dataset['quantitative']['likert_items']}
    assert items['A2']['mean'] == 5.0
    assert items['B4']['mean'] == 2.0
    assert dataset['quantitative']['overall_mean'] is not None
    assert dataset['quantitative']['lowest_rated'][0]['item'] in ('B3', 'B4')


def _feedback_row(student_id, answers, submitted_at, row_id=1, comments=None):
    payload = {
        'respondent': {'student_id': student_id} if student_id else {},
        'section_a': {
            'course_structure': answers,
            'course_goals': answers,
            'course_content_guidance': answers,
            'course_interest': answers,
        },
        'section_b': {
            'course_plan_discussed': answers,
            'guidelines_received': answers,
            'assessment_helpful': answers,
            'feedback_timely': answers,
            'teaching_methods': ['Lectures (including online lectures)'],
        },
        'section_c': {},
        'section_d': comments or {
            'likes': f'Likes from {student_id or "anon"}',
            'challenges': 'Late scripts',
            'suggestions': 'Return work sooner',
        },
    }
    return SimpleNamespace(id=row_id, payload=payload, submitted_at=submitted_at)


def test_dataset_keeps_one_response_per_student(app, class_session_w1):
    from blueprints.class_management.models import Session
    from utils.ai.feedback_report import dedupe_feedback_responses

    first = datetime(2026, 10, 11, 9, 0)
    second = datetime(2026, 10, 13, 15, 0)
    rows = [
        _feedback_row('210101', 'Agree', first, row_id=1),
        _feedback_row('210101', 'Disagree', second, row_id=2),
        _feedback_row('210102', 'Agree', first, row_id=3),
        _feedback_row('210102', 'Agree', first, row_id=4),
        _feedback_row('', 'Neutral', first, row_id=5, comments={
            'likes': 'Same anonymous comment about lectures being structured well.',
            'challenges': 'Late scripts',
            'suggestions': 'Return work sooner',
        }),
        _feedback_row('', 'Neutral', second, row_id=6, comments={
            'likes': 'Same anonymous comment about lectures being structured well.',
            'challenges': 'Late scripts',
            'suggestions': 'Return work sooner',
        }),
    ]
    unique, excluded = dedupe_feedback_responses(rows)
    assert excluded == 3
    assert {row.id for row in unique} == {2, 4, 6}

    with app.app_context():
        session = Session.query.get(class_session_w1['session_id'])
        link = SimpleNamespace(title='Criminal Procedure Feedback')
        dataset = build_feedback_dataset(session, link, rows, enrolled_count=37)

    assert dataset['raw_response_count'] == 6
    assert dataset['response_count'] == 3
    assert dataset['duplicate_responses_excluded'] == 3
    assert dataset['response_rate'] == 8.1
    fields = {row['field']: row['value'] for row in dataset['profile']}
    assert fields['Valid responses received'] == '3'
    assert '3 later or repeat' in fields['Duplicate submissions excluded']
    items = {item['item']: item for item in dataset['quantitative']['likert_items']}
    # Latest 210101 answer is Disagree (2); 210102 Agree (4); anonymous Neutral (3)
    assert items['A1']['n'] == 3
    assert items['A1']['mean'] == 3.0


def test_dataset_does_not_collapse_different_students_with_same_answers(app, class_session_w1):
    from blueprints.class_management.models import Session

    when = datetime(2026, 10, 12, 10, 0)
    rows = [
        _feedback_row('210201', 'Agree', when, row_id=1),
        _feedback_row('210202', 'Agree', when, row_id=2),
        _feedback_row('210203', 'Agree', when, row_id=3),
    ]
    with app.app_context():
        session = Session.query.get(class_session_w1['session_id'])
        dataset = build_feedback_dataset(
            session, SimpleNamespace(title='Test'), rows, enrolled_count=3
        )
    assert dataset['response_count'] == 3
    assert dataset['duplicate_responses_excluded'] == 0


def test_prompt_comments_are_clipped_and_limited():
    comments = [{'likes': 'x' * 400, 'challenges': 'late scripts', 'suggestions': 'faster marks'}]
    comments.extend({'likes': f'ok {i}', 'challenges': '', 'suggestions': ''} for i in range(45))
    lines = _prompt_comments(comments, limit=40)
    assert lines[0].startswith('1. ')
    assert '…' in lines[0]
    assert any('further comments omitted' in line for line in lines)
    assert len(lines) == 41
