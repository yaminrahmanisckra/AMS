from datetime import datetime
from extensions import db

class RSession(db.Model):
    __tablename__ = 'result_session'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    term = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(50), nullable=True)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    students = db.relationship('RStudent', backref='session', lazy=True, cascade="all, delete-orphan")
    subjects = db.relationship('RSubject', backref='session', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<RSession {self.name}>'

class RStudent(db.Model):
    __tablename__ = 'result_student'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    year = db.Column(db.String(50), nullable=True)
    discipline = db.Column(db.String(100), nullable=True)
    school = db.Column(db.String(100), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey('result_session.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    marks = db.relationship('RMark', backref='student', lazy=True, cascade="all, delete-orphan")
    registrations = db.relationship('RCourseRegistration', backref='student', lazy=True, cascade="all, delete-orphan")
    
    __table_args__ = (db.UniqueConstraint('student_id', 'session_id', name='_student_session_uc'),)


class RSubject(db.Model):
    __tablename__ = 'result_subject'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    credit = db.Column(db.Float, nullable=False)
    subject_type = db.Column(db.String(20), nullable=False)  # Theory/Dissertation
    dissertation_type = db.Column(db.String(20), nullable=True)  # For dissertation subjects
    has_retake = db.Column(db.Boolean, default=False)
    session_id = db.Column(db.Integer, db.ForeignKey('result_session.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    marks = db.relationship('RMark', backref='subject', lazy=True, cascade="all, delete-orphan")
    registrations = db.relationship('RCourseRegistration', backref='subject', lazy=True, cascade="all, delete-orphan")


class RMark(db.Model):
    __tablename__ = 'result_mark'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('result_student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('result_subject.id'), nullable=False)
    
    # Theory marks
    attendance = db.Column(db.Float, nullable=True)
    continuous_assessment = db.Column(db.Float, nullable=True)
    part_a = db.Column(db.Float, nullable=True)
    part_b = db.Column(db.Float, nullable=True)
    
    # Sessional marks
    sessional_report = db.Column(db.Float, nullable=True)
    sessional_viva = db.Column(db.Float, nullable=True)
    
    # Dissertation marks
    supervisor_assessment = db.Column(db.Float, nullable=True)
    proposal_presentation = db.Column(db.Float, nullable=True)
    project_report = db.Column(db.Float, nullable=True)
    defense = db.Column(db.Float, nullable=True)
    
    total_marks = db.Column(db.Float, nullable=True)
    grade_point = db.Column(db.Float, nullable=True)
    grade_letter = db.Column(db.String(2), nullable=True)
    is_retake = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RCourseRegistration(db.Model):
    __tablename__ = 'result_course_registration'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('result_student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('result_subject.id'), nullable=False)
    is_retake = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint('student_id', 'subject_id', 'is_retake', name='_r_student_subject_retake_uc'),) 