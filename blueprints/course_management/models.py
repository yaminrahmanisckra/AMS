from extensions import db
from datetime import datetime
from sqlalchemy import or_
import json
"""
NOTE:
Do NOT import Student model here; it creates a circular import:
course_management.models -> student_management.models/routes -> course_management.models
Relationships use string model names (e.g. 'Student'), which is sufficient for SQLAlchemy.
"""


class Curriculum(db.Model):
    __tablename__ = 'curriculum'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(50), nullable=True)  # Date as string (e.g., "15 January 2025")
    applicable_batches = db.Column(db.Text, nullable=True)  # Comma-separated batch values
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    courses = db.relationship('Course', back_populates='curriculum', cascade="all, delete-orphan", lazy='dynamic')
    year_term_configs = db.relationship('CurriculumYearTerm', back_populates='curriculum', cascade="all, delete-orphan", lazy='dynamic')

    def get_batches_list(self):
        """Return applicable batches as a list"""
        if self.applicable_batches:
            return [b.strip() for b in self.applicable_batches.split(',') if b.strip()]
        return []

    def _year_term_configs_for_window(self, window_id=None):
        """Year/term rows scoped to an operational window."""
        query = self.year_term_configs
        if window_id is None:
            try:
                from utils.window_utils import get_effective_window_id, DEFAULT_WINDOW_ID
                window_id = get_effective_window_id(admin_override=False)
                if window_id is None:
                    window_id = DEFAULT_WINDOW_ID
            except ImportError:
                window_id = 1
        if window_id is not None:
            query = query.filter(
                or_(
                    CurriculumYearTerm.window_id == window_id,
                    CurriculumYearTerm.window_id.is_(None),
                )
            )
        return query

    def get_year_term_config(self, year, term, window_id=None):
        """Get configuration for a specific year/term combination in the active window."""
        scoped = self._year_term_configs_for_window(window_id)
        # Fast path: exact stored values
        exact = scoped.filter_by(year=year, term=term).order_by(
            CurriculumYearTerm.updated_at.desc(),
            CurriculumYearTerm.id.desc()
        ).first()
        if exact:
            return exact

        # Fallback: normalize common label variations (e.g., LLM <-> Fifth, 1st <-> First)
        def _norm(value, is_term=False):
            if value is None:
                return ''
            v = str(value).strip().lower()
            if is_term:
                term_map = {
                    '1': 'first', '1st': 'first', 'first': 'first',
                    '2': 'second', '2nd': 'second', 'second': 'second',
                }
                return term_map.get(v, v)
            year_map = {
                '1': 'first', '1st': 'first', 'first': 'first',
                '2': 'second', '2nd': 'second', 'second': 'second',
                '3': 'third', '3rd': 'third', 'third': 'third',
                '4': 'fourth', '4th': 'fourth', 'fourth': 'fourth',
                '5': 'fifth', '5th': 'fifth', 'fifth': 'fifth',
                'llm': 'fifth',
            }
            return year_map.get(v, v)

        target_year = _norm(year, is_term=False)
        target_term = _norm(term, is_term=True)
        matched_configs = []
        for cfg in scoped.all():
            if _norm(cfg.year, is_term=False) == target_year and _norm(cfg.term, is_term=True) == target_term:
                matched_configs.append(cfg)
        if not matched_configs:
            return None
        return sorted(
            matched_configs,
            key=lambda cfg: (cfg.updated_at or datetime.min, cfg.id or 0),
            reverse=True
        )[0]

    def __repr__(self):
        return f'<Curriculum {self.name}>'


class CurriculumYearTerm(db.Model):
    __tablename__ = 'curriculum_year_term'
    id = db.Column(db.Integer, primary_key=True)
    curriculum_id = db.Column(db.Integer, db.ForeignKey('curriculum.id'), nullable=False)
    year = db.Column(db.String(50), nullable=False)  # Year (e.g., "First", "Second")
    term = db.Column(db.String(50), nullable=False)  # Term (e.g., "First", "Second")
    batch = db.Column(db.String(20), nullable=True)  # Batch (dropdown selection)
    academic_session = db.Column(db.String(50), nullable=True)  # Academic Session (text input)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    curriculum = db.relationship('Curriculum', back_populates='year_term_configs')
    operational_window = db.relationship('OperationalWindow', backref=db.backref('curriculum_year_terms', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint(
            'window_id', 'curriculum_id', 'year', 'term', 'academic_session',
            name='uq_curriculum_year_term_window_session',
        ),
    )

    def __repr__(self):
        return f'<CurriculumYearTerm {self.curriculum_id} - {self.year} - {self.term}>'

class Course(db.Model):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True)
    curriculum_id = db.Column(db.Integer, db.ForeignKey('curriculum.id'), nullable=True)
    course_code = db.Column(db.String(20), nullable=False)
    course_name = db.Column(db.String(100), nullable=False)
    credit = db.Column(db.Float, nullable=False)
    course_type = db.Column(db.String(20), nullable=False)  # Theory/Sessional/Viva
    category = db.Column(db.String(20), nullable=False, default='ug') # UG/PG
    core_optional = db.Column(db.String(20), nullable=True)  # Core/Optional
    syllabus_year = db.Column(db.String(20), nullable=True)  # Syllabus Year
    offered = db.Column(db.Boolean, default=True, nullable=False)  # Whether the course is currently offered
    
    # Additional course information
    year = db.Column(db.String(50), nullable=True)  # Year (text field)
    term = db.Column(db.String(50), nullable=True)  # Term (text field)
    rationale = db.Column(db.Text, nullable=True)  # Course rationale
    clo = db.Column(db.Text, nullable=True)  # Course Learning Outcomes (JSON: list of {text, teaching_strategy, assessment_strategy, plo})
    content_section_a = db.Column(db.Text, nullable=True)  # Course content Section A
    content_section_b = db.Column(db.Text, nullable=True)  # Course content Section B
    
    def _extract_year_term_digits(self):
        """Return the last 4 numeric characters from the course code, if available."""
        if not self.course_code:
            return ''
        digits = ''.join(ch for ch in self.course_code if ch.isdigit())
        return digits[-4:] if len(digits) >= 4 else ''
    
    @staticmethod
    def _strip_label_suffix(label: str, suffix_word: str) -> str:
        """Remove a trailing suffix word (e.g., 'Year', 'Term') from a label."""
        if not label:
            return ''
        label = label.strip()
        suffix = f' {suffix_word.lower()}'
        if label.lower().endswith(suffix):
            return label[:-len(suffix)].strip()
        return label
    
    @property
    def derived_year(self):
        """Infer the academic year from the course code when year is not stored."""
        digits = self._extract_year_term_digits()
        if len(digits) < 4:
            return ''
        mapping = {
            '1': 'First',
            '2': 'Second',
            '3': 'Third',
            '4': 'Fourth',
            '5': 'LLM'
        }
        return mapping.get(digits[0], '')
    
    @property
    def derived_term(self):
        """Infer the term/semester from the course code when term is not stored."""
        digits = self._extract_year_term_digits()
        if len(digits) < 4:
            return ''
        mapping = {
            '1': 'First',
            '2': 'Second'
        }
        return mapping.get(digits[1], '')
    
    @property
    def display_year(self):
        """Year label with any trailing 'Year' suffix removed for cleaner display."""
        base = self.year or self.derived_year
        normalized = self._strip_label_suffix(base, 'year')
        return normalized or base or ''
    
    @property
    def display_term(self):
        """Term label with any trailing 'Term' suffix removed for cleaner display."""
        base = self.term or self.derived_term
        normalized = self._strip_label_suffix(base, 'term')
        return normalized or base or ''
    
    def get_clos_list(self):
        """Return CLOs as a list of dictionaries"""
        if self.clo:
            try:
                return json.loads(self.clo)
            except (json.JSONDecodeError, TypeError):
                # Legacy format: plain text, convert to list
                if self.clo.strip():
                    return [{'text': self.clo, 'teaching_strategy': '', 'assessment_strategy': '', 'plo': ''}]
        return []
    
    def set_clos_list(self, clos_list):
        """Set CLOs from a list of dictionaries"""
        if clos_list:
            self.clo = json.dumps(clos_list)
        else:
            self.clo = None

    # Relationships
    curriculum = db.relationship('Curriculum', back_populates='courses')
    assigned_teachers = db.relationship('AssignedCourse', back_populates='course', cascade="all, delete-orphan", lazy='dynamic')

    __table_args__ = (
        # Allow same course code in different curricula, but unique within same curriculum
        db.UniqueConstraint('curriculum_id', 'course_code', name='uq_curriculum_course_code'),
    )

    def __repr__(self):
        return f'<Course {self.course_code}>'


class CourseSessionAssignment(db.Model):
    """Model to assign Teacher and Section to Course for automatic Session creation in Class Management"""
    __tablename__ = 'course_session_assignment'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    curriculum_id = db.Column(db.Integer, db.ForeignKey('curriculum.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    section = db.Column(db.String(10), nullable=True)  # A, B, or null for Full
    batch = db.Column(db.String(20), nullable=True)  # Batch from CurriculumYearTerm
    year = db.Column(db.String(50), nullable=False)  # Year from Course
    term = db.Column(db.String(50), nullable=False)  # Term from Course
    academic_session = db.Column(db.String(50), nullable=True)  # Academic Session from CurriculumYearTerm
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    session_created = db.Column(db.Boolean, default=False, nullable=False)  # Whether Session has been created
    session_id = db.Column(db.Integer, nullable=True)  # ID of created Session in Class Management
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    course = db.relationship('Course', backref=db.backref('session_assignments', lazy='dynamic'))
    curriculum = db.relationship('Curriculum', backref=db.backref('session_assignments', lazy='dynamic'))
    teacher = db.relationship('Teacher', lazy='joined')
    operational_window = db.relationship('OperationalWindow', backref=db.backref('session_assignments', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint(
            'window_id', 'course_id', 'teacher_id', 'section', 'year', 'term', 'batch',
            name='uq_course_session_assignment_window'
        ),
    )
    
    def __repr__(self):
        section_text = f" Section {self.section}" if self.section else " Full"
        return f'<CourseSessionAssignment {self.course_id} -> Teacher {self.teacher_id}{section_text}>'


class StudentCourseRegistration(db.Model):
    __tablename__ = 'student_course_registration'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    academic_session = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(20), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    # Source year/term keeps course-origin metadata for mixed regular+retake registration.
    # Running processing scope still uses academic_session/year/term above.
    source_year = db.Column(db.String(20), nullable=True)
    source_term = db.Column(db.String(20), nullable=True)
    # Relevant-course mapping for retake/re-retake:
    # evaluator/question-setter/committee count may use this context,
    # while marks/result remain on original course_code context.
    relevant_course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    relevant_course_code = db.Column(db.String(50), nullable=True)
    relevant_academic_session = db.Column(db.String(50), nullable=True)
    relevant_year = db.Column(db.String(20), nullable=True)
    relevant_term = db.Column(db.String(20), nullable=True)
    # Retake merge control:
    # True  -> committee/remuneration count may merge through relevant-course context.
    # False -> keep separate; count only in original retake subject context.
    use_relevant_for_committee = db.Column(db.Boolean, nullable=False, default=True)
    course_code = db.Column(db.String(50), nullable=False)
    course_name = db.Column(db.String(150), nullable=False)
    credit = db.Column(db.Float, nullable=False)
    course_type = db.Column(db.String(30), nullable=False)
    nature = db.Column(db.String(20), nullable=False, default='Core')
    remark = db.Column(db.String(20), nullable=False, default='Regular')
    carry_on = db.Column(db.Boolean, nullable=False, default=False)  # Carry on previous assessment marks for retake students
    status = db.Column(db.String(20), nullable=False, default='draft')  # draft | pending | finalized
    registered_by = db.Column(db.String(20), nullable=False, default='student')  # 'student' | 'coordinator' | 'head' - who initiated the registration
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('course_registrations', lazy='dynamic', cascade='all, delete-orphan'))
    course = db.relationship(
        'Course',
        foreign_keys=[course_id],
        backref=db.backref('student_registrations', lazy='dynamic')
    )
    relevant_course = db.relationship('Course', foreign_keys=[relevant_course_id], lazy='joined')

    __table_args__ = (
        db.UniqueConstraint(
            'window_id', 'student_id', 'academic_session', 'year', 'term', 'course_code',
            name='uq_student_course_term_window',
        ),
    )


class CourseRegistrationInvite(db.Model):
    __tablename__ = 'course_registration_invite'
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey('student_course_registration.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    coordinator_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | accepted | finalized | declined
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    
    registration = db.relationship('StudentCourseRegistration', backref=db.backref('invites', lazy='dynamic', cascade='all, delete-orphan'))
    student = db.relationship('Student', backref=db.backref('registration_invites', lazy='dynamic', cascade='all, delete-orphan'))
    coordinator = db.relationship('Teacher', foreign_keys=[coordinator_teacher_id], backref=db.backref('course_registration_invites', lazy='dynamic'))
    operational_window = db.relationship('OperationalWindow', backref=db.backref('course_registration_invites', lazy='dynamic'))


class DutyAssignment(db.Model):
    __tablename__ = 'duty_assignment'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    course_code = db.Column(db.String(50), nullable=True)  # For courses not in curriculum
    course_name = db.Column(db.String(150), nullable=True)
    academic_session = db.Column(db.String(50), nullable=True)
    year = db.Column(db.String(20), nullable=True)
    term = db.Column(db.String(20), nullable=True)
    batch = db.Column(db.String(20), nullable=True)  # Batch for course coordinator assignment
    duty_type = db.Column(db.String(50), nullable=False)  # course_coordinator | tabulator | teaching_assistant | scrutinizer
    assigned_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=True)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Head who assigned
    remarks = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='active')  # active | inactive
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    course = db.relationship('Course', backref=db.backref('duty_assignments', lazy='dynamic'))
    operational_window = db.relationship('OperationalWindow', backref=db.backref('duty_assignments', lazy='dynamic'))
    assigned_teacher = db.relationship('Teacher', foreign_keys=[assigned_teacher_id], backref=db.backref('duty_assignments', lazy='dynamic'))
    assigned_student = db.relationship('Student', foreign_keys=[student_id], backref=db.backref('assistant_duties', lazy='dynamic'))
    # Note: assigned_by relationship removed to avoid SQLAlchemy User class resolution issues
    # Use User.query.get(assigned_by_id) to access the user who assigned the duty
    
    __table_args__ = (
        db.Index('idx_duty_course_session', 'course_id', 'academic_session', 'year', 'term', 'duty_type'),
    )


class SessionArchive(db.Model):
    """Model to archive complete academic session data"""
    __tablename__ = 'session_archive'
    
    id = db.Column(db.Integer, primary_key=True)
    academic_session = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(50), nullable=True)
    term = db.Column(db.String(50), nullable=True)
    batch = db.Column(db.String(50), nullable=True)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    
    # Archive data (JSON format)
    archive_data = db.Column(db.Text, nullable=False)  # JSON string containing all archived data
    
    # Metadata
    archived_by = db.Column(db.String(100), nullable=True)  # User who archived
    archived_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    restored_at = db.Column(db.DateTime, nullable=True)
    restored_by = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # False if restored
    
    # Description/notes
    description = db.Column(db.String(500), nullable=True)

    operational_window = db.relationship('OperationalWindow', backref=db.backref('session_archives', lazy='dynamic'))
    
    def __repr__(self):
        return f'<SessionArchive {self.academic_session} - {self.year} - {self.term}>'
    
    def to_dict(self):
        """Convert archive to dictionary"""
        return {
            'id': self.id,
            'academic_session': self.academic_session,
            'year': self.year,
            'term': self.term,
            'batch': self.batch,
            'archived_by': self.archived_by,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'restored_at': self.restored_at.isoformat() if self.restored_at else None,
            'restored_by': self.restored_by,
            'is_active': self.is_active,
            'description': self.description
        }


class OperationalWindow(db.Model):
    """Operational window: isolated partition for assignments, classes, registrations."""
    __tablename__ = 'operational_window'

    STATUS_DRAFT = 'draft'
    STATUS_RUNNING = 'running'
    STATUS_CLOSING = 'closing'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = (STATUS_DRAFT, STATUS_RUNNING, STATUS_CLOSING, STATUS_CLOSED)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    academic_session = db.Column(db.String(50), nullable=True)
    year = db.Column(db.String(50), nullable=True)
    term = db.Column(db.String(50), nullable=True)
    batch = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_RUNNING)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    activated_by = db.Column(db.String(100), nullable=True)
    activated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    deactivated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index('idx_operational_window_active', 'is_active', 'status'),
    )

    def __repr__(self):
        return f'<OperationalWindow {self.id}: {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'academic_session': self.academic_session,
            'year': self.year,
            'term': self.term,
            'batch': self.batch,
            'status': self.status,
            'is_active': self.is_active,
            'activated_by': self.activated_by,
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
            'deactivated_at': self.deactivated_at.isoformat() if self.deactivated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def display_label(self):
        parts = [self.name]
        if self.academic_session:
            parts.append(self.academic_session)
        if self.year and self.term:
            parts.append(f'{self.year} / {self.term}')
        return ' — '.join(parts)


class ActiveSemesterConfig(db.Model):
    """Model to manage active semester configuration"""
    __tablename__ = 'active_semester_config'
    
    id = db.Column(db.Integer, primary_key=True)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    academic_session = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(50), nullable=False)
    term = db.Column(db.String(50), nullable=False)
    batch = db.Column(db.String(50), nullable=True)  # NULL = All batches, or specific batch
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    activated_by = db.Column(db.String(100), nullable=True)  # User who activated
    activated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    deactivated_at = db.Column(db.DateTime, nullable=True)

    operational_window = db.relationship('OperationalWindow', backref=db.backref('active_semesters', lazy='dynamic'))
    
    __table_args__ = (
        db.Index('idx_active_semester', 'academic_session', 'year', 'term', 'batch', 'is_active'),
        db.Index('idx_active_semester_window', 'window_id', 'is_active'),
    )
    
    def __repr__(self):
        batch_str = f" - Batch: {self.batch}" if self.batch else ""
        return f'<ActiveSemesterConfig {self.academic_session} - {self.year} - {self.term}{batch_str}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        window_name = None
        if self.operational_window:
            window_name = self.operational_window.name
        return {
            'id': self.id,
            'window_id': self.window_id,
            'window_name': window_name,
            'academic_session': self.academic_session,
            'year': self.year,
            'term': self.term,
            'batch': self.batch,
            'is_active': self.is_active,
            'activated_by': self.activated_by,
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
            'deactivated_at': self.deactivated_at.isoformat() if self.deactivated_at else None
        }

