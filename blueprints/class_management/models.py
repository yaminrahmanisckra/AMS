from datetime import datetime, date
from flask_login import UserMixin
from extensions import db
import json

# Teacher Model
class Teacher(db.Model):
    __tablename__ = 'teacher'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    short_name = db.Column(db.String(10), nullable=False, unique=True)
    designation = db.Column(db.String(50), nullable=True)  # Professor, Associate Professor, Assistant Professor, Lecturer
    institute = db.Column(db.String(100), nullable=True)  # Set from current_tenant().institute_label on insert
    call_sign = db.Column(db.String(50), nullable=True)  # Call Sign for teacher
    bank_account_no = db.Column(db.String(100), nullable=True)  # Bank Account Number for teacher
    tin_number = db.Column(db.String(50), nullable=True)  # TIN number for teacher
    is_external = db.Column(db.Boolean, default=False, nullable=False)  # True = External Teacher (other department)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)

    operational_window = db.relationship(
        'OperationalWindow',
        backref=db.backref('teachers', lazy='dynamic'),
    )

    # Define the back-population for the relationship
    class_sessions = db.relationship('Session', back_populates='teacher')
    
    def __repr__(self):
        return f"Teacher('{self.name}', '{self.short_name}')"


class TeacherFeedbackVisibility(db.Model):
    """Per-teacher switch for seeing who submitted student feedback. Default off."""
    __tablename__ = 'teacher_feedback_visibility'

    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), primary_key=True)
    show_respondents = db.Column(db.Boolean, nullable=False, default=False, server_default='0')

    teacher = db.relationship('Teacher', backref=db.backref('feedback_visibility', uselist=False))

# Database Models
class Session(db.Model):
    __tablename__ = 'class_session'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.String(4), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    academic_session = db.Column(db.String(20), nullable=True)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    course_code = db.Column(db.String(20), nullable=True)
    course_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    teacher = db.relationship('Teacher', back_populates='class_sessions')
    students = db.relationship('ClassStudent', backref='session', lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship('ClassAttendance', backref='session', lazy=True, cascade="all, delete-orphan")
    # Note: course_outline relationship is defined in CourseOutline model to avoid circular dependency
    archived = db.Column(db.Boolean, default=False)
    is_external_course = db.Column(db.Boolean, default=False, nullable=False)
    external_assessment_mode = db.Column(db.String(20), nullable=False, default='best_three')
    # When True, assessment totals are shown/exported as whole numbers (half-up).
    round_assessment_total = db.Column(db.Boolean, nullable=False, default=False)
    course_type = db.Column(db.String(20), nullable=False, default='theory')
    category = db.Column(db.String(20), nullable=False, default='ug')
    course_scope = db.Column(db.String(10), nullable=False, default='full')  # full | part_a | part_b
    split_group_id = db.Column(db.String(36), nullable=True, index=True)
    # Assessment reveal status (JSON format: {teacher_id: {assessment1: true, assessment2: false, ...}})
    assessment_revealed = db.Column(db.Text, nullable=True)
    qa_ai_auto_reply = db.Column(db.Boolean, default=False, nullable=False)


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
    
    # Manual attendance marks override (if set, takes precedence over calculated marks)
    attendance_marks_manual = db.Column(db.Float, nullable=True)
    
    # Absent status for assessments (JSON: {"assessment1": true, "assessment2": false, "sessional_report": true, "sessional_viva": false})
    assessment_absent = db.Column(db.Text, nullable=True)
    
    # Relationships
    attendances = db.relationship('ClassAttendance', backref='student', lazy=True, cascade="all, delete-orphan")

class ClassAttendance(db.Model):
    __tablename__ = 'class_attendance'
    STATUS_PRESENT = 'present'
    STATUS_ABSENT = 'absent'
    STATUS_SKIP = 'skip'
    STATUS_NONE = 'none'
    VALID_STATUSES = {STATUS_PRESENT, STATUS_ABSENT, STATUS_SKIP, STATUS_NONE}

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    is_present = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_ABSENT, server_default=STATUS_ABSENT)
    slot_number = db.Column(db.Integer, nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('class_student.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)

    def normalized_status(self):
        """Return normalized tri-state attendance status."""
        if self.status in self.VALID_STATUSES:
            return self.status
        return self.STATUS_PRESENT if self.is_present else self.STATUS_ABSENT

    def set_status(self, status_value):
        """Set tri-state status while keeping legacy is_present in sync."""
        normalized = (status_value or self.STATUS_ABSENT).strip().lower()
        if normalized not in self.VALID_STATUSES:
            normalized = self.STATUS_ABSENT
        self.status = normalized
        self.is_present = normalized == self.STATUS_PRESENT

class CourseReview(db.Model):
    __tablename__ = 'course_review'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CourseFileUpload(db.Model):
    """Model for teacher-uploaded files that students can download"""
    __tablename__ = 'course_file_upload'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)  # Path to uploaded file
    file_size = db.Column(db.Integer, nullable=True)  # File size in bytes
    file_type = db.Column(db.String(50), nullable=True)  # MIME type or extension
    file_category = db.Column(db.String(50), nullable=True)  # syllabus, reading, slides, other
    description = db.Column(db.Text, nullable=True)  # Optional description
    extracted_text = db.Column(db.Text, nullable=True)  # Cached text for AI RAG
    student_access_enabled = db.Column(db.Boolean, default=True, nullable=False)  # Allow students to download
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    session = db.relationship('Session', backref=db.backref('uploaded_files', lazy='dynamic'))
    teacher = db.relationship('Teacher', backref=db.backref('uploaded_files', lazy='dynamic'))


class AnswerGuideline(db.Model):
    """Global answer-writing guideline uploaded from Admin Dashboard."""
    __tablename__ = 'answer_guideline'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    extracted_text = db.Column(db.Text, nullable=True)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class QuestionBankFile(db.Model):
    """Past-question PDF files shared for all students/teachers."""
    __tablename__ = 'question_bank_file'
    id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(200), nullable=False)
    course_code = db.Column(db.String(50), nullable=True)
    question_year = db.Column(db.String(20), nullable=False)  # e.g. 2023
    title = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_kind = db.Column(db.String(30), nullable=False, default='question')  # question | answer_guideline
    extracted_text = db.Column(db.Text, nullable=True)
    analysis_json = db.Column(db.Text, nullable=True)
    model_answers_json = db.Column(db.Text, nullable=True)


class QuestionBankFolder(db.Model):
    """Folder for organizing question bank files."""
    __tablename__ = 'question_bank_folder'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CourseQuestionThread(db.Model):
    """Student -> Teacher Q&A threads per course session."""
    __tablename__ = 'course_question_thread'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False, index=True)
    student_id = db.Column(db.String(50), nullable=False, index=True)
    student_name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    teacher_read_at = db.Column(db.DateTime, nullable=True)  # when teacher saw this thread (for notifications)

    session = db.relationship('Session', backref=db.backref('question_threads', lazy='dynamic'))
    teacher = db.relationship('Teacher', backref=db.backref('question_threads', lazy='dynamic'))
    messages = db.relationship(
        'CourseQuestionMessage',
        backref='thread',
        lazy='selectin',
        cascade="all, delete-orphan"
    )


class CourseQuestionMessage(db.Model):
    """Messages inside a Q&A thread."""
    __tablename__ = 'course_question_message'
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('course_question_thread.id'), nullable=False, index=True)
    sender_role = db.Column(db.String(20), nullable=False)  # student | teacher
    sender_user_id = db.Column(db.Integer, nullable=True)   # teacher.id or student.id (optional)
    body = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    seen_by_teacher_at = db.Column(db.DateTime, nullable=True)  # when teacher viewed a student message
    seen_by_student_at = db.Column(db.DateTime, nullable=True)  # when student viewed a teacher message
    is_ai_generated = db.Column(db.Boolean, default=False, nullable=False)

    attachments = db.relationship(
        'CourseQuestionAttachment',
        backref='message',
        lazy='selectin',
        cascade="all, delete-orphan"
    )


class CourseQuestionAttachment(db.Model):
    """Attachment for a Q&A message."""
    __tablename__ = 'course_question_attachment'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('course_question_message.id'), nullable=False, index=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    file_type = db.Column(db.String(100), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudentNotification(db.Model):
    """Notifications for students: question reply, marks revealed, file shared."""
    __tablename__ = 'student_notification'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False)  # 'question_reply' | 'marks_revealed' | 'file_shared' | 'notice'
    title = db.Column(db.String(300), nullable=False)
    link_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)

    operational_window = db.relationship(
        'OperationalWindow',
        backref=db.backref('student_notifications', lazy='dynamic'),
    )


# Evaluation invitation for external/internal teacher to assess a course session
class EvaluationInvite(db.Model):
    __tablename__ = 'evaluation_invite'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    inviter_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    evaluator_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    status = db.Column(db.String(20), default='invited')  # invited | submitted | reviewed | cancelled
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    operational_window = db.relationship(
        'OperationalWindow',
        backref=db.backref('evaluation_invites', lazy='dynamic'),
    )

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
    is_external_subject = db.Column(db.Boolean, default=False, nullable=False)
    owner_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    assigned_scrutinizer_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_teacher = db.relationship('Teacher', foreign_keys=[owner_teacher_id], backref=db.backref('owned_exam_entries', lazy='dynamic'))
    operational_window = db.relationship('OperationalWindow', backref=db.backref('exam_paper_evaluations', lazy='dynamic'))
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
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    exam_entry = db.relationship('ExamPaperEvaluation', backref=db.backref('scrutinizer_invites', lazy='dynamic'))
    operational_window = db.relationship('OperationalWindow', backref=db.backref('exam_scrutinizer_invites', lazy='dynamic'))
    inviter = db.relationship('Teacher', foreign_keys=[inviter_teacher_id], backref=db.backref('sent_exam_scrutinizer_invites', lazy='dynamic'))
    scrutinizer = db.relationship('Teacher', foreign_keys=[scrutinizer_teacher_id], backref=db.backref('received_exam_scrutinizer_invites', lazy='dynamic'))


class ExamPaperEvaluatorAssignment(db.Model):
    """Model to track Exam Paper Evaluator assignments by Exam Committee Chief"""
    __tablename__ = 'exam_paper_evaluator_assignment'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    part = db.Column(db.String(10), nullable=False)  # 'A' or 'B'
    assigned_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)  # Evaluator
    question_setter_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)  # Question Setter
    is_same_person = db.Column(db.Boolean, default=False)  # True if question setter and evaluator are same
    academic_session = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(20), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    exam_paper_evaluation_id = db.Column(db.Integer, db.ForeignKey('exam_paper_evaluation.id'), nullable=True)  # Created ExamPaperEvaluation entry
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Exam Committee Chief who assigned
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - Course model is in blueprints.course_management.models, use string reference
    operational_window = db.relationship('OperationalWindow', backref=db.backref('evaluator_assignments', lazy='dynamic'))
    assigned_teacher = db.relationship('Teacher', foreign_keys=[assigned_teacher_id], backref=db.backref('evaluator_assignments', lazy='dynamic'))
    question_setter = db.relationship('Teacher', foreign_keys=[question_setter_id], backref=db.backref('question_setter_assignments', lazy='dynamic'))
    exam_paper_evaluation = db.relationship('ExamPaperEvaluation', foreign_keys=[exam_paper_evaluation_id], backref=db.backref('evaluator_assignment', uselist=False))
    
    __table_args__ = (
        db.UniqueConstraint(
            'window_id', 'course_id', 'part', 'academic_session', 'year', 'term',
            name='uq_evaluator_assignment_window',
        ),
    )
    
    def __repr__(self):
        return f'<ExamPaperEvaluatorAssignment {self.course_id} Part {self.part} -> Teacher {self.assigned_teacher_id}>'


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
    ai_report_json = db.Column(db.Text, nullable=True)
    ai_report_generated_at = db.Column(db.DateTime, nullable=True)
    session = db.relationship('Session', backref=db.backref('student_feedback_links', lazy='dynamic', cascade='all, delete-orphan'))


class StudentFeedbackResponse(db.Model):
    __tablename__ = 'student_feedback_response'
    id = db.Column(db.Integer, primary_key=True)
    feedback_link_id = db.Column(db.Integer, db.ForeignKey('student_feedback_link.id'), nullable=False)
    payload = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text('0'))
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
    credit_value = db.Column(db.String(20), nullable=True)  # Credit value (e.g., 4.0)
    course_type = db.Column(db.String(50), nullable=True)  # Core Course / Elective Course
    level_term_section = db.Column(db.String(100), nullable=True)  # Level/Term and Section
    clo_data = db.Column(db.Text, nullable=True)  # JSON array: [{number, description, plos}]
    plo_mapping = db.Column(db.Text, nullable=True)  # JSON: {CLO 1: {PLO 1: 3, PLO 2: 2}, ...}
    
    # Lesson Plan / Weekly Schedule (JSON array)
    lesson_plan = db.Column(db.Text, nullable=True)  # JSON: [{week, date, topic, outcome, activities, teaching_assessment, clo_alignment}]
    
    # Part B: Course Content (if needed)
    course_content_summary = db.Column(db.Text, nullable=True)  # JSON: {section_a: [...], section_b: [...]}
    course_content_classes = db.Column(db.Text, nullable=True)  # JSON: {section_a: [1,2,1,...], section_b: [1,1,3,...]}
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
    
    # Student access control
    student_access_enabled = db.Column(db.Boolean, default=False, nullable=False)  # Allow students to download course outline PDF
    
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


# --- Socrates AI Debate Companion ---

class SocratesAssignment(db.Model):
    """Teacher-set debate topic students argue with the AI companion (Socrates)."""
    __tablename__ = 'socrates_assignment'
    MODE_INDIVIDUAL = 'individual'
    MODE_GROUP = 'group'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False, index=True)
    topic = db.Column(db.String(300), nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    mode = db.Column(db.String(20), nullable=False, default=MODE_INDIVIDUAL)  # individual | group
    prompt_limit = db.Column(db.Integer, nullable=False, default=15)
    prompt_seconds = db.Column(db.Integer, nullable=True)  # per-prompt time limit; null = none
    prompt_timer_include_first = db.Column(db.Boolean, nullable=False, default=True)
    paste_disabled = db.Column(db.Boolean, nullable=False, default=True)
    paste_max_words = db.Column(db.Integer, nullable=True)  # per paste event
    paste_max_events = db.Column(db.Integer, nullable=True)  # total pastes per conversation
    deadline = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('Session', backref=db.backref('socrates_assignments', lazy='dynamic', cascade='all, delete-orphan'))
    teacher = db.relationship('Teacher', backref=db.backref('socrates_assignments', lazy='dynamic'))
    groups = db.relationship('SocratesGroup', backref='assignment', lazy='selectin', cascade='all, delete-orphan')
    conversations = db.relationship('SocratesConversation', backref='assignment', lazy='selectin', cascade='all, delete-orphan')

    def is_open(self):
        if not self.is_active:
            return False
        if self.deadline and datetime.utcnow().date() > self.deadline.date():
            return False
        return True

    def effective_deadline(self, conversation=None):
        """Inclusive calendar-day deadline; conversation override wins when set."""
        if conversation is not None and getattr(conversation, 'deadline_override', None):
            return conversation.deadline_override
        return self.deadline

    def conversation_is_open(self, conversation=None):
        if not self.is_active:
            return False
        deadline = self.effective_deadline(conversation)
        if deadline and datetime.utcnow().date() > deadline.date():
            return False
        return True

    def has_prompt_timer(self):
        return bool(self.prompt_seconds and int(self.prompt_seconds) > 0)

    def paste_mode(self):
        """disabled | limited | unlimited"""
        if self.paste_disabled:
            return 'disabled'
        if self.paste_max_words or self.paste_max_events:
            return 'limited'
        return 'unlimited'


class SocratesGroup(db.Model):
    """Teacher-assigned student group for a group-mode Socrates assignment."""
    __tablename__ = 'socrates_group'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('socrates_assignment.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('SocratesGroupMember', backref='group', lazy='selectin', cascade='all, delete-orphan')


class SocratesGroupMember(db.Model):
    __tablename__ = 'socrates_group_member'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('socrates_group.id'), nullable=False, index=True)
    student_id = db.Column(db.String(50), nullable=False, index=True)
    student_name = db.Column(db.String(100), nullable=True)


class SocratesConversation(db.Model):
    """One debate per student (individual) or per group (group mode)."""
    __tablename__ = 'socrates_conversation'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_SUBMITTED = 'submitted'
    STATUS_EVALUATED = 'evaluated'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('socrates_assignment.id'), nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('socrates_group.id'), nullable=True, index=True)
    student_id = db.Column(db.String(50), nullable=True, index=True)  # individual mode
    student_name = db.Column(db.String(100), nullable=True)
    prompts_used = db.Column(db.Integer, nullable=False, default=0)
    extra_prompts = db.Column(db.Integer, nullable=False, default=0)
    focus_loss_count = db.Column(db.Integer, nullable=False, default=0)
    screenshot_hint_count = db.Column(db.Integer, nullable=False, default=0)
    paste_events_used = db.Column(db.Integer, nullable=False, default=0)
    debate_started_at = db.Column(db.DateTime, nullable=True)
    prompt_deadline_at = db.Column(db.DateTime, nullable=True)
    deadline_override = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_IN_PROGRESS)
    ai_evaluation_json = db.Column(db.Text, nullable=True)
    teacher_mark = db.Column(db.Float, nullable=True)
    teacher_comment = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = db.relationship('SocratesGroup', backref=db.backref('conversations', lazy='selectin'))
    messages = db.relationship(
        'SocratesMessage',
        backref='conversation',
        lazy='selectin',
        cascade='all, delete-orphan',
        order_by='SocratesMessage.created_at',
    )

    def participant_label(self):
        if self.group_id and self.group:
            return self.group.name
        return f"{self.student_name or ''} ({self.student_id})".strip()

    def prompt_cap(self):
        base = int(self.assignment.prompt_limit or 0) if self.assignment else 0
        return base + int(self.extra_prompts or 0)

    def remaining_prompts(self):
        return max(0, self.prompt_cap() - int(self.prompts_used or 0))


class SocratesMessage(db.Model):
    __tablename__ = 'socrates_message'
    SENDER_STUDENT = 'student'
    SENDER_SOCRATES = 'socrates'
    SENDER_SYSTEM = 'system'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('socrates_conversation.id'), nullable=False, index=True)
    sender = db.Column(db.String(20), nullable=False)  # student | socrates
    sender_student_id = db.Column(db.String(50), nullable=True)  # who in the group wrote it
    sender_student_name = db.Column(db.String(100), nullable=True)
    body = db.Column(db.Text, nullable=False)
    input_meta = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def input_signal(self):
        """Paste/type/style signal for teacher review. None for Socrates replies or old rows."""
        if self.sender != self.SENDER_STUDENT or not self.input_meta:
            return None
        try:
            data = json.loads(self.input_meta)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        source = data.get('source') or 'unknown'
        labels = {
            'typed': 'টাইপ করা',
            'pasted': 'পেস্ট করা',
            'mixed': 'পেস্ট + টাইপ',
            'burst': 'খুব দ্রুত ঢোকানো',
        }
        label = labels.get(source)
        style = data.get('style') if isinstance(data.get('style'), dict) else {}
        style_flag = bool(style.get('flag'))
        style_label = style.get('label') if style_flag else None
        if not label and not style_flag:
            return None
        data = dict(data)
        data['source'] = source
        data['label'] = label
        data['flag'] = source in ('pasted', 'mixed', 'burst')
        data['style_flag'] = style_flag
        data['style_label'] = style_label
        data['style_label_en'] = 'AI-style' if style_flag else None
        data['style_score'] = style.get('score')
        data['label_en'] = {
            'typed': 'Typed',
            'pasted': 'Pasted',
            'mixed': 'Pasted + typed',
            'burst': 'Entered very fast',
        }.get(source)
        data['paste_snippets'] = data.get('paste_snippets') if isinstance(data.get('paste_snippets'), list) else []
        data['ai_snippets'] = data.get('ai_snippets') if isinstance(data.get('ai_snippets'), list) else []
        return data

    def teacher_body_html(self):
        """Escaped student text with paste/AI spans marked for teacher review."""
        from utils.integrity_highlight import (
            collect_ai_snippets,
            highlight_integrity_plain,
            parse_snippet_list,
        )

        signal = self.input_signal() or {}
        paste = parse_snippet_list(signal.get('paste_snippets'))
        ai = parse_snippet_list(signal.get('ai_snippets'))
        if not ai and signal.get('style_flag'):
            ai = collect_ai_snippets(self.body or '')
        pasted = bool(signal.get('flag'))
        return highlight_integrity_plain(
            self.body or '',
            paste_snippets=paste,
            ai_snippets=ai,
            whole_paste=pasted and not paste,
            whole_ai=bool(signal.get('style_flag')) and not ai and not paste,
        )

    def teacher_body_classes(self):
        from utils.integrity_highlight import block_classes

        signal = self.input_signal() or {}
        return block_classes(
            pasted=bool(signal.get('flag')),
            ai=bool(signal.get('style_flag')),
        )


def classify_socrates_input(body, raw=None):
    """Classify a student message as typed, pasted, mixed, or too-fast burst.

    This cannot prove another AI wrote the text. It only records how the text
    entered the box (paste vs typing, plus a speed check).
    """
    length = len(body or '')
    raw = raw if isinstance(raw, dict) else {}

    def _int(key, cap):
        try:
            return max(0, min(int(cap), int(raw.get(key) or 0)))
        except (TypeError, ValueError):
            return 0

    pasted = min(length, _int('pasted_chars', 20000))
    typed = min(length, _int('typed_chars', 20000))
    paste_events = _int('paste_events', 100)
    compose_ms = _int('compose_ms', 86400000)
    burst = bool(length >= 80 and compose_ms > 0 and compose_ms < max(2500, length * 40))
    if paste_events or pasted >= 24:
        source = 'mixed' if typed >= 24 and pasted >= 24 else 'pasted'
    elif burst:
        source = 'burst'
    elif length:
        source = 'typed'
    else:
        source = 'unknown'
    result = {
        'source': source,
        'pasted_chars': pasted,
        'typed_chars': typed,
        'paste_events': paste_events,
        'compose_ms': compose_ms,
        'length': length,
    }
    result['style'] = estimate_socrates_ai_style(body)
    return result


def estimate_socrates_ai_style(body):
    """Heuristic guess that text looks like generic AI prose. Not proof.

    Returns score 0–100 and flag when score is high enough for teacher review.
    """
    import re

    text = (body or '').strip()
    if len(text) < 90:
        return {'score': 0, 'flag': False, 'label': None, 'reasons': []}

    lower = text.lower()
    score = 0
    reasons = []

    stock_phrases = (
        'furthermore', 'moreover', 'in conclusion', 'it is important to note',
        'it is worth noting', "in today's world", 'plays a crucial role',
        'multifaceted', 'delve into', 'landscape of', 'aforementioned',
        'it can be argued that', 'from a broader perspective', 'underscores the',
        'pivotal role', 'comprehensive understanding', 'intricate',
        'in this regard', 'to summarize', 'as previously mentioned',
        'a double-edged sword', 'at the end of the day',
        'এছাড়াও উল্লেখযোগ্য', 'উপসংহারে বলা যায়', 'এটি অত্যন্ত গুরুত্বপূর্ণ',
    )
    hits = [p for p in stock_phrases if p in lower]
    if hits:
        score += min(42, 14 * len(hits))
        reasons.append(f'stock:{len(hits)}')

    sentences = [s.strip() for s in re.split(r'[.!?।]+', text) if len(s.strip()) > 8]
    if len(sentences) >= 3:
        lengths = [len(re.findall(r'\S+', s)) for s in sentences]
        avg = sum(lengths) / len(lengths)
        if avg >= 22:
            score += 16
            reasons.append('long_sentences')
        if len(lengths) >= 4:
            var = sum((x - avg) ** 2 for x in lengths) / len(lengths)
            if var < 28 and avg >= 14:
                score += 14
                reasons.append('uniform_rhythm')

    formal_marks = text.count('—') + text.count('–') + text.count(';')
    if formal_marks >= 2:
        score += 10
        reasons.append('formal_punctuation')

    words = re.findall(r"[A-Za-z']+", text)
    if len(words) >= 55:
        contractions = {
            "don't", "can't", "won't", "isn't", "aren't", "it's", "i'm", "we're",
            "they're", "that's", "there's", "wouldn't", "couldn't", "shouldn't",
            "doesn't", "didn't", "haven't", "hasn't",
        }
        has_contraction = any(w.lower() in contractions for w in words)
        if not has_contraction:
            score += 10
            reasons.append('no_contractions')

    # Very tidy paragraphs with little informal voice
    if len(text) >= 280 and text.count('\n\n') >= 1 and 'i think' not in lower and 'i feel' not in lower:
        if lower.count(' however ') + lower.count(' therefore ') >= 2:
            score += 8
            reasons.append('essay_connectives')

    score = max(0, min(100, int(score)))
    flag = score >= 36
    return {
        'score': score,
        'flag': flag,
        'label': 'এআই-স্টাইল সন্দেহ' if flag else None,
        'reasons': reasons[:5],
    }


SOCRATES_AI_USE_WARNING = 'আপনি এআই ব্যবহার করছেন, ফলে কাঙ্ক্ষিত নম্বর নাও পেতে পারেন।'
SOCRATES_NO_PASTE_MESSAGE = 'কপি-পেস্ট নিষিদ্ধ। নিজের ভাষায় টাইপ করুন।'


def socrates_ai_use_warning(conversation):
    """Student-facing warning text if any message looks pasted/burst/AI-styled."""
    for msg in (conversation.messages or []):
        signal = msg.input_signal()
        if not signal:
            continue
        if signal.get('flag') or signal.get('style_flag'):
            return SOCRATES_AI_USE_WARNING
    return None


def socrates_integrity_summary(conversation):
    """Teacher-facing integrity counts for one conversation."""
    style_flags = 0
    paste_flags = 0
    for msg in (conversation.messages or []):
        signal = msg.input_signal() or {}
        if signal.get('flag'):
            paste_flags += 1
        if signal.get('style_flag'):
            style_flags += 1
    return {
        'focus_loss_count': int(conversation.focus_loss_count or 0),
        'screenshot_hint_count': int(conversation.screenshot_hint_count or 0),
        'paste_flag_count': paste_flags,
        'style_flag_count': style_flags,
    }


def socrates_word_count(text):
    """Count whitespace-separated tokens (Bangla/English friendly enough for paste quotas)."""
    import re
    return len(re.findall(r'\S+', text or ''))


def build_socrates_auto_instructions(assignment):
    """HTML bullets describing live timer/paste rules (not stored in TinyMCE)."""
    from markupsafe import escape
    items = []
    seconds = int(assignment.prompt_seconds or 0)
    if seconds > 0:
        minutes = seconds // 60
        rem = seconds % 60
        if minutes and rem:
            dur = f'{minutes} মিনিট {rem} সেকেন্ড'
        elif minutes:
            dur = f'{minutes} মিনিট'
        else:
            dur = f'{seconds} সেকেন্ড'
        if assignment.prompt_timer_include_first:
            items.append(
                f'প্রতিটি প্রম্পট (প্রথমটিসহ) {escape(dur)}-এর মধ্যে দিতে হবে। '
                f'সময় শেষ হলে লেখা থাকলে সেটাই পাঠানো হবে; কিছু না লিখলে প্রম্পট বাতিল হবে। '
                f'সব প্রম্পট শেষ হলে ডিবেট অটো-জমা হবে।'
            )
        else:
            items.append(
                f'প্রথম প্রম্পটের পর প্রতিটি প্রম্পট {escape(dur)}-এর মধ্যে দিতে হবে। '
                f'সময় শেষ হলে লেখা থাকলে সেটাই পাঠানো হবে; কিছু না লিখলে প্রম্পট বাতিল হবে। '
                f'সব প্রম্পট শেষ হলে ডিবেট অটো-জমা হবে।'
            )
        items.append('নির্দেশনা একসেপ্ট করার আগে টাইমার চালু হবে না।')

    mode = assignment.paste_mode()
    if mode == 'disabled':
        items.append('কপি-পেস্ট সম্পূর্ণ নিষিদ্ধ। নিজের ভাষায় টাইপ করুন।')
    elif mode == 'limited':
        bits = []
        if assignment.paste_max_words:
            bits.append(f'প্রতি পেস্টে সর্বোচ্চ {int(assignment.paste_max_words)} শব্দ')
        if assignment.paste_max_events:
            bits.append(f'মোট সর্বোচ্চ {int(assignment.paste_max_events)} বার পেস্ট')
        if bits:
            items.append('পেস্ট সীমা: ' + ' · '.join(bits) + '।')
    else:
        items.append('এই অ্যাসাইনমেন্টে পেস্ট অনুমোদিত (সীমা নেই)।')

    if not items:
        return ''
    lis = ''.join(f'<li>{item}</li>' for item in items)
    return (
        '<div class="soc-auto-rules">'
        '<p><strong>অটো নিয়ম (শিক্ষক সেটিংস)</strong></p>'
        f'<ul>{lis}</ul>'
        '</div>'
    )


def socrates_requires_start(assignment):
    """Student must Accept instructions once before chatting (arms timer when configured)."""
    return bool(assignment)

