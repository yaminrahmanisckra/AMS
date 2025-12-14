from datetime import datetime
from extensions import db
from flask_login import current_user
import json

class RemunerationForm(db.Model):
    __tablename__ = 'remuneration_form'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User and status
    user_id = db.Column(db.Integer, nullable=False, index=True)
    status = db.Column(db.String(20), default='draft')  # 'draft' or 'archived'
    title = db.Column(db.String(200), nullable=True)  # Optional title for the form
    
    # Form metadata
    applicant_name = db.Column(db.String(200))
    designation = db.Column(db.String(200))
    address = db.Column(db.Text)
    discipline = db.Column(db.String(100))
    exam_discipline = db.Column(db.String(100))
    year = db.Column(db.String(50))
    term = db.Column(db.String(50))
    academic_year = db.Column(db.String(100))
    exam_start_date = db.Column(db.String(50))
    exam_end_date = db.Column(db.String(50))
    
    # Voucher info
    voucher_no = db.Column(db.String(100))
    voucher_date = db.Column(db.String(50))
    
    # Form data - stored as JSON for flexibility
    form_data = db.Column(db.Text)  # JSON string containing all form fields
    
    # Totals
    total_amount = db.Column(db.Float, default=0.0)
    total_in_words = db.Column(db.String(500))
    
    # Bank info
    bank_account = db.Column(db.String(100))
    bank_advice_no = db.Column(db.String(100))
    payment_date = db.Column(db.String(50))
    
    # Signature fields
    discipline_head_sign = db.Column(db.String(200))
    exam_committee_president_sign = db.Column(db.String(200))
    receiver_sign = db.Column(db.String(200))
    receiver_date = db.Column(db.String(50))
    
    # Controller signatures
    auditor_sign = db.Column(db.String(200))
    deputy_sign = db.Column(db.String(200))
    controller_sign = db.Column(db.String(200))
    
    # Finance signatures
    section_officer_sign = db.Column(db.String(200))
    deputy_director_sign = db.Column(db.String(200))
    director_sign = db.Column(db.String(200))
    finance_amount = db.Column(db.String(200))
    finance_amount_words = db.Column(db.String(500))
    
    # Audit signatures
    audit_assistant_sign = db.Column(db.String(200))
    audit_head_sign = db.Column(db.String(200))
    audit_amount = db.Column(db.String(200))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        """Convert form to dictionary"""
        form_data_json = {}
        if self.form_data:
            try:
                form_data_json = json.loads(self.form_data)
            except:
                pass
        
        return {
            'id': self.id,
            'user_id': self.user_id,
            'status': self.status,
            'title': self.title,
            'applicant_name': self.applicant_name,
            'designation': self.designation,
            'address': self.address,
            'discipline': self.discipline,
            'exam_discipline': self.exam_discipline,
            'year': self.year,
            'term': self.term,
            'academic_year': self.academic_year,
            'exam_start_date': self.exam_start_date,
            'exam_end_date': self.exam_end_date,
            'voucher_no': self.voucher_no,
            'voucher_date': self.voucher_date,
            'total_amount': self.total_amount,
            'total_in_words': self.total_in_words,
            'bank_account': self.bank_account,
            'bank_advice_no': self.bank_advice_no,
            'payment_date': self.payment_date,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'form_data': form_data_json
        }
    
    def __repr__(self):
        return f'<RemunerationForm {self.id}: {self.applicant_name} - {self.status}>'
























