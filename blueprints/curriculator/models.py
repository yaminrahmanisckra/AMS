"""Curriculator models: syllabus documents, parts (A/B/C/D), course entries, author assignments."""
from datetime import datetime
import json

from extensions import db


class SyllabusDocument(db.Model):
    """A syllabus document (e.g. LLB Revised Feb 2023)."""
    __tablename__ = 'syllabus_document'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    applicable_batches = db.Column(db.Text, nullable=True)  # Comma-separated batch values
    source_file = db.Column(db.String(500), nullable=True)  # Original docx path, if imported
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parts = db.relationship(
        'SyllabusPart',
        back_populates='document',
        cascade='all, delete-orphan',
        lazy='dynamic',
        order_by='SyllabusPart.sort_order',
    )

    def get_batches_list(self):
        if self.applicable_batches:
            return [b.strip() for b in self.applicable_batches.split(',') if b.strip()]
        return []

    def __repr__(self):
        return f'<SyllabusDocument {self.name}>'


class SyllabusPart(db.Model):
    """Part A / B / C / D of a syllabus document."""
    __tablename__ = 'syllabus_part'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('syllabus_document.id'), nullable=False)
    part_key = db.Column(db.String(10), nullable=False)  # A | B | C | D
    title = db.Column(db.String(200), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    # Rich text (HTML) or structured JSON; Part C uses course entries instead.
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = db.relationship('SyllabusDocument', back_populates='parts')
    course_entries = db.relationship(
        'SyllabusCourseEntry',
        back_populates='part',
        cascade='all, delete-orphan',
        lazy='dynamic',
        order_by='SyllabusCourseEntry.sort_order',
    )

    __table_args__ = (
        db.UniqueConstraint('document_id', 'part_key', name='uq_syllabus_part_doc_key'),
    )

    def __repr__(self):
        return f'<SyllabusPart {self.part_key} doc={self.document_id}>'


class SyllabusCourseEntry(db.Model):
    """Part C per-course block: course code, title, credit, year, content, CLOs, etc."""
    __tablename__ = 'syllabus_course_entry'
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey('syllabus_part.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)  # Link to Course (curriculum)
    # Denormalized for export/sync when course_id is null or override
    course_code = db.Column(db.String(50), nullable=True)
    course_name = db.Column(db.String(200), nullable=True)
    credit = db.Column(db.Float, nullable=True)
    year_term = db.Column(db.String(100), nullable=True)  # legacy / display; prefer year + term
    year = db.Column(db.String(50), nullable=True)       # e.g. First, Second, Third, Fourth, LLM
    term = db.Column(db.String(50), nullable=True)       # e.g. First, Second
    entry_type = db.Column(db.String(30), nullable=True) # Theory | Sessional | Viva | Capstone
    status = db.Column(db.String(30), nullable=True)     # Core | Optional | Non-Credit
    prerequisite_entry_id = db.Column(db.Integer, db.ForeignKey('syllabus_course_entry.id'), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    # Part C specific: Section A/B, CLOs (JSON), other rich content
    content_json = db.Column(db.Text, nullable=True)  # JSON: { "section_a": "...", "section_b": "...", "clos": [...] }
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    part = db.relationship('SyllabusPart', back_populates='course_entries')
    course = db.relationship('Course', foreign_keys=[course_id])
    prerequisite_entry = db.relationship(
        'SyllabusCourseEntry',
        remote_side='SyllabusCourseEntry.id',
        foreign_keys=[prerequisite_entry_id],
        backref=db.backref('prerequisite_for', lazy='dynamic'),
    )
    author_assignments = db.relationship(
        'SyllabusAuthorAssignment',
        back_populates='course_entry',
        cascade='all, delete-orphan',
        lazy='dynamic',
    )

    def get_content_dict(self):
        if not self.content_json:
            return {}
        try:
            return json.loads(self.content_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_content_dict(self, d):
        self.content_json = json.dumps(d) if d else None

    def __repr__(self):
        return f'<SyllabusCourseEntry {self.course_code or self.course_id}>'


class CurriculatorEditor(db.Model):
    """Users Head has granted add/remove syllabus permission (Head always has it)."""
    __tablename__ = 'curriculator_editor'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('user_models.User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<CurriculatorEditor user_id={self.user_id}>'


class SyllabusAuthorAssignment(db.Model):
    """Assigns a teacher to author Part C content for a specific course entry."""
    __tablename__ = 'syllabus_author_assignment'
    id = db.Column(db.Integer, primary_key=True)
    course_entry_id = db.Column(db.Integer, db.ForeignKey('syllabus_course_entry.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course_entry = db.relationship('SyllabusCourseEntry', back_populates='author_assignments')
    teacher = db.relationship('Teacher', backref=db.backref('syllabus_author_assignments', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('course_entry_id', 'teacher_id', name='uq_syllabus_author_entry_teacher'),
    )

    def __repr__(self):
        return f'<SyllabusAuthorAssignment entry={self.course_entry_id} teacher={self.teacher_id}>'


# --- Plan: table-style Part A/B/D structured storage + section ownership ---

class SyllabusPartASection(db.Model):
    """Part A structured sections (overview, PEOs, PLOs, mappings). One row per (part, section_key)."""
    __tablename__ = 'syllabus_part_a_section'
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey('syllabus_part.id'), nullable=False)
    section_key = db.Column(db.String(80), nullable=False)  # overview, peos, plos, mapping_mission_peo, etc.
    data = db.Column(db.Text, nullable=True)               # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    part = db.relationship(
        'SyllabusPart',
        backref=db.backref('part_a_sections', lazy='dynamic', cascade='all, delete-orphan'),
    )
    __table_args__ = (db.UniqueConstraint('part_id', 'section_key', name='uq_part_a_section_part_key'),)

    def get_data(self):
        if not self.data:
            return None
        try:
            return json.loads(self.data)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_data(self, obj):
        self.data = json.dumps(obj) if obj is not None else None


class SyllabusPartBConfig(db.Model):
    """Part B config and overrides (duration, term duration, area-wise, category). One row per Part B."""
    __tablename__ = 'syllabus_part_b_config'
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey('syllabus_part.id'), nullable=False, unique=True)
    config_json = db.Column(db.Text, nullable=True)  # {duration_years, terms, term_duration, area_wise_override, category_override}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    part = db.relationship(
        'SyllabusPart',
        backref=db.backref('part_b_config', uselist=False, cascade='all, delete-orphan'),
    )

    def get_config(self):
        if not self.config_json:
            return {}
        try:
            return json.loads(self.config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_config(self, obj):
        self.config_json = json.dumps(obj) if obj else None


class SyllabusPartDSection(db.Model):
    """Part D structured sections (grading_scale, theory_evaluation, sessional_evaluation)."""
    __tablename__ = 'syllabus_part_d_section'
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey('syllabus_part.id'), nullable=False)
    section_key = db.Column(db.String(80), nullable=False)
    data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    part = db.relationship(
        'SyllabusPart',
        backref=db.backref('part_d_sections', lazy='dynamic', cascade='all, delete-orphan'),
    )
    __table_args__ = (db.UniqueConstraint('part_id', 'section_key', name='uq_part_d_section_part_key'),)

    def get_data(self):
        if not self.data:
            return None
        try:
            return json.loads(self.data)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_data(self, obj):
        self.data = json.dumps(obj) if obj is not None else None


class SyllabusSectionAssignment(db.Model):
    """Head-assigned section owners for Part A (and optionally Part D). part_id + section_key -> user."""
    __tablename__ = 'syllabus_section_assignment'
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey('syllabus_part.id'), nullable=False)
    section_key = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    part = db.relationship(
        'SyllabusPart',
        backref=db.backref('section_assignments', lazy='dynamic', cascade='all, delete-orphan'),
    )
    user = db.relationship('user_models.User', foreign_keys=[user_id])

    __table_args__ = (db.UniqueConstraint('part_id', 'section_key', name='uq_section_assignment_part_key'),)
