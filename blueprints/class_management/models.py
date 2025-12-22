from datetime import datetime, date
from flask_login import UserMixin
from extensions import db

# Teacher Model
class Teacher(db.Model):
    __tablename__ = 'teacher'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(10), nullable=False, unique=True)
    designation = db.Column(db.String(50), nullable=True)  # Professor, Associate Professor, Assistant Professor, Lecturer
    institute = db.Column(db.String(100), nullable=True, default='Law Discipline, KU')  # Default: Law Discipline, KU
    call_sign = db.Column(db.String(50), nullable=True)  # Call Sign for teacher
    bank_account_no = db.Column(db.String(100), nullable=True)  # Bank Account Number for teacher

    # Define the back-population for the relationship
    class_sessions = db.relationship('Session', back_populates='teacher')
    
    def __repr__(self):
        return f"Teacher('{self.name}', '{self.short_name}')"

# Database Models
class Session(db.Model):
    __tablename__ = 'class_session'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.String(4), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    academic_session = db.Column(db.String(20), nullable=True)
    course_code = db.Column(db.String(20), nullable=True)
    course_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    teacher = db.relationship('Teacher', back_populates='class_sessions')
    students = db.relationship('ClassStudent', backref='session', lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship('ClassAttendance', backref='session', lazy=True, cascade="all, delete-orphan")
    # Note: course_outline relationship is defined in CourseOutline model to avoid circular dependency
    archived = db.Column(db.Boolean, default=False)
    course_type = db.Column(db.String(20), nullable=False, default='theory')
    category = db.Column(db.String(20), nullable=False, default='ug')
    course_scope = db.Column(db.String(10), nullable=False, default='full')  # full | part_a | part_b
    split_group_id = db.Column(db.String(36), nullable=True, index=True)
    # Assessment reveal status (JSON format: {teacher_id: {assessment1: true, assessment2: false, ...}})
    assessment_revealed = db.Column(db.Text, nullable=True)


class ClassSplitInvite(db.Model):
    __tablename__ = 'class_split_invite'
    id = db.Column(db.Integer, primary_key=True)
    split_group_id = db.Column(db.String(36), nullable=False, index=True)
    inviter_session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    inviter_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    invited_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    invited_scope = db.Column(db.String(10), nullable=False)  # part_a | part_b
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | accepted | declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    inviter_session = db.relationship('Session', foreign_keys=[inviter_session_id])
    inviter_teacher = db.relationship('Teacher', foreign_keys=[inviter_teacher_id], backref=db.backref('sent_split_invites', lazy='dynamic'))
    invited_teacher = db.relationship('Teacher', foreign_keys=[invited_teacher_id], backref=db.backref('received_split_invites', lazy='dynamic'))

class ClassStudent(db.Model):
    __tablename__ = 'class_student'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    
    # Assessment fields
    assessment1 = db.Column(db.Float, nullable=True)
    assessment2 = db.Column(db.Float, nullable=True)
    assessment3 = db.Column(db.Float, nullable=True)
    assessment4 = db.Column(db.Float, nullable=True)
    assessment_total = db.Column(db.Float, nullable=True)
    assessment_avg = db.Column(db.Float, nullable=True)
    assessment_total_40 = db.Column(db.Float, nullable=True)
    sessional_report = db.Column(db.Float, nullable=True)
    sessional_viva = db.Column(db.Float, nullable=True)
    
    # Absent status for assessments (JSON: {"assessment1": true, "assessment2": false, "sessional_report": true, "sessional_viva": false})
    assessment_absent = db.Column(db.Text, nullable=True)
    
    # Relationships
    attendances = db.relationship('ClassAttendance', backref='student', lazy=True, cascade="all, delete-orphan")

class ClassAttendance(db.Model):
    __tablename__ = 'class_attendance'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    is_present = db.Column(db.Boolean, default=False)
    student_id = db.Column(db.Integer, db.ForeignKey('class_student.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False) 

class CourseReview(db.Model):
    __tablename__ = 'course_review'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Evaluation invitation for external/internal teacher to assess a course session
class EvaluationInvite(db.Model):
    __tablename__ = 'evaluation_invite'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    inviter_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    evaluator_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    status = db.Column(db.String(20), default='invited')  # invited | submitted | reviewed | cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Submission of classroom observation report by invited teacher
class EvaluationSubmission(db.Model):
    __tablename__ = 'evaluation_submission'
    id = db.Column(db.Integer, primary_key=True)
    invite_id = db.Column(db.Integer, db.ForeignKey('evaluation_invite.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    evaluator_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    general_info = db.Column(db.Text, nullable=True)  # JSON string
    scores = db.Column(db.Text, nullable=True)       # JSON string
    comments_observer = db.Column(db.Text, nullable=True)
    comments_presenter = db.Column(db.Text, nullable=True)
    total_score = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ExamPaperEvaluation(db.Model):
    __tablename__ = 'exam_paper_evaluation'
    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(150), nullable=False)
    course_code = db.Column(db.String(50), nullable=False)
    academic_session = db.Column(db.String(50), nullable=True)
    batch = db.Column(db.String(20), nullable=True)
    discipline = db.Column(db.String(100), nullable=True)
    school = db.Column(db.String(100), nullable=True)
    year = db.Column(db.String(10), nullable=True)
    term = db.Column(db.String(10), nullable=True)
    section = db.Column(db.String(50), nullable=True)
    program_level = db.Column(db.String(20), nullable=False)  # ug / pg
    archived = db.Column(db.Boolean, default=False)
    marks_data = db.Column(db.Text, nullable=True)
    submitted_to_committee = db.Column(db.Boolean, nullable=False, default=False)
    submitted_at = db.Column(db.DateTime, nullable=True)
    owner_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    assigned_scrutinizer_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_teacher = db.relationship('Teacher', foreign_keys=[owner_teacher_id], backref=db.backref('owned_exam_entries', lazy='dynamic'))
    assigned_scrutinizer = db.relationship('Teacher', foreign_keys=[assigned_scrutinizer_id], backref=db.backref('assigned_scrutinizer_entries', lazy='dynamic'))


class ExamScrutinizerInvite(db.Model):
    __tablename__ = 'exam_scrutinizer_invite'
    id = db.Column(db.Integer, primary_key=True)
    exam_entry_id = db.Column(db.Integer, db.ForeignKey('exam_paper_evaluation.id'), nullable=False)
    inviter_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    scrutinizer_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='invited')  # invited | accepted | declined | cancelled
    remarks = db.Column(db.Text, nullable=True)
    is_complete = db.Column(db.Boolean, default=False, nullable=False)  # Complete/Incomplete status
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    exam_entry = db.relationship('ExamPaperEvaluation', backref=db.backref('scrutinizer_invites', lazy='dynamic'))
    inviter = db.relationship('Teacher', foreign_keys=[inviter_teacher_id], backref=db.backref('sent_exam_scrutinizer_invites', lazy='dynamic'))
    scrutinizer = db.relationship('Teacher', foreign_keys=[scrutinizer_teacher_id], backref=db.backref('received_exam_scrutinizer_invites', lazy='dynamic'))


class StudentFeedbackLink(db.Model):
    __tablename__ = 'student_feedback_link'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    access_code = db.Column(db.String(32), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    allow_multiple = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session = db.relationship('Session', backref=db.backref('student_feedback_links', lazy='dynamic', cascade='all, delete-orphan'))


class StudentFeedbackResponse(db.Model):
    __tablename__ = 'student_feedback_response'
    id = db.Column(db.Integer, primary_key=True)
    feedback_link_id = db.Column(db.Integer, db.ForeignKey('student_feedback_link.id'), nullable=False)
    payload = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    feedback_link = db.relationship('StudentFeedbackLink', backref=db.backref('responses', lazy='dynamic', cascade='all, delete-orphan'))


class CourseOutline(db.Model):
    __tablename__ = 'course_outline'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    
    # Part A: Introduction
    course_objectives = db.Column(db.Text, nullable=True)  # JSON array of objectives
    course_summary = db.Column(db.Text, nullable=True)
    prerequisites = db.Column(db.String(200), nullable=True)
    contact_hours = db.Column(db.String(50), nullable=True)
    cie_marks = db.Column(db.String(50), nullable=True)  # Continuous Internal Evaluation
    smee_marks = db.Column(db.String(50), nullable=True)  # Semester Mid/End Examination
    
    # Lesson Plan / Weekly Schedule (JSON array)
    lesson_plan = db.Column(db.Text, nullable=True)  # JSON: [{week, date, topic, outcome, activities, teaching_assessment, clo_alignment}]
    
    # Part B: Course Content (if needed)
    course_content_summary = db.Column(db.Text, nullable=True)  # JSON: {section_a: [...], section_b: [...]}
    clo_plo_mapping = db.Column(db.Text, nullable=True)  # JSON: [{clo, plos, mapping_matrix}]
    
    # Part C: Assessment and Evaluation
    assessment_strategy = db.Column(db.Text, nullable=True)  # JSON: {theory_marks: {...}, attendance_marks: {...}, ca_details: {...}}
    assessment_techniques = db.Column(db.Text, nullable=True)  # JSON: [{strategy, clo_marks, total_marks}]
    rubrics = db.Column(db.Text, nullable=True)  # JSON: [{type, criteria, levels}]
    grading_policy = db.Column(db.Text, nullable=True)  # JSON: [{marks_range, grade}]
    evaluation_policy = db.Column(db.Text, nullable=True)  # JSON: {grading_system, make_up_procedures}
    cie_breakdown = db.Column(db.Text, nullable=True)  # JSON: {blooms_category: {test: X, group_debate: Y}}
    smee_breakdown = db.Column(db.Text, nullable=True)  # JSON: {blooms_category: {test_marks: X}}
    
    # Part D: Learning Resources
    textbooks = db.Column(db.Text, nullable=True)  # JSON array
    reference_books = db.Column(db.Text, nullable=True)  # JSON array
    other_resources = db.Column(db.Text, nullable=True)  # JSON array
    course_file_components = db.Column(db.Text, nullable=True)  # JSON array: list of course file components
    
    # Other sections
    make_up_procedures = db.Column(db.Text, nullable=True)
    other_issues = db.Column(db.Text, nullable=True)  # JSON: {class_discussion, expectations, communication, academic_honesty}
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Use passive relationships to prevent SQLAlchemy from trying to update foreign keys
    # passive_updates=True: SQLAlchemy will NOT update foreign keys when parent changes
    # This is critical for delete operations - SQLAlchemy won't try to set session_id to NULL
    session = db.relationship('Session', 
                              backref=db.backref('course_outline', 
                                                uselist=False, 
                                                passive_deletes=True, 
                                                passive_updates=True,
                                                cascade='none'),  # Explicitly disable cascade
                              passive_updates=True)
    teacher = db.relationship('Teacher', backref=db.backref('course_outlines', lazy='dynamic'))
