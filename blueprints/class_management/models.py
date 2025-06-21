from datetime import datetime, date
from flask_login import UserMixin
from extensions import db

# Teacher Model
class Teacher(db.Model):
    __tablename__ = 'teacher'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(10), nullable=False, unique=True)
    
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
    course_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    teacher = db.relationship('Teacher', back_populates='class_sessions')
    students = db.relationship('ClassStudent', backref='session', lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship('ClassAttendance', backref='session', lazy=True, cascade="all, delete-orphan")
    archived = db.Column(db.Boolean, default=False)
    course_type = db.Column(db.String(20), nullable=False, default='theory')
    category = db.Column(db.String(20), nullable=False, default='ug')

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