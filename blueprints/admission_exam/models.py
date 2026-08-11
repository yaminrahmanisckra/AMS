"""Admission Exam models: self-contained module for masters admission cycles.

No coupling with the rest of the app except User (for committee access control
and payment-verification audit fields).
"""
from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from utils.timezone import bd_now_naive as _bd_now_naive, format_bd


class AdmissionCycle(db.Model):
    """One admission exam run (e.g. 'LLM Admission 2026'). Has a unique public link."""
    __tablename__ = 'admission_cycle'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    public_token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='draft')  # draft / open / closed
    # Master switch: when False, public apply link is unavailable (admin can still manage).
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    fee_amount = db.Column(db.String(20), nullable=True)
    rocket_account_number = db.Column(db.String(50), nullable=True)
    bkash_account_number = db.Column(db.String(50), nullable=True)
    nagad_account_number = db.Column(db.String(50), nullable=True)
    # Comma-separated method keys — which payment options applicants may use.
    payment_methods_enabled = db.Column(db.String(120), nullable=False, default='agrani_bank')
    agrani_account_number = db.Column(db.String(80), nullable=True)
    agrani_account_name = db.Column(db.String(120), nullable=True)
    agrani_routing_number = db.Column(db.String(40), nullable=True)
    agrani_branch = db.Column(db.String(120), nullable=True)
    apply_start = db.Column(db.DateTime, nullable=True)
    apply_end = db.Column(db.DateTime, nullable=True)
    app_id_prefix = db.Column(db.String(20), nullable=False, default='APP')
    roll_prefix = db.Column(db.String(20), nullable=False, default='')
    roll_start = db.Column(db.Integer, nullable=False, default=1)
    # Zero-pad numeric part: 0/1 = none, 2 = 01, 3 = 001, 4 = 0001, …
    roll_pad_width = db.Column(db.Integer, nullable=False, default=0)
    admit_published = db.Column(db.Boolean, nullable=False, default=False)
    instructions = db.Column(db.Text, nullable=True)
    # JSON list of field defs (form / admit card / application PDF). See fields.py.
    field_schema = db.Column(db.Text, nullable=True)
    # JSON list of suggested document tags for certificate/transcript uploads.
    document_tags = db.Column(db.Text, nullable=True)
    # Application form declaration text (customizable; NULL = use default).
    declaration_text = db.Column(db.Text, nullable=True)
    exam_date = db.Column(db.String(120), nullable=True)   # shown on admit card
    exam_venue = db.Column(db.String(200), nullable=True)  # shown on admit card
    chairman_signature_path = db.Column(db.String(255), nullable=True)  # image for admit card
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    committee_members = db.relationship(
        'AdmissionCommitteeMember', backref='cycle', lazy='dynamic',
        cascade='all, delete-orphan'
    )
    candidates = db.relationship(
        'AdmissionCandidate', backref='cycle', lazy='dynamic',
        cascade='all, delete-orphan'
    )

    @property
    def is_cycle_enabled(self):
        """False when admin has disabled the whole cycle (public link blocked)."""
        val = getattr(self, 'is_enabled', True)
        if isinstance(val, str):
            return val.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(val)

    @property
    def is_application_open(self):
        """Applications accepted only when enabled, status open, and within the window (if set)."""
        if not self.is_cycle_enabled:
            return False
        return self.application_closed_reason is None

    def enabled_payment_methods(self):
        """Ordered list of payment method keys enabled for this cycle."""
        from blueprints.admission_exam.fields import (
            ALL_PAYMENT_METHODS, DEFAULT_PAYMENT_METHOD, PAYMENT_METHOD_ORDER,
        )
        allowed = ALL_PAYMENT_METHODS
        raw = (self.payment_methods_enabled or DEFAULT_PAYMENT_METHOD).strip().lower()
        methods = []
        for part in raw.replace(';', ',').split(','):
            key = part.strip()
            if key in allowed and key not in methods:
                methods.append(key)
        if not methods:
            return [DEFAULT_PAYMENT_METHOD]
        # Stable display order
        order = {k: i for i, k in enumerate(PAYMENT_METHOD_ORDER)}
        methods.sort(key=lambda k: order.get(k, 99))
        return methods

    def payment_method_enabled(self, method):
        return method in self.enabled_payment_methods()

    def format_roll_number(self, n):
        """Build roll string: prefix + zero-padded (optional) numeric part."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 1
        prefix = self.roll_prefix or ''
        try:
            width = int(getattr(self, 'roll_pad_width', None) or 0)
        except (TypeError, ValueError):
            width = 0
        width = max(0, min(width, 8))
        body = str(n).zfill(width) if width >= 2 else str(n)
        return f'{prefix}{body}'

    @property
    def roll_start_display(self):
        return self.format_roll_number(self.roll_start or 1)

    def payment_account_number(self, method):
        method = (method or '').strip().lower()
        if method == 'rocket':
            return self.rocket_account_number
        if method == 'bkash':
            return self.bkash_account_number
        if method == 'nagad':
            return self.nagad_account_number
        if method == 'agrani_bank':
            return self.agrani_account_number
        return None

    @property
    def application_closed_reason(self):
        """None if accepting applications; otherwise a short human-readable reason."""
        if not self.is_cycle_enabled:
            return 'This admission cycle is currently disabled by the administrator.'
        status = (self.status or '').strip().lower()
        if status != 'open':
            if status == 'draft':
                return 'This cycle is still in draft.'
            return 'Applications are closed for this admission cycle.'
        now = _bd_now_naive()
        start = self.apply_start
        end = self.apply_end
        # Tolerate accidental timezone-aware values from the DB driver.
        if start is not None and getattr(start, 'tzinfo', None) is not None:
            start = start.replace(tzinfo=None)
        if end is not None and getattr(end, 'tzinfo', None) is not None:
            end = end.replace(tzinfo=None)
        if start and now < start:
            return (
                'Applications have not started yet'
                f' (opens {format_bd(start, "%d %B %Y, %I:%M %p", assume_utc=False)}).'
            )
        if end and now > end:
            return (
                'The application deadline has passed'
                f' ({format_bd(end, "%d %B %Y, %I:%M %p", assume_utc=False)}).'
            )
        return None

    def __repr__(self):
        return f"<AdmissionCycle {self.name}>"


class AdmissionCommitteeMember(db.Model):
    """Exam committee member for a cycle; selected from existing app users."""
    __tablename__ = 'admission_committee_member'
    id = db.Column(db.Integer, primary_key=True)
    cycle_id = db.Column(db.Integer, db.ForeignKey('admission_cycle.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    position = db.Column(db.String(30), nullable=False, default='member')  # chairman / member / officer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('admission_committee_memberships', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('cycle_id', 'user_id', name='uq_admission_committee_member'),
    )


class AdmissionCandidate(db.Model):
    """Candidate application; account is Application ID + PIN, fully separate from User."""
    __tablename__ = 'admission_candidate'
    id = db.Column(db.Integer, primary_key=True)
    cycle_id = db.Column(db.Integer, db.ForeignKey('admission_cycle.id'), nullable=False)
    application_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    pin_hash = db.Column(db.String(512), nullable=False)

    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    photo_path = db.Column(db.String(255), nullable=True)
    signature_path = db.Column(db.String(255), nullable=True)  # Applicant signature image
    extra_fields = db.Column(db.Text, nullable=True)  # JSON: form design finalized later

    # Payment (manual verification; no API)
    # agrani_bank | bkash | nagad | rocket
    payment_method = db.Column(db.String(20), nullable=False, default='agrani_bank')
    # Shared by bKash / Nagad / Rocket (MFS)
    rocket_txn_id = db.Column(db.String(60), nullable=True)
    rocket_sender_phone = db.Column(db.String(30), nullable=True)
    bank_slip_txn_no = db.Column(db.String(80), nullable=True)  # Agrani deposit / slip / txn no.
    bank_slip_path = db.Column(db.String(255), nullable=True)   # uploaded deposit slip image
    payment_status = db.Column(db.String(20), nullable=False, default='pending')  # pending / verified / rejected
    payment_note = db.Column(db.String(255), nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)

    application_status = db.Column(db.String(20), nullable=False, default='submitted')  # submitted / selected / rejected
    roll_no = db.Column(db.String(30), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    verifier = db.relationship('User', foreign_keys=[verified_by])
    documents = db.relationship(
        'AdmissionCandidateDocument', backref='candidate', lazy='dynamic',
        cascade='all, delete-orphan', order_by='AdmissionCandidateDocument.id',
    )

    __table_args__ = (
        db.UniqueConstraint('cycle_id', 'roll_no', name='uq_admission_candidate_roll'),
    )

    def set_pin(self, pin):
        self.pin_hash = generate_password_hash(pin, method='pbkdf2:sha512', salt_length=16)

    def check_pin(self, pin):
        return check_password_hash(self.pin_hash, pin)

    @property
    def can_download_admit(self):
        """Eligible when paid, has roll, not rejected, and admit cards are published."""
        if self.payment_status != 'verified' or not self.roll_no:
            return False
        if self.application_status == 'rejected':
            return False
        cycle = self.cycle
        if not cycle:
            return False
        published = cycle.admit_published
        if isinstance(published, str):
            return published.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(published)

    def __repr__(self):
        return f"<AdmissionCandidate {self.application_id}>"


class AdmissionCandidateDocument(db.Model):
    """Attested academic certificate / transcript upload for a candidate."""
    __tablename__ = 'admission_candidate_document'
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(
        db.Integer, db.ForeignKey('admission_candidate.id'), nullable=False, index=True
    )
    tag = db.Column(db.String(120), nullable=False)  # e.g. SSC Certificate / custom
    file_path = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending/verified/rejected
    note = db.Column(db.String(255), nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    verifier = db.relationship('User', foreign_keys=[verified_by])

    def __repr__(self):
        return f"<AdmissionCandidateDocument {self.id} {self.tag}>"
