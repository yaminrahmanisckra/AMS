from extensions import db
from datetime import datetime

class AcademicCalendarEvent(db.Model):
    """Model for academic calendar events (holidays, events, etc.)"""
    __tablename__ = 'academic_calendar_event'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.Date, nullable=False)  # Start date
    end_date = db.Column(db.Date, nullable=True)  # End date (optional, for date ranges)
    event_type = db.Column(db.String(50), nullable=False)  # 'holiday', 'event', 'exam', etc.
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)  # For weekly holidays like Friday/Saturday
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Note: created_by relationship removed to avoid SQLAlchemy User class resolution issues
    # Use User.query.get(created_by_id) to access the user who created the event
    
    def __repr__(self):
        if self.end_date and self.end_date != self.event_date:
            return f'<AcademicCalendarEvent {self.title} - {self.event_date} to {self.end_date}>'
        return f'<AcademicCalendarEvent {self.title} - {self.event_date}>'


class BatchCustomEvent(db.Model):
    """Model for batch-specific custom events created by teachers (Class Test, Viva, Presentation, etc.)"""
    __tablename__ = 'batch_custom_event'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False)
    batch = db.Column(db.String(20), nullable=False)  # Student batch (e.g., '2021', '2022')
    title = db.Column(db.String(200), nullable=False)  # Event title (e.g., 'Class Test 1', 'Viva', 'Presentation')
    description = db.Column(db.Text, nullable=True)  # Optional description
    event_date = db.Column(db.Date, nullable=False)  # Event date
    event_time = db.Column(db.Time, nullable=True)  # Optional event time
    event_type = db.Column(db.String(50), nullable=False, default='custom')  # 'class_test', 'viva', 'presentation', 'assignment', etc.
    location = db.Column(db.String(200), nullable=True)  # Optional location (e.g., 'Room 101', 'Lab 2')
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to Session (class session)
    session = db.relationship('Session', backref=db.backref('batch_custom_events', lazy='dynamic', cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<BatchCustomEvent {self.title} - Batch {self.batch} - {self.event_date}>'
    
    def to_dict(self):
        """Convert event to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'batch': self.batch,
            'title': self.title,
            'description': self.description,
            'event_date': self.event_date.strftime('%Y-%m-%d') if self.event_date else None,
            'event_time': self.event_time.strftime('%H:%M') if self.event_time else None,
            'event_type': self.event_type,
            'location': self.location,
            'course_code': self.session.course_code if self.session else None,
            'course_name': self.session.course_name if self.session else None,
        }


