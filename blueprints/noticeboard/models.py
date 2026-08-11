"""Noticeboard models: notices and flexible audience targets."""
from datetime import datetime

from extensions import db


def _bd_today():
    """Default notice_date = today's calendar date in Asia/Dhaka."""
    from utils.timezone import bd_now
    return bd_now().date()


class Notice(db.Model):
    __tablename__ = 'notice'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    author_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    notice_date = db.Column(db.Date, nullable=False, default=_bd_today, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    window_id = db.Column(
        db.Integer,
        db.ForeignKey('operational_window.id'),
        nullable=True,
        index=True,
    )

    author = db.relationship('User', foreign_keys=[author_user_id])
    operational_window = db.relationship(
        'OperationalWindow',
        backref=db.backref('notices', lazy='dynamic'),
    )
    targets = db.relationship(
        'NoticeTarget',
        back_populates='notice',
        cascade='all, delete-orphan',
        lazy='joined',
    )

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def __repr__(self):
        return f'<Notice {self.id}: {self.title[:40]}>'


class NoticeTarget(db.Model):
    """Audience row for a notice.

    target_type: all_students | batch | session | student
    target_value: batch string / session id / student_id (username); empty for all_students
    """
    __tablename__ = 'notice_target'

    TARGET_ALL = 'all_students'
    TARGET_BATCH = 'batch'
    TARGET_SESSION = 'session'
    TARGET_STUDENT = 'student'
    TARGET_TYPES = (TARGET_ALL, TARGET_BATCH, TARGET_SESSION, TARGET_STUDENT)

    id = db.Column(db.Integer, primary_key=True)
    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id'), nullable=False, index=True)
    target_type = db.Column(db.String(20), nullable=False)
    target_value = db.Column(db.String(100), nullable=True)

    notice = db.relationship('Notice', back_populates='targets')

    def __repr__(self):
        return f'<NoticeTarget {self.target_type}:{self.target_value}>'
