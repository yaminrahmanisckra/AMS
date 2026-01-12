from extensions import db
from datetime import datetime
from blueprints.class_management.models import Teacher
from blueprints.course_management.models import Course

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

class SavedRoutine(db.Model):
    __tablename__ = 'saved_routine'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(100))
    is_revealed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # NOTE: Relationship removed to avoid ORM errors when saved_routine_id column doesn't exist in DB
    # Use raw SQL for routine operations instead
    
    def __repr__(self):
        return f'<SavedRoutine {self.year}: {self.name or self.year}>'

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
    year = db.Column(db.String(20))  # Store year for color coding
    term = db.Column(db.String(20))   # Store term for color coding
    saved_routine_id = db.Column(db.Integer, db.ForeignKey('saved_routine.id'), nullable=True)
    # New fields for enhanced routine management
    batch = db.Column(db.String(20))  # Batch for color coding
    color_code = db.Column(db.String(7))  # Hex color for batch
    is_custom = db.Column(db.Boolean, default=False)  # Custom entry flag
    custom_course_name = db.Column(db.String(200))  # For custom entries
    placement_order = db.Column(db.Integer)  # Order of placement

    __table_args__ = (db.UniqueConstraint('day', 'time_slot', 'room_number', 'saved_routine_id', name='_day_time_room_saved_routine_uc'),)

    def __repr__(self):
        return f'<Routine {self.day} {self.time_slot} {self.room_number} -> {self.course_code}>'

class RoutineTimeSlot(db.Model):
    """Model for customizable time slots per saved routine"""
    __tablename__ = 'routine_time_slot'
    id = db.Column(db.Integer, primary_key=True)
    saved_routine_id = db.Column(db.Integer, db.ForeignKey('saved_routine.id'), nullable=False)
    time_slot = db.Column(db.String(50), nullable=False)
    display_order = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    saved_routine = db.relationship('SavedRoutine', backref=db.backref('time_slots', lazy='dynamic'))
    
    __table_args__ = (db.UniqueConstraint('saved_routine_id', 'time_slot', name='_saved_routine_time_slot_uc'),)
    
    def __repr__(self):
        return f'<RoutineTimeSlot {self.time_slot} (Order: {self.display_order})>'
