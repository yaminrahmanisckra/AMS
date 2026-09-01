"""Append-only audit log. Writes never join the caller's DB transaction.

If `audit_log` is missing (SQL not applied yet) or insert fails, the helper
returns None and the original save/commit is unaffected.
"""
from __future__ import annotations

import json
from datetime import datetime

from flask import has_request_context, request
from sqlalchemy.orm import sessionmaker

from extensions import db


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    actor_user_id = db.Column(db.Integer, nullable=True)
    actor_username = db.Column(db.String(150), nullable=True)
    actor_role = db.Column(db.String(120), nullable=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_type = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.String(64), nullable=True)
    before_json = db.Column(db.Text, nullable=True)
    after_json = db.Column(db.Text, nullable=True)
    extra_json = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    path = db.Column(db.String(255), nullable=True)


USER_AUDIT_FIELDS = ('username', 'email', 'full_name', 'role', 'teacher_id', 'must_change_password')
CLASS_MARK_FIELDS = (
    'assessment1', 'assessment2', 'assessment3', 'assessment4',
    'assessment_total', 'assessment_total_40',
    'sessional_report', 'sessional_viva', 'assessment_absent',
)
RESULT_MARK_FIELDS = (
    'attendance', 'continuous_assessment', 'part_a', 'part_b',
    'sessional_report', 'sessional_viva',
    'supervisor_assessment', 'proposal_presentation', 'project_report', 'defense',
    'thesis_evaluation', 'presentation', 'viva',
    'total_marks', 'grade_letter', 'grade_point', 'is_retake',
)


def _json_dump(value):
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return None


def snapshot_attrs(obj, fields):
    if obj is None:
        return {}
    out = {}
    for field in fields:
        val = getattr(obj, field, None)
        if hasattr(val, 'isoformat'):
            try:
                val = val.isoformat()
            except Exception:
                val = str(val)
        out[field] = val
    return out


def dict_diff(before, after):
    before = before or {}
    after = after or {}
    keys = set(before) | set(after)
    old, new = {}, {}
    for key in keys:
        if before.get(key) != after.get(key):
            old[key] = before.get(key)
            new[key] = after.get(key)
    return old, new


def write_audit(action, entity_type, entity_id=None, before=None, after=None, extra=None):
    """Insert one audit row on a separate connection. Never raises to the caller."""
    try:
        actor_id = actor_username = actor_role = ip = path = None
        if has_request_context():
            try:
                from flask_login import current_user
                if current_user.is_authenticated:
                    actor_id = current_user.id
                    actor_username = current_user.username
                    actor_role = getattr(current_user, 'active_role', None) or current_user.role
            except Exception:
                pass
            try:
                from utils.request_ip import client_ip
                ip = client_ip() or request.remote_addr
                path = (request.path or '')[:255]
            except Exception:
                pass

        factory = sessionmaker(bind=db.engine, expire_on_commit=False)
        session = factory()
        try:
            session.add(AuditLog(
                created_at=datetime.utcnow(),
                actor_user_id=actor_id,
                actor_username=actor_username,
                actor_role=(str(actor_role)[:120] if actor_role else None),
                action=(action or '')[:80],
                entity_type=(entity_type or '')[:40],
                entity_id=(str(entity_id)[:64] if entity_id is not None else None),
                before_json=_json_dump(before),
                after_json=_json_dump(after),
                extra_json=_json_dump(extra),
                ip=(ip[:64] if ip else None),
                path=path,
            ))
            session.commit()
        finally:
            session.close()
        return True
    except Exception as exc:
        try:
            from flask import current_app
            msg = str(exc).lower()
            missing = (
                'audit_log' in msg
                or "doesn't exist" in msg
                or 'does not exist' in msg
                or 'no such table' in msg
            )
            global _missing_table_logged
            if missing:
                if not _missing_table_logged:
                    _missing_table_logged = True
                    current_app.logger.warning(
                        'audit_log table is missing; writes skipped until SQL is applied'
                    )
            else:
                current_app.logger.warning('audit_log write skipped', exc_info=True)
        except Exception:
            pass
        return None


_missing_table_logged = False


def snapshot_rows(objects, fields, extra_attrs=('student_id',)):
    """Map object.id -> snapshot. Safe if objects is empty."""
    out = {}
    for obj in objects or []:
        if obj is None:
            continue
        oid = getattr(obj, 'id', None)
        if oid is None:
            continue
        snap = snapshot_attrs(obj, fields)
        for attr in extra_attrs:
            if hasattr(obj, attr):
                snap[attr] = getattr(obj, attr)
        out[oid] = snap
    return out


def snapshot_result_marks_by_student(students, subject_id, mark_model):
    """Key snapshots by student PK so new vs existing rows still match."""
    out = {}
    try:
        students = list(students or [])
        by_id = {s.id: s for s in students}
        marks = []
        if by_id:
            marks = mark_model.query.filter(
                mark_model.subject_id == subject_id,
                mark_model.student_id.in_(list(by_id)),
            ).all()
        marks_by_student = {m.student_id: m for m in marks}
        for student in students:
            mark = marks_by_student.get(student.id)
            snap = snapshot_attrs(mark, RESULT_MARK_FIELDS) if mark else {}
            snap['student_id'] = student.student_id
            out[student.id] = snap
    except Exception:
        return {}
    return out


def write_row_changes(action, entity_type, entity_id, before_by_id, after_by_id, extra=None):
    """Write one audit row if any tracked fields changed. Never raises."""
    try:
        changes = changed_row_list(before_by_id, after_by_id)
        if not changes:
            return None
        payload = dict(extra or {})
        payload['changed_count'] = len(changes)
        return write_audit(
            action,
            entity_type,
            entity_id,
            after={'changes': changes},
            extra=payload,
        )
    except Exception:
        return None


def changed_row_list(before_by_id, after_by_id, id_label='id'):
    """Return compact list of {id, student_id?, before, after} for changed rows only."""
    changes = []
    ids = set(before_by_id) | set(after_by_id)
    for row_id in ids:
        old = before_by_id.get(row_id) or {}
        new = after_by_id.get(row_id) or {}
        old_d, new_d = dict_diff(old, new)
        if not old_d and not new_d:
            continue
        item = {id_label: row_id, 'before': old_d, 'after': new_d}
        sid = new.get('student_id') or old.get('student_id')
        if sid is not None:
            item['student_id'] = sid
        changes.append(item)
    return changes
