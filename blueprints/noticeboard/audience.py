"""Audience resolution and authorization for the noticeboard."""
from __future__ import annotations

from flask_login import current_user

from extensions import db
from role_utils import has_role, has_teacher_privileges, is_admin, parse_roles
from user_models import User

from .models import NoticeTarget


def can_compose_notices(user=None) -> bool:
    user = user or current_user
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return has_teacher_privileges(user) or has_role(user, 'head', 'dean', 'admin')


def can_broadcast(user=None) -> bool:
    """Head / dean / admin may target all students, any batch, any session."""
    user = user or current_user
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return is_admin(user) or has_role(user, 'head', 'dean')


def can_manage_notice(notice, user=None) -> bool:
    user = user or current_user
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if is_admin(user) or has_role(user, 'head', 'dean'):
        return True
    return notice.author_user_id == user.id


def is_student_viewer(user=None) -> bool:
    user = user or current_user
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    active = getattr(user, 'active_role', None)
    if active:
        return 'student' in parse_roles(active) and not can_compose_notices(user)
    roles = set(parse_roles(getattr(user, 'role', None)))
    return 'student' in roles and not (roles & {'teacher', 'head', 'dean', 'admin', 'teaching_assistant'})


def get_current_teacher():
    """Resolve Teacher for the logged-in user without auto-creating."""
    from blueprints.class_management.models import Teacher

    user = current_user
    if getattr(user, 'teacher_id', None):
        teacher = Teacher.query.get(user.teacher_id)
        if teacher:
            return teacher
    name = (getattr(user, 'full_name', None) or '').strip()
    if name:
        return Teacher.query.filter_by(name=name).first()
    return None


def teacher_owned_session_ids(teacher_id: int) -> set[int]:
    from blueprints.class_management.models import Session
    from utils.window_utils import query_for_window

    rows = (
        query_for_window(Session)
        .filter_by(teacher_id=teacher_id, archived=False)
        .with_entities(Session.id)
        .all()
    )
    return {r[0] for r in rows}



def class_students_for_session(session_id: int):
    from blueprints.class_management.models import ClassStudent, Session
    from blueprints.student_management.models import Student

    q = ClassStudent.query.filter(ClassStudent.session_id == session_id)
    session = Session.query.get(session_id)
    if session and not getattr(session, 'is_external_course', False):
        q = q.filter(ClassStudent.student_id.in_(db.session.query(Student.student_id)))
    return q.all()


def allowed_student_ids_for_teacher(teacher_id: int) -> set[str]:
    from blueprints.class_management.models import ClassStudent, Session
    from blueprints.student_management.models import Student

    session_ids = teacher_owned_session_ids(teacher_id)
    if not session_ids:
        return set()
    q = ClassStudent.query.filter(ClassStudent.session_id.in_(session_ids))
    q = q.filter(ClassStudent.student_id.in_(db.session.query(Student.student_id)))
    return {cs.student_id for cs in q.all()}


def parse_targets_from_form(form) -> list[tuple[str, str | None]]:
    """Parse audience fields from request.form into (type, value) tuples."""
    targets: list[tuple[str, str | None]] = []
    seen = set()

    def _add(ttype: str, value: str | None):
        key = (ttype, value or '')
        if key in seen:
            return
        seen.add(key)
        targets.append((ttype, value))

    if form.get('audience_all_students') in ('1', 'on', 'true', 'yes'):
        _add(NoticeTarget.TARGET_ALL, None)

    for batch in form.getlist('audience_batches'):
        batch = (batch or '').strip()
        if batch:
            _add(NoticeTarget.TARGET_BATCH, batch)

    for sid in form.getlist('audience_sessions'):
        sid = (sid or '').strip()
        if sid.isdigit():
            _add(NoticeTarget.TARGET_SESSION, sid)

    for student_id in form.getlist('audience_students'):
        student_id = (student_id or '').strip()
        if student_id:
            _add(NoticeTarget.TARGET_STUDENT, student_id)

    return targets


def validate_targets_for_user(targets: list[tuple[str, str | None]], user=None) -> tuple[list[tuple[str, str | None]], str | None]:
    """Authorize and normalize targets. Returns (targets, error_message)."""
    from blueprints.class_management.models import Session
    from utils.window_utils import query_for_window

    user = user or current_user
    if not targets:
        return [], 'Select at least one audience (course, batch, students, or all students).'

    window_session_ids = {
        r[0]
        for r in query_for_window(Session).filter_by(archived=False).with_entities(Session.id).all()
    }

    if can_broadcast(user):
        cleaned = []
        for ttype, value in targets:
            if ttype == NoticeTarget.TARGET_ALL:
                cleaned.append((ttype, None))
            elif ttype == NoticeTarget.TARGET_BATCH and value:
                cleaned.append((ttype, value))
            elif ttype == NoticeTarget.TARGET_SESSION and value and value.isdigit():
                sid = int(value)
                if sid in window_session_ids:
                    cleaned.append((ttype, value))
            elif ttype == NoticeTarget.TARGET_STUDENT and value:
                cleaned.append((ttype, value))
        if not cleaned:
            return [], 'No valid audience selected for the active window.'
        return cleaned, None

    # Teacher path
    teacher = get_current_teacher()
    if not teacher:
        return [], 'No teacher profile linked to your account.'

    owned_sessions = teacher_owned_session_ids(teacher.id)
    allowed_students = allowed_student_ids_for_teacher(teacher.id)
    cleaned = []
    for ttype, value in targets:
        if ttype == NoticeTarget.TARGET_ALL:
            continue  # teachers cannot broadcast to all
        if ttype == NoticeTarget.TARGET_BATCH:
            continue  # teachers use sessions/students only
        if ttype == NoticeTarget.TARGET_SESSION and value and value.isdigit():
            if int(value) in owned_sessions:
                cleaned.append((ttype, value))
        elif ttype == NoticeTarget.TARGET_STUDENT and value:
            if value in allowed_students:
                cleaned.append((ttype, value))

    if not cleaned:
        return [], 'Select one or more of your courses, or students from your course rosters.'
    return cleaned, None


def resolve_recipient_users(targets: list[tuple[str, str | None]]) -> list[User]:
    """Expand targets to unique User rows (students with login accounts)."""
    from blueprints.student_management.models import Student

    usernames: set[str] = set()

    for ttype, value in targets:
        if ttype == NoticeTarget.TARGET_ALL:
            for sid, in Student.query.with_entities(Student.student_id).all():
                if sid:
                    usernames.add(sid)
        elif ttype == NoticeTarget.TARGET_BATCH and value:
            for sid, in Student.query.filter_by(batch=value).with_entities(Student.student_id).all():
                if sid:
                    usernames.add(sid)
        elif ttype == NoticeTarget.TARGET_SESSION and value and str(value).isdigit():
            for cs in class_students_for_session(int(value)):
                if cs.student_id:
                    usernames.add(cs.student_id)
        elif ttype == NoticeTarget.TARGET_STUDENT and value:
            usernames.add(value)

    if not usernames:
        return []

    users = User.query.filter(User.username.in_(usernames)).all()
    # Prefer accounts that look like students, but do not hard-filter by role
    # (some students may have multi-role strings).
    return users


def audience_options_for_user(user=None) -> dict:
    """Data for the compose audience picker (active window only)."""
    from blueprints.class_management.models import Session
    from blueprints.student_management.models import Student
    from utils.window_utils import query_for_window

    user = user or current_user
    broadcast = can_broadcast(user)

    sessions_out = []
    students_out = []
    batches_out = []

    if broadcast:
        sessions = (
            query_for_window(Session)
            .filter_by(archived=False)
            .order_by(Session.academic_session.desc(), Session.course_code)
            .limit(500)
            .all()
        )
        for s in sessions:
            label_parts = [
                s.course_code or '',
                s.course_name or '',
                f"Y{s.year}" if s.year else '',
                s.term or '',
                s.academic_session or '',
            ]
            teacher_name = s.teacher.name if s.teacher else ''
            sessions_out.append({
                'id': s.id,
                'label': ' — '.join(p for p in label_parts if p),
                'teacher': teacher_name,
            })
        batches_out = sorted({
            b for (b,) in Student.query.with_entities(Student.batch).distinct().all() if b
        })
        for st in Student.query.order_by(Student.student_id).limit(2000).all():
            students_out.append({
                'id': st.student_id,
                'name': st.name,
                'batch': st.batch or '',
                'label': f'{st.student_id} — {st.name}' + (f' ({st.batch})' if st.batch else ''),
            })
    else:
        teacher = get_current_teacher()
        if teacher:
            sessions = (
                query_for_window(Session)
                .filter_by(teacher_id=teacher.id, archived=False)
                .order_by(Session.academic_session.desc(), Session.course_code)
                .all()
            )
            session_ids = []
            for s in sessions:
                session_ids.append(s.id)
                label_parts = [
                    s.course_code or '',
                    s.course_name or '',
                    f"Y{s.year}" if s.year else '',
                    s.term or '',
                    s.academic_session or '',
                ]
                sessions_out.append({
                    'id': s.id,
                    'label': ' — '.join(p for p in label_parts if p),
                    'teacher': teacher.name,
                })
            seen = set()
            for sid in session_ids:
                for cs in class_students_for_session(sid):
                    if cs.student_id in seen:
                        continue
                    seen.add(cs.student_id)
                    students_out.append({
                        'id': cs.student_id,
                        'name': cs.name,
                        'batch': '',
                        'label': f'{cs.student_id} — {cs.name}',
                    })
            students_out.sort(key=lambda x: x['id'])

    return {
        'can_broadcast': broadcast,
        'sessions': sessions_out,
        'batches': batches_out,
        'students': students_out,
    }


def student_matches_notice(notice, student_username: str, student_batch: str | None, session_ids: set[int]) -> bool:
    for t in notice.targets or []:
        if t.target_type == NoticeTarget.TARGET_ALL:
            return True
        if t.target_type == NoticeTarget.TARGET_STUDENT and t.target_value == student_username:
            return True
        if t.target_type == NoticeTarget.TARGET_BATCH and student_batch and t.target_value == student_batch:
            return True
        if t.target_type == NoticeTarget.TARGET_SESSION and t.target_value and str(t.target_value).isdigit():
            if int(t.target_value) in session_ids:
                return True
    return False


def notices_visible_to_student(student_username: str):
    """Return non-deleted notices visible to this student in the active window."""
    from blueprints.class_management.models import ClassStudent, Session
    from blueprints.student_management.models import Student
    from utils.window_utils import query_for_window
    from .models import Notice

    student = Student.query.filter_by(student_id=student_username).first()
    batch = student.batch if student else None

    # Only count class sessions that belong to the active operational window
    window_session_ids = {
        r[0]
        for r in query_for_window(Session).with_entities(Session.id).all()
    }
    if window_session_ids:
        session_ids = {
            r[0]
            for r in ClassStudent.query.filter(
                ClassStudent.student_id == student_username,
                ClassStudent.session_id.in_(window_session_ids),
            ).with_entities(ClassStudent.session_id).all()
        }
    else:
        session_ids = set()

    notices = (
        query_for_window(Notice)
        .filter(Notice.deleted_at.is_(None))
        .order_by(Notice.notice_date.desc(), Notice.created_at.desc())
        .all()
    )
    return [n for n in notices if student_matches_notice(n, student_username, batch, session_ids)]


def format_audience_summary(notice) -> str:
    parts = []
    for t in notice.targets or []:
        if t.target_type == NoticeTarget.TARGET_ALL:
            parts.append('All students')
        elif t.target_type == NoticeTarget.TARGET_BATCH:
            parts.append(f'Batch {t.target_value}')
        elif t.target_type == NoticeTarget.TARGET_SESSION:
            from blueprints.class_management.models import Session
            s = Session.query.get(int(t.target_value)) if t.target_value and str(t.target_value).isdigit() else None
            if s:
                parts.append(f'{s.course_code or "Course"} ({s.academic_session or ""})'.strip())
            else:
                parts.append(f'Session {t.target_value}')
        elif t.target_type == NoticeTarget.TARGET_STUDENT:
            parts.append(t.target_value)
    return ', '.join(parts) if parts else '—'
