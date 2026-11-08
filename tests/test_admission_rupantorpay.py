"""RupantorPay online MFS payments for admission exam."""
from unittest.mock import patch

from blueprints.admission_exam.models import AdmissionCandidate, AdmissionCycle
from blueprints.admission_exam.rupantorpay import (
    amounts_match,
    format_amount,
    parse_fee_amount,
)
from extensions import db


def _cycle_and_candidate(app, *, fee='500', method='bkash', status='pending'):
    with app.app_context():
        cycle = AdmissionCycle(
            name='LLM Pay',
            public_token='llmpay',
            status='open',
            is_enabled=True,
            fee_amount=fee,
            payment_methods_enabled='bkash,nagad,rocket,agrani_bank',
        )
        db.session.add(cycle)
        db.session.flush()
        candidate = AdmissionCandidate(
            cycle_id=cycle.id,
            application_id='PAY-1',
            pin_hash='x',
            full_name='Payee One',
            phone='01710000000',
            email='payee@example.com',
            payment_method=method,
            payment_status=status,
            application_status='submitted',
        )
        candidate.set_pin('1234')
        db.session.add(candidate)
        db.session.commit()
        return {
            'cycle_id': cycle.id,
            'candidate_id': candidate.id,
            'token': cycle.public_token,
            'application_id': candidate.application_id,
        }


def test_fee_helpers():
    assert parse_fee_amount('500') == 500.0
    assert parse_fee_amount('Tk. 500.50') == 500.50
    assert parse_fee_amount('') is None
    assert format_amount(500.0) == '500'
    assert amounts_match(500, '500.000')
    assert not amounts_match(500, '499')


def test_success_marks_verified_when_amount_matches(client, app):
    ids = _cycle_and_candidate(app)
    with client.session_transaction() as sess:
        sess['admission_candidate_id'] = ids['candidate_id']

    verified = {
        'status': 'COMPLETED',
        'transaction_id': 'TXN-1',
        'trx_id': 'BK123',
        'amount': '500.000',
        'payment_method': 'bkash',
        'metadata': {
            'application_id': ids['application_id'],
            'candidate_id': ids['candidate_id'],
            'cycle_id': ids['cycle_id'],
        },
        'raw': {},
    }
    with patch(
        'blueprints.admission_exam.rupantorpay.verify_payment',
        return_value=verified,
    ):
        rv = client.get(
            f"/admission-exam/apply/{ids['token']}/pay/success?transactionId=TXN-1",
            follow_redirects=False,
        )
    assert rv.status_code in (302, 303)

    with app.app_context():
        c = db.session.get(AdmissionCandidate, ids['candidate_id'])
        assert c.payment_status == 'verified'
        assert c.rocket_txn_id == 'BK123'
        assert c.payment_note == 'RupantorPay auto'
        assert c.payment_method == 'bkash'


def test_wrong_amount_stays_pending(client, app):
    ids = _cycle_and_candidate(app)
    with client.session_transaction() as sess:
        sess['admission_candidate_id'] = ids['candidate_id']

    verified = {
        'status': 'COMPLETED',
        'transaction_id': 'TXN-2',
        'trx_id': 'BK999',
        'amount': '100',
        'payment_method': 'bkash',
        'metadata': {
            'application_id': ids['application_id'],
            'candidate_id': ids['candidate_id'],
        },
        'raw': {},
    }
    with patch(
        'blueprints.admission_exam.rupantorpay.verify_payment',
        return_value=verified,
    ):
        client.get(f"/admission-exam/apply/{ids['token']}/pay/success?transactionId=TXN-2")

    with app.app_context():
        c = db.session.get(AdmissionCandidate, ids['candidate_id'])
        assert c.payment_status == 'pending'


def test_webhook_and_success_are_idempotent(client, app):
    ids = _cycle_and_candidate(app)
    verified = {
        'status': 'COMPLETED',
        'transaction_id': 'TXN-3',
        'trx_id': 'NG111',
        'amount': '500',
        'payment_method': 'nagad',
        'metadata': {
            'application_id': ids['application_id'],
            'candidate_id': ids['candidate_id'],
            'cycle_id': ids['cycle_id'],
        },
        'raw': {},
    }
    with patch(
        'blueprints.admission_exam.rupantorpay.verify_payment',
        return_value=verified,
    ):
        wh = client.post(
            f"/admission-exam/apply/{ids['token']}/pay/webhook",
            json={'transaction_id': 'TXN-3'},
        )
        assert wh.status_code == 200
        assert wh.get_json()['ok'] is True

        with client.session_transaction() as sess:
            sess['admission_candidate_id'] = ids['candidate_id']
        client.get(f"/admission-exam/apply/{ids['token']}/pay/success?transactionId=TXN-3")

    with app.app_context():
        c = db.session.get(AdmissionCandidate, ids['candidate_id'])
        assert c.payment_status == 'verified'
        assert c.rocket_txn_id == 'NG111'


def test_checkout_redirects_to_payment_url(client, app):
    ids = _cycle_and_candidate(app)
    with client.session_transaction() as sess:
        sess['admission_candidate_id'] = ids['candidate_id']

    with patch('blueprints.admission_exam.rupantorpay.is_configured', return_value=True), patch(
        'blueprints.admission_exam.rupantorpay.create_checkout',
        return_value='https://payment.rupantorpay.com/api/execute/abc',
    ) as create:
        rv = client.post(
            f"/admission-exam/apply/{ids['token']}/pay/online",
            data={'payment_method': 'bkash'},
            follow_redirects=False,
        )
    assert rv.status_code in (302, 303)
    assert 'payment.rupantorpay.com' in (rv.headers.get('Location') or '')
    assert create.called
