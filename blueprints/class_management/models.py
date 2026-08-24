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
