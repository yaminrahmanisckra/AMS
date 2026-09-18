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


def test_prompt_comments_are_clipped_and_limited():
    comments = [{'likes': 'x' * 400, 'challenges': 'late scripts', 'suggestions': 'faster marks'}]
    comments.extend({'likes': f'ok {i}', 'challenges': '', 'suggestions': ''} for i in range(45))
    lines = _prompt_comments(comments, limit=40)
    assert lines[0].startswith('1. ')
    assert '…' in lines[0]
    assert any('further comments omitted' in line for line in lines)
    assert len(lines) == 41
