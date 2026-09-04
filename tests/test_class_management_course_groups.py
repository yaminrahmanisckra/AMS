"""Active-course dashboard groups by UG/PG × Theory/Sessional, year-term desc."""
from types import SimpleNamespace

from blueprints.class_management.routes import (
    _active_session_sort_key,
    _group_active_sessions_for_dashboard,
    _year_term_rank,
)


def _session(**kwargs):
    defaults = dict(
        id=1,
        course_name='Course',
        course_code='0421 28 Law 4101',
        course_type='theory',
        category='ug',
        year='First',
        term='First',
        academic_session='2024-25',
        course_scope='full',
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_year_term_rank_orders_labels():
    assert _year_term_rank('Fourth') > _year_term_rank('First')
    assert _year_term_rank('Second Term') > _year_term_rank('First')
    assert _year_term_rank('LLM') > _year_term_rank('Fourth Year')


def test_sort_key_puts_higher_year_and_term_first():
    fourth_first = _session(id=1, year='Fourth', term='First', course_code='A')
    fourth_second = _session(id=2, year='Fourth', term='Second', course_code='B')
    third_second = _session(id=3, year='Third', term='Second', course_code='C')
    ordered = sorted([fourth_first, third_second, fourth_second], key=_active_session_sort_key)
    assert [s.id for s in ordered] == [2, 1, 3]


def test_group_active_sessions_splits_level_and_kind(app):
    with app.app_context():
        ug_theory_low = _session(id=1, course_name='UG Theory First', year='First', term='First')
        ug_theory_high = _session(id=2, course_name='UG Theory Fourth', year='Fourth', term='Second')
        ug_sessional = _session(
            id=3, course_name='UG Sessional', course_type='sessional',
            year='Fourth', term='First',
        )
        pg_theory = _session(
            id=4, course_name='PG Theory', category='pg', year='LLM',
            term='Second', course_code='0421 28 Law 5209',
        )
        groups = _group_active_sessions_for_dashboard(
            [ug_theory_low, pg_theory, ug_sessional, ug_theory_high]
        )

    assert [g['id'] for g in groups] == ['pg', 'ug']
    ug_kinds = {kind['id']: kind for kind in groups[1]['kinds']}
    assert list(ug_kinds) == ['ug-theory', 'ug-sessional']
    assert [s.id for s in ug_kinds['ug-theory']['sessions']] == [2, 1]
    assert [s.id for s in ug_kinds['ug-sessional']['sessions']] == [3]
    assert groups[0]['kinds'][0]['id'] == 'pg-theory'
    assert [s.id for s in groups[0]['kinds'][0]['sessions']] == [4]


def test_empty_groups_are_omitted(app):
    with app.app_context():
        groups = _group_active_sessions_for_dashboard([
            _session(id=10, category='pg', year='LLM', term='First', course_type='sessional'),
        ])
    assert [g['id'] for g in groups] == ['pg']
    assert [k['id'] for k in groups[0]['kinds']] == ['pg-sessional']
