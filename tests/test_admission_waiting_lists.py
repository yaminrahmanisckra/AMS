"""Multiple named merit / waiting lists per admission cycle."""
from blueprints.admission_exam.models import (
    AdmissionCandidate, AdmissionCycle, AdmissionWaitingList,
)
from blueprints.admission_exam.routes import (
    _add_candidates_to_waiting_list, _ensure_standard_merit_lists,
)
from extensions import db


def test_multiple_waiting_lists_and_membership(app):
    with app.app_context():
        cycle = AdmissionCycle(
            name='LLM Wait',
            public_token='llmwait',
            status='open',
            is_enabled=True,
        )
        db.session.add(cycle)
        db.session.flush()

        c1 = AdmissionCandidate(
            cycle_id=cycle.id, application_id='W-1', pin_hash='x',
            full_name='One', phone='0171', payment_status='verified',
            application_status='eligible',
        )
        c1.set_pin('1111')
        c2 = AdmissionCandidate(
            cycle_id=cycle.id, application_id='W-2', pin_hash='x',
            full_name='Two', phone='0172', payment_status='verified',
            application_status='eligible',
        )
        c2.set_pin('2222')
        db.session.add_all([c1, c2])

        wl1 = AdmissionWaitingList(
            cycle_id=cycle.id, name='Waiting List 1', list_kind='waiting', sort_order=1
        )
        wl2 = AdmissionWaitingList(
            cycle_id=cycle.id, name='Waiting List 2', list_kind='waiting', sort_order=2
        )
        db.session.add_all([wl1, wl2])
        db.session.flush()

        assert _add_candidates_to_waiting_list(wl1, [c1, c2]) == 2
        assert _add_candidates_to_waiting_list(wl1, [c1]) == 0
        assert _add_candidates_to_waiting_list(wl2, [c2]) == 1
        db.session.commit()

        lists = (
            AdmissionWaitingList.query
            .filter_by(cycle_id=cycle.id, list_kind='waiting')
            .order_by(AdmissionWaitingList.sort_order)
            .all()
        )
        assert [w.name for w in lists] == ['Waiting List 1', 'Waiting List 2']
        assert [c.application_id for c in wl1.ordered_candidates()] == ['W-1', 'W-2']
        assert [r['rank'] for r in wl1.merit_rows()] == [1, 2]
        assert [c.application_id for c in wl2.ordered_candidates()] == ['W-2']


def test_ensure_viva_and_final_lists(app):
    with app.app_context():
        cycle = AdmissionCycle(
            name='LLM Merit',
            public_token='llmmerit',
            status='open',
            is_enabled=True,
        )
        db.session.add(cycle)
        db.session.commit()
        lists = _ensure_standard_merit_lists(cycle)
        kinds = {wl.kind_key for wl in lists}
        assert 'viva' in kinds
        assert 'final' in kinds
        again = _ensure_standard_merit_lists(cycle)
        assert len([w for w in again if w.kind_key == 'viva']) == 1
        assert len([w for w in again if w.kind_key == 'final']) == 1
