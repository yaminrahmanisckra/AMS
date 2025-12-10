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


