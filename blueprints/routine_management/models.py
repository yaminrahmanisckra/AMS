from extensions import db
from blueprints.class_management.models import Teacher

class Course(db.Model):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), nullable=False, unique=True)
    course_name = db.Column(db.String(100), nullable=False)
    credit = db.Column(db.Float, nullable=False)
    course_type = db.Column(db.String(20), nullable=False)  # Theory/Sessional
    category = db.Column(db.String(20), nullable=False, default='ug') # UG/PG

    assigned_teachers = db.relationship('AssignedCourse', back_populates='course', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Course {self.course_code}>'

class Room(db.Model):
    __tablename__ = 'room'
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(20), nullable=False, unique=True)

    def __repr__(self):
        return f'<Room {self.room_number}>'

class AssignedCourse(db.Model):
    __tablename__ = 'assigned_course'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    part = db.Column(db.String(10), nullable=False, default='Full') # Full, Part A, Part B
    
    teacher = db.relationship('Teacher', backref='assigned_courses')
    course = db.relationship('Course', back_populates='assigned_teachers')

    __table_args__ = (db.UniqueConstraint('teacher_id', 'course_id', 'part', name='_teacher_course_part_uc'),)

    def __repr__(self):
        return f'<AssignedCourse {self.teacher.short_name} -> {self.course.course_code} ({self.part})>'

class Routine(db.Model):
    __tablename__ = 'routine'
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)
    time_slot = db.Column(db.String(50), nullable=False)
    room_number = db.Column(db.String(50), nullable=False)
    course_code = db.Column(db.String(20))
    teacher_short_name = db.Column(db.String(50))
    part = db.Column(db.String(10)) 
    is_shared = db.Column(db.Boolean, default=False)
    shared_with = db.Column(db.String(50))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))

    __table_args__ = (db.UniqueConstraint('day', 'time_slot', 'room_number', name='_day_time_room_uc'),)

    def __repr__(self):
        return f'<Routine {self.day} {self.time_slot} {self.room_number} -> {self.course_code}>'
