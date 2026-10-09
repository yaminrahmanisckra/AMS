"""Student, Officer, and Teacher dashboard card visibility settings (admin-controlled)."""
from datetime import datetime

from flask import flash, redirect, url_for
from flask_login import current_user

from extensions import db


STUDENT_DASHBOARD_CARDS = (
    {
        'card_key': 'course_files',
        'label': 'Course Files',
        'description': 'Download course outlines and files uploaded by teachers.',
        'sort_order': 1,
    },
    {
        'card_key': 'question_bank',
        'label': 'Question Bank',
        'description': "Download previous years' question papers in PDF.",
        'sort_order': 2,
    },
    {
        'card_key': 'class_routine',
        'label': 'Class Routine',
        'description': 'View and download your class routine.',
        'sort_order': 3,
    },
    {
        'card_key': 'academic_calendar',
        'label': 'Academic Calendar',
        'description': 'View holidays, events, and important academic dates.',
        'sort_order': 4,
    },
    {
        'card_key': 'my_scores',
        'label': 'My Scores',
        'description': 'View your assessment and attendance scores.',
        'sort_order': 5,
    },
    {
        'card_key': 'course_registration',
        'label': 'Course Registration',
        'description': 'Select session, year, term and download your registration form.',
        'sort_order': 6,
    },
    {
        'card_key': 'noticeboard',
        'label': 'Noticeboard',
        'description': 'Read notices from teachers and Head of Discipline.',
        'sort_order': 7,
    },
    {
        'card_key': 'socrates',
        'label': 'Socrates',
        'description': 'Argue with the AI companion on teacher-set debate topics.',
        'sort_order': 8,
    },
    {
        'card_key': 'mock_trial_simulator',
        'label': 'Mock Trial Simulator',
        'description': 'Practice mock trials in a virtual courtroom that simulates real court.',
        'sort_order': 9,
    },
    {
        'card_key': 'assignments',
        'label': 'Assignments',
        'description': 'Write individual and group assignments inside AMS.',
        'sort_order': 10,
    },
)


class StudentDashboardCard(db.Model):
    """Per-card enable/disable for the student dashboard."""
    __tablename__ = 'student_dashboard_card'

    id = db.Column(db.Integer, primary_key=True)
    card_key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<StudentDashboardCard {self.card_key} enabled={self.is_enabled}>'


def ensure_student_dashboard_cards():
    """Insert any missing default cards (all enabled). Returns ordered rows."""
    existing = {
        row.card_key: row
        for row in StudentDashboardCard.query.all()
    }
    created = False
    for spec in STUDENT_DASHBOARD_CARDS:
        row = existing.get(spec['card_key'])
        if row is None:
            row = StudentDashboardCard(
                card_key=spec['card_key'],
                label=spec['label'],
                description=spec['description'],
                is_enabled=True,
                sort_order=spec['sort_order'],
            )
            db.session.add(row)
            created = True
        else:
            # Keep label/description/sort_order in sync with code defaults.
            if row.label != spec['label']:
                row.label = spec['label']
            if row.description != spec['description']:
                row.description = spec['description']
            if row.sort_order != spec['sort_order']:
                row.sort_order = spec['sort_order']
    if created:
        db.session.commit()
    return StudentDashboardCard.query.order_by(
        StudentDashboardCard.sort_order.asc(),
        StudentDashboardCard.id.asc(),
    ).all()


def get_student_dashboard_card_map():
    """Return {card_key: is_enabled}. Missing keys default to True."""
    try:
        rows = ensure_student_dashboard_cards()
        return {row.card_key: bool(row.is_enabled) for row in rows}
    except Exception:
        # Table missing or DB error — fail open so students keep access.
        db.session.rollback()
        return {spec['card_key']: True for spec in STUDENT_DASHBOARD_CARDS}


def is_student_dashboard_card_enabled(card_key):
    """True when the card is enabled (or unknown / DB unavailable)."""
    card_map = get_student_dashboard_card_map()
    return bool(card_map.get(card_key, True))


def _is_pure_student_user(user=None):
    """Student without teacher privileges / admin — subject to card soft-blocks."""
    user = user or current_user
    if not getattr(user, 'is_authenticated', False):
        return False
    try:
        from role_utils import parse_roles, has_teacher_privileges, is_admin
    except ImportError:
        return False
    roles = parse_roles(getattr(user, 'role', None))
    if 'student' not in roles:
        return False
    if is_admin(user) or has_teacher_privileges(user):
        return False
    return True


def require_student_dashboard_card(card_key, message=None):
    """
    Soft-block pure students when a dashboard card is disabled.
    Returns a redirect response, or None if access is allowed.
    """
    if not _is_pure_student_user():
        return None
    if is_student_dashboard_card_enabled(card_key):
        return None
    flash(
        message or 'This feature is currently disabled by the administrator.',
        'warning',
    )
    return redirect(url_for('student_dashboard'))


OFFICER_DASHBOARD_CARDS = (
    {
        'card_key': 'exam_info',
        'label': 'Exam Info',
        'description': 'View examination information and schedules.',
        'sort_order': 1,
    },
    {
        'card_key': 'class_routine',
        'label': 'Class Routine',
        'description': 'View published class schedules (view only).',
        'sort_order': 2,
    },
    {
        'card_key': 'academic_calendar',
        'label': 'Academic Calendar',
        'description': 'View holidays, events, and important academic dates.',
        'sort_order': 3,
    },
    {
        'card_key': 'leave_application',
        'label': 'Leave Application',
        'description': 'Fill out leave applications and download official PDFs.',
        'sort_order': 4,
    },
    {
        'card_key': 'remuneration',
        'label': 'Remuneration',
        'description': 'Manage remuneration and payment information.',
        'sort_order': 5,
    },
    {
        'card_key': 'admission_exam',
        'label': 'Admission Exam',
        'description': 'Masters admission cycles, applications, and admit cards.',
        'sort_order': 6,
    },
)


class OfficerDashboardCard(db.Model):
    """Per-card enable/disable for the officer dashboard."""
    __tablename__ = 'officer_dashboard_card'

    id = db.Column(db.Integer, primary_key=True)
    card_key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<OfficerDashboardCard {self.card_key} enabled={self.is_enabled}>'


def ensure_officer_dashboard_cards():
    """Insert any missing default cards (all enabled). Returns ordered rows."""
    existing = {
        row.card_key: row
        for row in OfficerDashboardCard.query.all()
    }
    created = False
    for spec in OFFICER_DASHBOARD_CARDS:
        row = existing.get(spec['card_key'])
        if row is None:
            row = OfficerDashboardCard(
                card_key=spec['card_key'],
                label=spec['label'],
                description=spec['description'],
                is_enabled=True,
                sort_order=spec['sort_order'],
            )
            db.session.add(row)
            created = True
        else:
            if row.label != spec['label']:
                row.label = spec['label']
            if row.description != spec['description']:
                row.description = spec['description']
            if row.sort_order != spec['sort_order']:
                row.sort_order = spec['sort_order']
    if created:
        db.session.commit()
    return OfficerDashboardCard.query.order_by(
        OfficerDashboardCard.sort_order.asc(),
        OfficerDashboardCard.id.asc(),
    ).all()


def get_officer_dashboard_card_map():
    """Return {card_key: is_enabled}. Missing keys default to True."""
    try:
        rows = ensure_officer_dashboard_cards()
        return {row.card_key: bool(row.is_enabled) for row in rows}
    except Exception:
        return {spec['card_key']: True for spec in OFFICER_DASHBOARD_CARDS}


def is_officer_dashboard_card_enabled(card_key):
    """True when the card is enabled (or unknown / DB unavailable)."""
    card_map = get_officer_dashboard_card_map()
    return bool(card_map.get(card_key, True))


def _is_pure_officer_user(user=None):
    """Officer without teacher privileges / admin — subject to card soft-blocks."""
    user = user or current_user
    if not getattr(user, 'is_authenticated', False):
        return False
    try:
        from role_utils import parse_roles, has_teacher_privileges, is_admin
    except ImportError:
        return False
    roles = parse_roles(getattr(user, 'role', None))
    if 'officer' not in roles:
        return False
    if is_admin(user) or has_teacher_privileges(user):
        return False
    return True


def require_officer_dashboard_card(card_key, message=None):
    """
    Soft-block pure officers when a dashboard card is disabled.
    Returns a redirect response, or None if access is allowed.
    """
    if not _is_pure_officer_user():
        return None
    if is_officer_dashboard_card_enabled(card_key):
        return None
    flash(
        message or 'This feature is currently disabled by the administrator.',
        'warning',
    )
    return redirect(url_for('index'))


TEACHER_DASHBOARD_CARDS = (
    {
        'card_key': 'socrates',
        'label': 'Socrates',
        'description': 'Set debate topics; students argue with the AI companion as a graded assignment.',
        'sort_order': 1,
    },
    {
        'card_key': 'mock_trial_simulator',
        'label': 'Mock Trial Simulator',
        'description': 'Build mock-trial games and run a virtual courtroom that simulates real court.',
        'sort_order': 2,
    },
)


class TeacherDashboardCard(db.Model):
    """Per-card enable/disable for the teacher (main) dashboard."""
    __tablename__ = 'teacher_dashboard_card'

    id = db.Column(db.Integer, primary_key=True)
    card_key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<TeacherDashboardCard {self.card_key} enabled={self.is_enabled}>'


def ensure_teacher_dashboard_cards():
    """Insert any missing default cards (all enabled). Returns ordered rows."""
    existing = {
        row.card_key: row
        for row in TeacherDashboardCard.query.all()
    }
    created = False
    for spec in TEACHER_DASHBOARD_CARDS:
        row = existing.get(spec['card_key'])
        if row is None:
            row = TeacherDashboardCard(
                card_key=spec['card_key'],
                label=spec['label'],
                description=spec['description'],
                is_enabled=True,
                sort_order=spec['sort_order'],
            )
            db.session.add(row)
            created = True
        else:
            if row.label != spec['label']:
                row.label = spec['label']
            if row.description != spec['description']:
                row.description = spec['description']
            if row.sort_order != spec['sort_order']:
                row.sort_order = spec['sort_order']
    if created:
        db.session.commit()
    return TeacherDashboardCard.query.order_by(
        TeacherDashboardCard.sort_order.asc(),
        TeacherDashboardCard.id.asc(),
    ).all()


def get_teacher_dashboard_card_map():
    """Return {card_key: is_enabled}. Missing keys default to True."""
    try:
        rows = ensure_teacher_dashboard_cards()
        return {row.card_key: bool(row.is_enabled) for row in rows}
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return {spec['card_key']: True for spec in TEACHER_DASHBOARD_CARDS}


def is_teacher_dashboard_card_enabled(card_key):
    """True when the card is enabled (or unknown / DB unavailable)."""
    card_map = get_teacher_dashboard_card_map()
    return bool(card_map.get(card_key, True))


def _is_teacher_dashboard_subject(user=None):
    """Teachers/heads (not admins) subject to teacher-dashboard card soft-blocks."""
    user = user or current_user
    if not getattr(user, 'is_authenticated', False):
        return False
    try:
        from role_utils import get_effective_roles, is_admin
    except ImportError:
        return False
    if is_admin(user):
        return False
    roles = set(get_effective_roles(user))
    if 'teaching_assistant' in roles:
        return False
    return bool(roles & {'teacher', 'head', 'dean'})


def require_teacher_dashboard_card(card_key, message=None):
    """
    Soft-block teachers/heads when a teacher dashboard card is disabled.
    Returns a redirect response, or None if access is allowed.
    """
    if not _is_teacher_dashboard_subject():
        return None
    if is_teacher_dashboard_card_enabled(card_key):
        return None
    flash(
        message or 'This feature is currently disabled by the administrator.',
        'warning',
    )
    return redirect(url_for('index'))
