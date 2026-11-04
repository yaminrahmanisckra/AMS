"""Admission cycle can turn off academic certificate uploads."""
from blueprints.admission_exam.models import AdmissionCycle
from extensions import db


def test_documents_enabled_defaults_on(app):
    with app.app_context():
        cycle = AdmissionCycle(
            name='LLM 2027',
            public_token='llm2027docs',
            status='open',
            is_enabled=True,
        )
        db.session.add(cycle)
        db.session.commit()
        loaded = AdmissionCycle.query.filter_by(public_token='llm2027docs').one()
        assert loaded.is_documents_enabled is True


def test_documents_can_be_turned_off(app):
    with app.app_context():
        cycle = AdmissionCycle(
            name='LLM 2027 Off',
            public_token='llm2027docsoff',
            status='open',
            is_enabled=True,
            documents_enabled=False,
        )
        db.session.add(cycle)
        db.session.commit()
        loaded = AdmissionCycle.query.filter_by(public_token='llm2027docsoff').one()
        assert loaded.is_documents_enabled is False
