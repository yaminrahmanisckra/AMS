from extensions import db
from datetime import datetime
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

    def get_year_term_config(self, year, term):
        """Get configuration for a specific year/term combination"""
        return self.year_term_configs.filter_by(year=year, term=term).first()

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    curriculum = db.relationship('Curriculum', back_populates='year_term_configs')
    
    __table_args__ = (
        db.UniqueConstraint('curriculum_id', 'year', 'term', name='uq_curriculum_year_term'),
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
    session_created = db.Column(db.Boolean, default=False, nullable=False)  # Whether Session has been created
    session_id = db.Column(db.Integer, nullable=True)  # ID of created Session in Class Management
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    course = db.relationship('Course', backref=db.backref('session_assignments', lazy='dynamic'))
    curriculum = db.relationship('Curriculum', backref=db.backref('session_assignments', lazy='dynamic'))
    teacher = db.relationship('Teacher', lazy='joined')
    
    __table_args__ = (
        # Prevent duplicate assignments for same course, teacher, section, year, term
        db.UniqueConstraint('course_id', 'teacher_id', 'section', 'year', 'term', 'batch', name='uq_course_session_assignment'),
    )
    
    def __repr__(self):
        section_text = f" Section {self.section}" if self.section else " Full"
        return f'<CourseSessionAssignment {self.course_id} -> Teacher {self.teacher_id}{section_text}>'


class StudentCourseRegistration(db.Model):
    __tablename__ = 'student_course_registration'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    academic_session = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(20), nullable=False)
    term = db.Column(db.String(20), nullable=False)
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

    student = db.relationship('Student', backref=db.backref('course_registrations', lazy='dynamic'))
    course = db.relationship('Course', backref=db.backref('student_registrations', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint(
            'student_id', 'academic_session', 'year', 'term', 'course_code',
            name='uq_student_course_term'
        ),
    )


class CourseRegistrationInvite(db.Model):
    __tablename__ = 'course_registration_invite'
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey('student_course_registration.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    coordinator_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | accepted | finalized | declined
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    
    registration = db.relationship('StudentCourseRegistration', backref=db.backref('invites', lazy='dynamic', cascade='all, delete-orphan'))
    student = db.relationship('Student', backref=db.backref('registration_invites', lazy='dynamic'))
    coordinator = db.relationship('Teacher', foreign_keys=[coordinator_teacher_id], backref=db.backref('course_registration_invites', lazy='dynamic'))


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    course = db.relationship('Course', backref=db.backref('duty_assignments', lazy='dynamic'))
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


class ActiveSemesterConfig(db.Model):
    """Model to manage active semester configuration"""
    __tablename__ = 'active_semester_config'
    
    id = db.Column(db.Integer, primary_key=True)
    academic_session = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(50), nullable=False)
    term = db.Column(db.String(50), nullable=False)
    batch = db.Column(db.String(50), nullable=True)  # NULL = All batches, or specific batch
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    activated_by = db.Column(db.String(100), nullable=True)  # User who activated
    activated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    deactivated_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        db.Index('idx_active_semester', 'academic_session', 'year', 'term', 'batch', 'is_active'),
    )
    
    def __repr__(self):
        batch_str = f" - Batch: {self.batch}" if self.batch else ""
        return f'<ActiveSemesterConfig {self.academic_session} - {self.year} - {self.term}{batch_str}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'academic_session': self.academic_session,
            'year': self.year,
            'term': self.term,
            'batch': self.batch,
            'is_active': self.is_active,
            'activated_by': self.activated_by,
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
            'deactivated_at': self.deactivated_at.isoformat() if self.deactivated_at else None
        }

