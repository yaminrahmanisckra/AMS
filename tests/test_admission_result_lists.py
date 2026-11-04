"""Eligible / selected result-list membership helpers."""
from blueprints.admission_exam.models import AdmissionCandidate, AdmissionCycle
from blueprints.admission_exam.routes import _result_list_candidates
from extensions import db


def _cycle(token='llmlists'):
    cycle = AdmissionCycle(
        name='LLM Lists',
        public_token=token,
        status='open',
        is_enabled=True,
    )
    db.session.add(cycle)
    db.session.flush()
    return cycle


def _candidate(cycle, app_id, *, status='submitted', roll=None):
    c = AdmissionCandidate(
        cycle_id=cycle.id,
        application_id=app_id,
        pin_hash='x',
        full_name=f'Name {app_id}',
        phone='01700000000',
        payment_status='verified',
        application_status=status,
        roll_no=roll,
    )
    c.set_pin('1234')
    db.session.add(c)
    return c


def test_eligible_list_includes_eligible_and_roll_holders(app):
    with app.app_context():
        cycle = _cycle('eligiblemix')
        _candidate(cycle, 'APP-E1', status='eligible')
        _candidate(cycle, 'APP-R1', status='submitted', roll='R01')
        _candidate(cycle, 'APP-S1', status='submitted')
        _candidate(cycle, 'APP-X1', status='rejected', roll='R99')
        db.session.commit()

        ids = {c.application_id for c in _result_list_candidates(cycle, 'eligible')}
        assert ids == {'APP-E1', 'APP-R1'}


def test_selected_list_only_selected(app):
    with app.app_context():
        cycle = _cycle('selectedonly')
        _candidate(cycle, 'APP-OK', status='selected', roll='S01')
        _candidate(cycle, 'APP-EL', status='eligible', roll='S02')
        db.session.commit()

        ids = {c.application_id for c in _result_list_candidates(cycle, 'selected')}
        assert ids == {'APP-OK'}
