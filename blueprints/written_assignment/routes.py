"""Teacher and student routes for in-AMS written assignments."""
import json
import os
import re
from datetime import datetime
from io import BytesIO
from uuid import uuid4

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from markupsafe import Markup
from werkzeug.utils import secure_filename

from extensions import db
from utils.outline_richtext import html_is_empty, html_to_plain_text, sanitize_outline_html
from utils.ownership import resolve_caller_teacher

from blueprints.class_management.models import (
    SOCRATES_AI_USE_WARNING,
    ClassStudent,
    Session,
    StudentNotification,
)
from utils.window_utils import filter_by_window_sessions, get_or_404_for_window

from . import written_assignment_bp
from .export import build_docx, build_pdf
from .models import (
    WrittenAssignment,
    WrittenAssignmentEvaluation,
    WrittenAssignmentGroup,
    WrittenAssignmentMember,
    WrittenAssignmentPart,
    WrittenAssignmentPost,
    WrittenAssignmentPostFile,
    WrittenAssignmentPostVote,
    WrittenAssignmentSection,
    evaluate_paste,
    part_integrity,
    plain_word_count,
    rebuild_part_from_sections,
    record_composition,
    student_writing_warning,
)

try:
    from blueprints.student_management.models import Student
except ImportError:
    Student = None

try:
    from user_models import User
except ImportError:
    User = None


_MAX_HTML = 500_000
_MAX_DISCUSSION_FILES = 3
_IMAGE_KINDS = frozenset({'png', 'jpg', 'jpeg', 'gif', 'webp'})


def _roster(session_id):
    query = ClassStudent.query.filter(ClassStudent.session_id == session_id)
    session_obj = Session.query.get(session_id)
    if Student is not None and session_obj and not getattr(session_obj, 'is_external_course', False):
        query = query.filter(ClassStudent.student_id.in_(db.session.query(Student.student_id)))
    return query.order_by(ClassStudent.student_id).all()


def _student_sessions(student_id):
    query = ClassStudent.query.filter_by(student_id=student_id)
    try:
        query = filter_by_window_sessions(
            query,
            ClassStudent.session_id,
            session_model=Session,
            admin_override=False,
        )
    except Exception:
        current_app.logger.exception('Window filter failed for assignment roster')
    return {row.session_id: row for row in query.all()}


def _course_label(session_obj):
    if not session_obj:
        return ''
    code = (session_obj.course_code or '').strip()
    name = (session_obj.course_name or '').strip()
    if code and name:
        return f'{code} — {name}'
    return code or name or 'Course'


def _owned_session(session_id):
    session_obj = get_or_404_for_window(Session, session_id)
    teacher = resolve_caller_teacher(current_user)
    if not teacher or teacher.id != session_obj.teacher_id:
        flash('You can manage assignments only for your own courses.', 'danger')
        return None, None
    return session_obj, teacher


def _assignment_for_teacher(assignment_id):
    assignment = WrittenAssignment.query.get_or_404(assignment_id)
    session_obj, teacher = _owned_session(assignment.session_id)
    if not session_obj:
        return None, None, None
    return assignment, session_obj, teacher


def _parts_by_student(assignment):
    return {part.student_id: part for part in (assignment.parts or [])}


def _iso(value):
    if not value:
        return ''
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def _display_html(raw, part=None, *, highlight=False):
    clean = sanitize_outline_html(raw or '')
    if html_is_empty(clean):
        return '<p class="wa-empty">No writing yet.</p>'
    if not highlight or not part:
        return clean
    from utils.integrity_highlight import collect_ai_snippets, highlight_integrity_html, parse_snippet_list

    meta = part.parsed_meta()
    paste = parse_snippet_list(meta.get('paste_snippets'))
    ai = parse_snippet_list(meta.get('ai_snippets'))
    if not ai:
        style = meta.get('style') if isinstance(meta.get('style'), dict) else {}
        if style.get('flag'):
            ai = collect_ai_snippets(html_to_plain_text(clean))
    return highlight_integrity_html(clean, paste_snippets=paste, ai_snippets=ai)


def _hl_classes(part, integrity):
    if not part:
        return ''
    from utils.integrity_highlight import block_classes
    return block_classes(
        pasted=integrity.get('source') in ('pasted', 'mixed', 'burst'),
        ai=bool(integrity.get('style_flag')),
    )


def _json_snippets(data, key='paste_snippets', cap=12):
    raw = data.get(key) if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    from utils.integrity_highlight import parse_snippet_list
    return parse_snippet_list(raw, cap=cap)


def _mark_fields(assignment, part):
    out_of = int(assignment.marks_out_of or 10)
    if not part:
        return {
            'mark_line': f'Teacher mark: not recorded / {out_of}',
            'comment': '',
            'integrity_notes': [],
        }
    if part.teacher_mark is not None:
        mark_line = f'Teacher mark: {part.teacher_mark} / {out_of}'
    else:
        mark_line = f'Teacher mark: not recorded / {out_of}'
    return {
        'mark_line': mark_line,
        'comment': (part.teacher_comment or '').strip(),
        'integrity_notes': _integrity_notes(part),
    }


def _parse_evaluation(raw):
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _evaluation_map(assignment_id):
    try:
        rows = WrittenAssignmentEvaluation.query.filter_by(assignment_id=assignment_id).all()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Could not load assignment evaluations')
        return {}
    return {
        (row.target_type, row.target_id): _parse_evaluation(row.body_json)
        for row in rows
    }


def _row_for(student_id, student_name, part, group_name=None, evaluation=None):
    integrity = part_integrity(part) if part else {
        'focus_loss_count': 0,
        'screenshot_hint_count': 0,
        'paste_events_used': 0,
        'source': '',
        'source_label': None,
        'style_flag': False,
        'style_label': None,
        'style_score': None,
    }
    status = part.status if part else 'not_started'
    return {
        'key': re.sub(r'[^A-Za-z0-9_-]', '_', student_id or 'student'),
        'student_id': student_id,
        'student_name': student_name or student_id,
        'group_name': group_name,
        'html': _display_html(part.html_body if part else '', part, highlight=True),
        'hl_classes': _hl_classes(part, integrity),
        'word_count': int(part.word_count or 0) if part else 0,
        'status': status,
        'updated_at': _iso(part.updated_at) if part else '',
        'part_id': part.id if part else None,
        'teacher_mark': part.teacher_mark if part else None,
        'teacher_comment': part.teacher_comment if part else '',
        'updated_label': part.updated_at.strftime('%d %b %H:%M') if part and part.updated_at else '',
        'evaluation': evaluation,
        'integrity': integrity,
    }


def _monitor(assignment):
    parts = _parts_by_student(assignment)
    evaluations = _evaluation_map(assignment.id)
    if assignment.mode == WrittenAssignment.MODE_GROUP:
        blocks = []
        for group in assignment.groups or []:
            rows = []
            for member in group.members or []:
                part = parts.get(member.student_id)
                rows.append(_row_for(
                    member.student_id,
                    member.student_name,
                    part,
                    group.name,
                    evaluation=evaluations.get(('part', part.id)) if part else None,
                ))
            blocks.append({
                'id': group.id,
                'name': group.name,
                'teacher_mark': group.teacher_mark,
                'teacher_comment': group.teacher_comment or '',
                'evaluation': evaluations.get((WrittenAssignmentEvaluation.TARGET_GROUP, group.id)),
                'submitted_count': sum(1 for row in rows if row['status'] == 'submitted'),
                'rows': rows,
            })
        return blocks, []
    rows = []
    for stu in _roster(assignment.session_id):
        part = parts.get(stu.student_id)
        rows.append(_row_for(
            stu.student_id,
            stu.name,
            part,
            evaluation=evaluations.get(('part', part.id)) if part else None,
        ))
    return [], rows


def _group_sections(assignment, group):
    """All sections of one group in serial order."""
    if not group:
        return []
    return (
        WrittenAssignmentSection.query
        .join(WrittenAssignmentPart, WrittenAssignmentSection.part_id == WrittenAssignmentPart.id)
        .filter(
            WrittenAssignmentPart.assignment_id == assignment.id,
            WrittenAssignmentPart.group_id == group.id,
        )
        .order_by(WrittenAssignmentSection.sort_order.asc(), WrittenAssignmentSection.id.asc())
        .all()
    )


def _ensure_section(part):
    """Group parts always have at least one section; adopt pre-section writing."""
    if part.sections:
        return part.sections[0]
    section = WrittenAssignmentSection(
        assignment_id=part.assignment_id,
        part_id=part.id,
        html_body=part.html_body or '',
        word_count=int(part.word_count or 0),
        sort_order=_next_sort_order(part),
    )
    db.session.add(section)
    db.session.flush()
    return section

def _next_sort_order(part):
    highest = (
        db.session.query(db.func.max(WrittenAssignmentSection.sort_order))
        .join(WrittenAssignmentPart, WrittenAssignmentSection.part_id == WrittenAssignmentPart.id)
        .filter(
            WrittenAssignmentPart.assignment_id == part.assignment_id,
            WrittenAssignmentPart.group_id == part.group_id,
        )
        .scalar()
    )
    return int(highest or 0) + 1


def _section_payload(assignment, group, me=None):
    rows = []
    for index, section in enumerate(_group_sections(assignment, group), start=1):
        part = section.part
        rows.append({
            'id': section.id,
            'index': index,
            'title': section.display_title(index),
            'author_id': part.student_id,
            'author_name': part.student_name or part.student_id,
            'mine': me is not None and part.student_id == me,
            'word_count': int(section.word_count or 0),
            'html': sanitize_outline_html(section.html_body or ''),
            'updated_at': _iso(section.updated_at),
        })
    return rows


def _own_section(assignment, part, section_id):
    """The student's own section by id, or their first section when unspecified."""
    if section_id:
        for section in part.sections or []:
            if section.id == int(section_id):
                return section
        return None
    return _ensure_section(part)


def _move_section(assignment, group, section_id, direction):
    """Swap one section with its neighbor in the group serial. Returns an error or None."""
    sections = _group_sections(assignment, group)
    index = next((i for i, row in enumerate(sections) if row.id == section_id), None)
    if index is None:
        return 'Section not found.'
    other = index - 1 if direction == 'up' else index + 1
    if other < 0 or other >= len(sections):
        return None
    sections[index], sections[other] = sections[other], sections[index]
    # Rewrite the whole serial so legacy equal sort_orders cannot stick together.
    for position, row in enumerate(sections, start=1):
        row.sort_order = position
    db.session.commit()
    return None


def _ordered_own_sections(part):
    return sorted(part.sections or [], key=lambda row: (int(row.sort_order or 0), int(row.id or 0)))


def _own_section_payload(part):
    rows = []
    for index, section in enumerate(_ordered_own_sections(part), start=1):
        rows.append({
            'id': section.id,
            'index': index,
            'title': section.display_title(index),
            'word_count': int(section.word_count or 0),
        })
    return rows


def _move_own_section(part, section_id, direction):
    """Swap one of the student's sections with their previous/next own section."""
    own = _ordered_own_sections(part)
    index = next((i for i, row in enumerate(own) if row.id == section_id), None)
    if index is None:
        return 'Section not found.'
    other = index - 1 if direction == 'up' else index + 1
    if other < 0 or other >= len(own):
        return None
    own[index].sort_order, own[other].sort_order = own[other].sort_order, own[index].sort_order
    db.session.commit()
    return None


def _mentions_of(row):
    try:
        data = json.loads(row.mentions_json or '[]')
    except (TypeError, ValueError, AttributeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        key = str(item.get('key') or '').strip()[:80]
        name = str(item.get('name') or '').strip()[:120]
        if key and name:
            out.append({
                'key': key,
                'name': name,
                'role': str(item.get('role') or '')[:20],
            })
    return out[:20]


def _body_html(body, mentions):
    from markupsafe import escape
    text = str(body or '')
    names = sorted({item['name'] for item in mentions if item.get('name')}, key=len, reverse=True)
    if not names:
        return str(escape(text))
    pattern = '(' + '|'.join(re.escape('@' + name) for name in names) + ')'
    named = {'@' + name for name in names}
    parts = []
    for chunk in re.split(pattern, text):
        if chunk in named:
            parts.append(f'<span class="wa-mention">{escape(chunk)}</span>')
        else:
            parts.append(str(escape(chunk)))
    return ''.join(parts)


def _file_payload(row):
    return {
        'id': row.id,
        'name': row.original_name,
        'is_image': bool(row.is_image),
        'size': row.size_bytes,
        'url': url_for('written_assignment.discussion_file', file_id=row.id),
    }


def _post_payload(row, actor_key=None, vote_map=None, file_map=None):
    mentions = _mentions_of(row)
    likes = dislikes = 0
    my_vote = 0
    if vote_map is not None:
        for voter_key, value in vote_map.get(row.id, []):
            if value == WrittenAssignmentPostVote.LIKE:
                likes += 1
            elif value == WrittenAssignmentPostVote.DISLIKE:
                dislikes += 1
            if actor_key and voter_key == actor_key:
                my_vote = value
    else:
        for vote in row.votes or []:
            if vote.value == WrittenAssignmentPostVote.LIKE:
                likes += 1
            elif vote.value == WrittenAssignmentPostVote.DISLIKE:
                dislikes += 1
            if actor_key and vote.author_key == actor_key:
                my_vote = vote.value
    files = file_map.get(row.id, []) if file_map is not None else [_file_payload(item) for item in (row.files or [])]
    parent = row.parent
    return {
        'id': row.id,
        'parent_id': row.parent_id,
        'parent_name': (parent.author_name if parent else '') or '',
        'author_role': row.author_role,
        'author_key': row.author_key,
        'author_name': row.author_name,
        'body': row.body,
        'body_html': _body_html(row.body, mentions),
        'mentions': mentions,
        'likes': likes,
        'dislikes': dislikes,
        'my_vote': my_vote,
        'files': files,
        'created_at': _iso(row.created_at),
        'created_label': row.created_at.strftime('%d %b %H:%M') if row.created_at else '',
    }


def _discussion_people(assignment):
    people = []
    teacher = getattr(assignment, 'teacher', None)
    teacher_name = ((getattr(teacher, 'name', None) or 'Teacher').strip() or 'Teacher')[:120]
    people.append({
        'key': f'teacher:{assignment.teacher_id}',
        'name': teacher_name,
        'role': 'teacher',
    })
    seen = {people[0]['key']}
    for stu in _roster(assignment.session_id):
        key = f'student:{stu.student_id}'
        if key in seen:
            continue
        seen.add(key)
        name = (stu.name or stu.student_id or 'Student').strip()[:120]
        people.append({
            'key': key,
            'name': name or stu.student_id,
            'role': 'student',
            'student_id': stu.student_id,
        })
    return people


def _discussion_thread(assignment_id, actor_key=None):
    try:
        rows = (
            WrittenAssignmentPost.query.filter_by(assignment_id=assignment_id)
            .order_by(WrittenAssignmentPost.id.asc())
            .limit(200)
            .all()
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Could not load assignment discussion')
        return [], 'Discussion is unavailable until the discussion table is added.'
    ids = [row.id for row in rows]
    vote_map = {}
    file_map = {}
    if ids:
        try:
            for vote in WrittenAssignmentPostVote.query.filter(WrittenAssignmentPostVote.post_id.in_(ids)).all():
                vote_map.setdefault(vote.post_id, []).append((vote.author_key, vote.value))
        except Exception:
            db.session.rollback()
            vote_map = {}
        try:
            for item in WrittenAssignmentPostFile.query.filter(WrittenAssignmentPostFile.post_id.in_(ids)).all():
                file_map.setdefault(item.post_id, []).append(_file_payload(item))
        except Exception:
            db.session.rollback()
            file_map = {}
    return [_post_payload(row, actor_key=actor_key, vote_map=vote_map, file_map=file_map) for row in rows], None


def _discussion_actor(assignment):
    """Return (actor dict, error response) for the teacher who owns the course or an enrolled student."""
    teacher = resolve_caller_teacher(current_user)
    if teacher and teacher.id == assignment.teacher_id:
        session_obj, owned = _owned_session(assignment.session_id)
        if session_obj and owned:
            name = (getattr(current_user, 'full_name', None) or getattr(owned, 'name', None) or 'Teacher').strip()
            return {
                'role': 'teacher',
                'name': (name or 'Teacher')[:120],
                'key': f'teacher:{owned.id}',
            }, None
    from utils.dashboard_settings import require_student_dashboard_card
    blocked = require_student_dashboard_card('assignments')
    if blocked is not None:
        return None, blocked
    ctx, error = _student_context(assignment.id)
    if error:
        return None, _deny(error)
    student = ctx['class_student']
    name = (student.name or getattr(current_user, 'full_name', None) or student.student_id or 'Student').strip()
    return {
        'role': 'student',
        'name': name[:120],
        'key': f'student:{student.student_id}',
    }, None


def _clean_post_body(raw, allow_empty=False):
    text = re.sub(r'<[^>]+>', ' ', raw or '')
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        if allow_empty:
            return '', None
        return None, 'Write a message first.'
    if len(text) > 2000:
        return None, 'Keep the message under 2000 characters.'
    return text, None


def _discussion_view(assignment, actor_key=None):
    messages, error = _discussion_thread(assignment.id, actor_key=actor_key)
    return {
        'messages': messages,
        'discuss_error': error,
        'discuss_url': url_for('written_assignment.discussion', assignment_id=assignment.id),
        'discuss_people': _discussion_people(assignment),
        'discuss_me': actor_key or '',
    }


def _parse_parent_id(assignment_id, raw):
    if raw in (None, '', 0, '0'):
        return None, None
    try:
        parent_id = int(raw)
    except (TypeError, ValueError):
        return None, 'Invalid reply.'
    parent = WrittenAssignmentPost.query.filter_by(id=parent_id, assignment_id=assignment_id).first()
    if not parent:
        return None, 'The message you are replying to was not found.'
    # One-level replies: attach to the root post.
    return parent.parent_id or parent.id, None


def _parse_mention_keys(raw, people, author_key):
    keys = []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = []
    if not isinstance(raw, list):
        raw = []
    allowed = {person['key']: person for person in people}
    seen = set()
    for item in raw:
        key = str(item).strip() if not isinstance(item, dict) else str(item.get('key') or '').strip()
        if key in seen or key == author_key or key not in allowed:
            continue
        seen.add(key)
        keys.append(allowed[key])
    return keys[:20]


def _discussion_upload_dir(assignment_id):
    from utils.safe_files import upload_roots
    candidates = [
        os.path.join(current_app.root_path, 'instance', 'uploads'),
        os.path.join(current_app.root_path, 'uploads'),
    ]
    candidates.extend(upload_roots())
    last_error = None
    for base in candidates:
        folder = os.path.join(base, 'written_assignment', str(assignment_id))
        try:
            os.makedirs(folder, exist_ok=True)
            return folder
        except OSError as exc:
            last_error = exc
    raise last_error or OSError('Could not create discussion upload folder')


def _save_discussion_files(files, assignment_id, post_id):
    from utils.uploads import QA_PURPOSE, UploadError, validate_upload

    incoming = [item for item in (files or []) if item and getattr(item, 'filename', None)]
    if not incoming:
        return [], None
    if len(incoming) > _MAX_DISCUSSION_FILES:
        return [], f'Attach at most {_MAX_DISCUSSION_FILES} files.'
    saved = []
    folder = _discussion_upload_dir(assignment_id)
    for item in incoming:
        try:
            validated = validate_upload(item, QA_PURPOSE)
        except UploadError as exc:
            return [], exc.message
        stored = os.path.join(folder, f'{uuid4().hex}.{validated.ext}')
        with open(stored, 'wb') as handle:
            handle.write(validated.data)
        kind = (validated.kind or validated.ext or '').lower()
        if kind == 'jpeg':
            kind = 'jpg'
        saved.append(WrittenAssignmentPostFile(
            post_id=post_id,
            original_name=validated.original_name[:255],
            stored_path=stored,
            mime=kind,
            size_bytes=len(validated.data),
            is_image=kind in _IMAGE_KINDS,
        ))
    return saved, None


def _delete_post_files(files):
    for item in files or []:
        path = getattr(item, 'stored_path', None)
        if not path:
            continue
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


def _notify_discussion_people(assignment, actor, recipients, kind):
    if User is None or not recipients:
        return
    window_id = assignment.session.window_id if assignment.session else None
    link = url_for('written_assignment.student_write', assignment_id=assignment.id)
    title = (
        f"{actor['name']} mentioned you in Assignment: {(assignment.title or 'Assignment')[:60]}"
        if kind == 'mention'
        else f"{actor['name']} replied to you in Assignment: {(assignment.title or 'Assignment')[:60]}"
    )
    seen = set()
    for person in recipients:
        if person.get('role') != 'student':
            continue
        student_id = person.get('student_id') or (person['key'].split(':', 1)[1] if person['key'].startswith('student:') else '')
        if not student_id or student_id in seen:
            continue
        seen.add(student_id)
        user = User.query.filter_by(username=student_id).first()
        if not user:
            continue
        db.session.add(StudentNotification(
            user_id=user.id,
            type='assignment',
            title=title[:300],
            link_url=link,
            window_id=window_id,
        ))


def _save_evaluation(assignment_id, target_type, target_id, evaluation):
    row = WrittenAssignmentEvaluation.query.filter_by(
        assignment_id=assignment_id,
        target_type=target_type,
        target_id=target_id,
    ).first()
    payload = json.dumps(evaluation, ensure_ascii=False)
    if row is None:
        row = WrittenAssignmentEvaluation(
            assignment_id=assignment_id,
            target_type=target_type,
            target_id=target_id,
            body_json=payload,
        )
        db.session.add(row)
    else:
        row.body_json = payload
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Could not save assignment evaluation')
        raise


def _integrity_notes(part):
    info = part_integrity(part)
    notes = []
    if info.get('focus_loss_count'):
        notes.append(f"Focus left the page {info['focus_loss_count']} time(s).")
    if info.get('screenshot_hint_count'):
        notes.append(f"Screenshot hint {info['screenshot_hint_count']} time(s).")
    if info.get('paste_events_used'):
        notes.append(f"Paste events recorded: {info['paste_events_used']}.")
    if info.get('style_flag'):
        notes.append('Writing resembles common AI prose.')
    if info.get('source_label') and info.get('source') not in ('', 'typed'):
        notes.append(f"Input pattern: {info['source_label']}.")
    return notes


def _read_settings(*, allow_mode):
    title = (request.form.get('title') or '').strip()
    if not title:
        return None, 'Enter an assignment title.'
    if len(title) > 300:
        return None, 'Title must be 300 characters or fewer.'
    mode = WrittenAssignment.MODE_INDIVIDUAL
    if allow_mode:
        mode = (request.form.get('mode') or WrittenAssignment.MODE_INDIVIDUAL).strip().lower()
        if mode not in (WrittenAssignment.MODE_INDIVIDUAL, WrittenAssignment.MODE_GROUP):
            mode = WrittenAssignment.MODE_INDIVIDUAL
    instructions = sanitize_outline_html(request.form.get('instructions') or '')
    if len(instructions) > 100_000:
        return None, 'Instructions are too long.'
    deadline = None
    raw_deadline = (request.form.get('deadline') or '').strip()
    if raw_deadline:
        try:
            deadline = datetime.strptime(raw_deadline, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            return None, 'Deadline must be a valid date.'
    try:
        marks_out_of = int(request.form.get('marks_out_of') or 10)
    except (TypeError, ValueError):
        return None, 'Marks must be a whole number.'
    marks_out_of = max(1, min(100, marks_out_of))

    paste_mode = (request.form.get('paste_mode') or 'disabled').strip().lower()
    if paste_mode not in ('disabled', 'limited', 'unlimited'):
        paste_mode = 'disabled'
    paste_max_words = None
    paste_max_events = None
    if paste_mode == 'limited':
        try:
            words_raw = (request.form.get('paste_max_words') or '').strip()
            events_raw = (request.form.get('paste_max_events') or '').strip()
            if words_raw:
                paste_max_words = max(1, min(5000, int(words_raw)))
            if events_raw:
                paste_max_events = max(1, min(100, int(events_raw)))
        except (TypeError, ValueError):
            return None, 'Paste limits must be whole numbers.'
        if not paste_max_words and not paste_max_events:
            return None, 'Set a word limit or a paste-count limit.'
    return {
        'title': title,
        'mode': mode,
        'instructions': instructions,
        'deadline': deadline,
        'marks_out_of': marks_out_of,
        'paste_disabled': paste_mode == 'disabled',
        'paste_max_words': paste_max_words if paste_mode == 'limited' else None,
        'paste_max_events': paste_max_events if paste_mode == 'limited' else None,
        'is_active': request.form.get('is_active') == '1',
    }, None


def _apply_settings(assignment, payload, *, allow_mode):
    assignment.title = payload['title']
    assignment.instructions = payload['instructions']
    assignment.deadline = payload['deadline']
    assignment.marks_out_of = payload['marks_out_of']
    assignment.paste_disabled = payload['paste_disabled']
    assignment.paste_max_words = payload['paste_max_words']
    assignment.paste_max_events = payload['paste_max_events']
    assignment.is_active = payload['is_active']
    if allow_mode:
        assignment.mode = payload['mode']


def _notify(assignment, student_ids):
    if User is None or not student_ids:
        return
    link = url_for('written_assignment.student_write', assignment_id=assignment.id)
    window_id = assignment.session.window_id if assignment.session else None
    title = f"Assignment: {(assignment.title or 'New assignment')[:80]}"
    seen = set()
    for student_id in student_ids:
        if student_id in seen:
            continue
        seen.add(student_id)
        user = User.query.filter_by(username=student_id).first()
        if not user:
            continue
        note = StudentNotification(
            user_id=user.id,
            type='assignment',
            title=title,
            link_url=link,
            window_id=window_id,
        )
        db.session.add(note)


def _assigned_ids(assignment):
    if assignment.mode == WrittenAssignment.MODE_GROUP:
        ids = []
        for group in assignment.groups or []:
            for member in group.members or []:
                ids.append(member.student_id)
        return ids
    return [stu.student_id for stu in _roster(assignment.session_id)]


def _member_group(assignment, student_id):
    return (
        WrittenAssignmentGroup.query.join(WrittenAssignmentMember)
        .filter(
            WrittenAssignmentGroup.assignment_id == assignment.id,
            WrittenAssignmentMember.student_id == student_id,
        )
        .first()
    )


def _taken_student_ids(assignment):
    taken = set()
    for group in assignment.groups or []:
        for member in group.members or []:
            taken.add(member.student_id)
    return taken


def _student_context(assignment_id):
    assignment = WrittenAssignment.query.get(assignment_id)
    if not assignment:
        return None, (jsonify({'ok': False, 'error': 'Assignment not found.'}), 404)
    student_id = current_user.username
    enrolled = _student_sessions(student_id)
    class_student = enrolled.get(assignment.session_id)
    if not class_student:
        return None, (jsonify({'ok': False, 'error': 'You are not enrolled in this course.'}), 403)
    group = None
    if assignment.mode == WrittenAssignment.MODE_GROUP:
        group = _member_group(assignment, student_id)
    return {
        'assignment': assignment,
        'class_student': class_student,
        'group': group,
        'needs_group': assignment.mode == WrittenAssignment.MODE_GROUP and group is None,
    }, None


def _wants_json():
    if request.is_json:
        return True
    accept = request.headers.get('Accept') or ''
    return 'application/json' in accept or request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _deny(ctx_error):
    body, status = ctx_error
    if _wants_json():
        return body, status
    message = 'You cannot open this assignment.'
    try:
        payload = body.get_json(silent=True) or {}
        message = payload.get('error') or message
    except Exception:
        pass
    flash(message, 'danger')
    return redirect(url_for('written_assignment.student_list'))


def _get_or_create_part(assignment, student_id, student_name, group_id=None):
    part = WrittenAssignmentPart.query.filter_by(
        assignment_id=assignment.id,
        student_id=student_id,
    ).first()
    if part is None:
        part = WrittenAssignmentPart(
            assignment_id=assignment.id,
            group_id=group_id,
            student_id=student_id,
            student_name=student_name,
            html_body='',
            status=WrittenAssignmentPart.STATUS_DRAFT,
        )
        db.session.add(part)
        db.session.flush()
        return part
    if group_id and part.group_id != group_id:
        part.group_id = group_id
    if student_name and not part.student_name:
        part.student_name = student_name
    return part


def _lock_overdue(part, assignment):
    if not part or part.status != WrittenAssignmentPart.STATUS_DRAFT:
        return
    if part.can_edit(assignment):
        return
    if html_is_empty(part.html_body):
        return
    part.status = WrittenAssignmentPart.STATUS_SUBMITTED
    part.submitted_at = part.submitted_at or datetime.utcnow()


def _json_int(data, key, cap):
    try:
        return max(0, min(int(cap), int(data.get(key) or 0)))
    except (TypeError, ValueError):
        return 0


def _editor_source(html):
    return re.sub(r'</textarea', '&lt;/textarea', html or '', flags=re.I)


def _download_stem(*parts):
    raw = '_'.join(str(part).strip() for part in parts if part and str(part).strip())
    cleaned = secure_filename(raw) or 'assignment'
    return cleaned[:80]


def _meta_lines(assignment, session_obj):
    lines = [
        _course_label(session_obj),
        f"Mode: {'Group' if assignment.mode == WrittenAssignment.MODE_GROUP else 'Individual'}",
    ]
    if assignment.deadline_label():
        lines.append(f'Deadline: {assignment.deadline_label()}')
    lines.append(f'Marks out of {int(assignment.marks_out_of or 10)}')
    return lines


def _sections_for(assignment, scope, student_id=None, group_id=None, *, highlight=False, include_marks=False):
    parts = _parts_by_student(assignment)

    def decorate(block, part):
        if include_marks:
            block.update(_mark_fields(assignment, part))
        if highlight and part:
            block['hl_classes'] = _hl_classes(part, part_integrity(part))
        return block

    def one(sid, name, group_name=None):
        part = parts.get(sid)
        heading = f'{name} ({sid})'
        if group_name:
            heading = f'{group_name} — {heading}'
        status = (part.status if part else 'not started').replace('_', ' ')
        words = int(part.word_count or 0) if part else 0
        sub = f'{status} · {words} words'
        if include_marks and part and part.teacher_mark is not None:
            sub = f'{sub} · Mark {part.teacher_mark}/{int(assignment.marks_out_of or 10)}'
        return decorate({
            'heading': heading,
            'subheading': sub,
            'html': _display_html(part.html_body if part else '', part, highlight=highlight),
        }, part)

    def group_serial(group, only_student=None):
        """One export block per section, in the group's serial order."""
        rows = _group_sections(assignment, group)
        if not rows:
            members = group.members or []
            if only_student:
                members = [m for m in members if m.student_id == only_student]
            return [one(m.student_id, m.student_name or m.student_id, group.name) for m in members]
        blocks = []
        for index, section in enumerate(rows, start=1):
            part = section.part
            if only_student and part.student_id != only_student:
                continue
            author = part.student_name or part.student_id
            sub = f'{group.name} — {author} ({part.student_id}) · {int(section.word_count or 0)} words'
            if include_marks and part.teacher_mark is not None:
                sub = f'{sub} · Mark {part.teacher_mark}/{int(assignment.marks_out_of or 10)}'
            blocks.append(decorate({
                'heading': f'{index}. {section.display_title(index)}',
                'subheading': sub,
                'html': _display_html(section.html_body or '', part, highlight=highlight),
            }, part))
        return blocks

    if scope == 'student':
        if assignment.mode == WrittenAssignment.MODE_GROUP:
            group = _member_group(assignment, student_id)
            if group:
                return group_serial(group, only_student=student_id)
            part = parts.get(student_id)
            name = (part.student_name if part else None) or student_id
            return [one(student_id, name, None)]
        part = parts.get(student_id)
        name = (part.student_name if part else None) or student_id
        return [one(student_id, name)]

    if scope == 'group':
        group = WrittenAssignmentGroup.query.filter_by(id=group_id, assignment_id=assignment.id).first()
        if not group:
            return []
        return group_serial(group)

    sections = []
    if assignment.mode == WrittenAssignment.MODE_GROUP:
        for group in assignment.groups or []:
            sections.extend(group_serial(group))
        return sections
    for stu in _roster(assignment.session_id):
        sections.append(one(stu.student_id, stu.name or stu.student_id))
    return sections


def _send_download(assignment, session_obj, sections, fmt, stem, *, include_legend=False):
    if not sections:
        flash('Nothing to download yet.', 'warning')
        return None
    title = assignment.title
    meta = _meta_lines(assignment, session_obj)
    if fmt == 'docx':
        data = build_docx(title, meta, sections)
        mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ext = 'docx'
    elif fmt == 'pdf':
        data = build_pdf(title, meta, sections, include_legend=include_legend)
        if not data:
            flash('PDF export is unavailable on this server. Download the DOCX instead.', 'danger')
            return None
        mime = 'application/pdf'
        ext = 'pdf'
    else:
        abort(404)
    buf = BytesIO(data)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f'{stem}.{ext}', mimetype=mime)


def _parse_mark(raw, out_of):
    text = (raw or '').strip()
    if not text:
        return None, None
    try:
        value = float(text)
    except ValueError:
        return None, 'Enter a number for the mark.'
    if value < 0 or value > float(out_of or 10):
        return None, f'Mark must be between 0 and {int(out_of or 10)}.'
    return round(value, 2), None


@written_assignment_bp.route('/course/<int:session_id>', methods=['GET', 'POST'])
@login_required
def teacher_course(session_id):
    session_obj, teacher = _owned_session(session_id)
    if not session_obj:
        return redirect(url_for('class_management.index'))
    if request.method == 'POST':
        payload, error = _read_settings(allow_mode=True)
        if error:
            flash(error, 'danger')
            return redirect(url_for('written_assignment.teacher_course', session_id=session_id))
        payload['is_active'] = True
        assignment = WrittenAssignment(
            session_id=session_obj.id,
            teacher_id=teacher.id,
            title=payload['title'],
            instructions=payload['instructions'],
            mode=payload['mode'],
            deadline=payload['deadline'],
            marks_out_of=payload['marks_out_of'],
            paste_disabled=payload['paste_disabled'],
            paste_max_words=payload['paste_max_words'],
            paste_max_events=payload['paste_max_events'],
            is_active=True,
        )
        db.session.add(assignment)
        db.session.flush()
        if assignment.mode == WrittenAssignment.MODE_INDIVIDUAL:
            _notify(assignment, _assigned_ids(assignment))
        db.session.commit()
        flash('Assignment created.', 'success')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))

    assignments = (
        WrittenAssignment.query.filter_by(session_id=session_obj.id)
        .order_by(WrittenAssignment.created_at.desc())
        .all()
    )
    return render_template(
        'written_assignment/teacher_course.html',
        session=session_obj,
        course_label=_course_label(session_obj),
        assignments=assignments,
    )


@written_assignment_bp.route('/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def teacher_manage(assignment_id):
    assignment, session_obj, _teacher = _assignment_for_teacher(assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    if request.method == 'POST':
        payload, error = _read_settings(allow_mode=False)
        if error:
            flash(error, 'danger')
        else:
            _apply_settings(assignment, payload, allow_mode=False)
            db.session.commit()
            flash('Assignment updated.', 'success')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))

    blocks, rows = _monitor(assignment)
    taken = _taken_student_ids(assignment)
    unassigned = [stu for stu in _roster(session_obj.id) if stu.student_id not in taken]
    section_map = {}
    if assignment.mode == WrittenAssignment.MODE_GROUP:
        for group in assignment.groups or []:
            section_map[group.id] = _section_payload(assignment, group)
    return render_template(
        'written_assignment/teacher_manage.html',
        assignment=assignment,
        session=session_obj,
        course_label=_course_label(session_obj),
        blocks=blocks,
        rows=rows,
        section_map=section_map,
        unassigned=unassigned,
        instructions_html=Markup(sanitize_outline_html(assignment.instructions or '')),
        live_url=url_for('written_assignment.teacher_live', assignment_id=assignment.id),
        **_discussion_view(assignment, actor_key=f'teacher:{assignment.teacher_id}'),
    )


@written_assignment_bp.route('/<int:assignment_id>/live')
@login_required
def teacher_live(assignment_id):
    assignment, _session_obj, _teacher = _assignment_for_teacher(assignment_id)
    if not assignment:
        return jsonify({'ok': False, 'error': 'Not allowed.'}), 403
    blocks, rows = _monitor(assignment)
    return jsonify({'ok': True, 'open': assignment.is_open(), 'blocks': blocks, 'rows': rows})


@written_assignment_bp.route('/<int:assignment_id>/discussion', methods=['GET', 'POST'])
@login_required
def discussion(assignment_id):
    assignment = WrittenAssignment.query.get(assignment_id)
    if not assignment:
        return jsonify({'ok': False, 'error': 'Assignment not found.'}), 404
    actor, error = _discussion_actor(assignment)
    if error is not None:
        return error
    people = _discussion_people(assignment)
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        raw = data.get('body') if isinstance(data.get('body'), str) else request.form.get('body')
        files = request.files.getlist('files') if request.files else []
        has_files = any(item and getattr(item, 'filename', None) for item in files)
        body, body_error = _clean_post_body(raw, allow_empty=has_files)
        if body_error:
            return jsonify({'ok': False, 'error': body_error}), 400
        parent_raw = data.get('parent_id') if 'parent_id' in data else request.form.get('parent_id')
        parent_id, parent_error = _parse_parent_id(assignment.id, parent_raw)
        if parent_error:
            return jsonify({'ok': False, 'error': parent_error}), 400
        mention_raw = data.get('mentions') if 'mentions' in data else request.form.get('mentions')
        mentions = _parse_mention_keys(mention_raw, people, actor['key'])
        known = {item['key'] for item in mentions}
        for person in people:
            if person['key'] == actor['key'] or person['key'] in known:
                continue
            if ('@' + person['name']) in (body or ''):
                mentions.append(person)
                known.add(person['key'])
        if parent_id:
            parent = WrittenAssignmentPost.query.get(parent_id)
            if parent and parent.author_key != actor['key'] and parent.author_key not in {item['key'] for item in mentions}:
                mentions.append({
                    'key': parent.author_key,
                    'name': parent.author_name,
                    'role': parent.author_role,
                    'student_id': parent.author_key.split(':', 1)[1] if parent.author_key.startswith('student:') else '',
                })
        try:
            last = (
                WrittenAssignmentPost.query.filter_by(assignment_id=assignment.id, author_key=actor['key'])
                .order_by(WrittenAssignmentPost.id.desc())
                .first()
            )
        except Exception:
            db.session.rollback()
            return jsonify({'ok': False, 'error': 'Discussion is unavailable until the discussion table is added.'}), 503
        if last and last.created_at and (datetime.utcnow() - last.created_at).total_seconds() < 2:
            return jsonify({'ok': False, 'error': 'Wait a moment before posting again.'}), 429
        post = WrittenAssignmentPost(
            assignment_id=assignment.id,
            parent_id=parent_id,
            author_role=actor['role'],
            author_key=actor['key'],
            author_name=actor['name'],
            body=body,
            mentions_json=json.dumps(mentions) if mentions else None,
        )
        db.session.add(post)
        try:
            db.session.flush()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Could not save assignment discussion post')
            return jsonify({'ok': False, 'error': 'Discussion is unavailable until the discussion table is added.'}), 503
        stored = []
        if has_files:
            stored, file_error = _save_discussion_files(files, assignment.id, post.id)
            if file_error:
                db.session.rollback()
                return jsonify({'ok': False, 'error': file_error}), 400
            for item in stored:
                db.session.add(item)
        try:
            _notify_discussion_people(assignment, actor, mentions, 'mention' if not parent_id else 'reply')
            db.session.commit()
        except Exception:
            db.session.rollback()
            _delete_post_files(stored)
            current_app.logger.exception('Could not save assignment discussion post')
            return jsonify({'ok': False, 'error': 'Discussion is unavailable until the discussion table is added.'}), 503
    messages, thread_error = _discussion_thread(assignment.id, actor_key=actor['key'])
    if thread_error and request.method == 'GET':
        return jsonify({'ok': False, 'error': thread_error, 'messages': [], 'people': people, 'me': actor['key']}), 503
    return jsonify({'ok': True, 'messages': messages, 'people': people, 'me': actor['key']})


@written_assignment_bp.route('/<int:assignment_id>/discussion/<int:post_id>/vote', methods=['POST'])
@login_required
def discussion_vote(assignment_id, post_id):
    assignment = WrittenAssignment.query.get(assignment_id)
    if not assignment:
        return jsonify({'ok': False, 'error': 'Assignment not found.'}), 404
    actor, error = _discussion_actor(assignment)
    if error is not None:
        return error
    post = WrittenAssignmentPost.query.filter_by(id=post_id, assignment_id=assignment.id).first()
    if not post:
        return jsonify({'ok': False, 'error': 'Message not found.'}), 404
    data = request.get_json(silent=True) or {}
    raw = data.get('value') if 'value' in data else request.form.get('value')
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Pick like or dislike.'}), 400
    if value not in (WrittenAssignmentPostVote.LIKE, WrittenAssignmentPostVote.DISLIKE, 0):
        return jsonify({'ok': False, 'error': 'Pick like or dislike.'}), 400
    try:
        vote = WrittenAssignmentPostVote.query.filter_by(post_id=post.id, author_key=actor['key']).first()
        if value == 0 or (vote and vote.value == value):
            if vote:
                db.session.delete(vote)
        elif vote:
            vote.value = value
        else:
            db.session.add(WrittenAssignmentPostVote(
                post_id=post.id,
                author_key=actor['key'],
                value=value,
            ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Could not save discussion vote')
        return jsonify({'ok': False, 'error': 'Likes are unavailable until the vote table is added.'}), 503
    messages, _thread_error = _discussion_thread(assignment.id, actor_key=actor['key'])
    return jsonify({'ok': True, 'messages': messages})


@written_assignment_bp.route('/discussion-file/<int:file_id>')
@login_required
def discussion_file(file_id):
    from utils.safe_files import send_confined_file

    row = WrittenAssignmentPostFile.query.get_or_404(file_id)
    post = WrittenAssignmentPost.query.get_or_404(row.post_id)
    assignment = WrittenAssignment.query.get(post.assignment_id)
    if not assignment:
        abort(404)
    actor, error = _discussion_actor(assignment)
    if error is not None:
        return error
    force = request.args.get('download') == '1' or not row.is_image
    mime = None
    if row.is_image:
        kind = (row.mime or '').lower()
        mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}.get(kind, 'image/jpeg')
    return send_confined_file(
        row.stored_path,
        mimetype=mime,
        download_name=row.original_name,
        as_attachment=force,
        force_attachment=force,
    )


@written_assignment_bp.route('/<int:assignment_id>/groups', methods=['POST'])
@login_required
def create_group(assignment_id):
    assignment, session_obj, _teacher = _assignment_for_teacher(assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    if assignment.mode != WrittenAssignment.MODE_GROUP:
        flash('This assignment is individual.', 'warning')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    name = (request.form.get('group_name') or '').strip()[:120]
    roster = {stu.student_id: stu for stu in _roster(session_obj.id)}
    taken = _taken_student_ids(assignment)
    chosen = []
    for sid in request.form.getlist('student_ids'):
        sid = (sid or '').strip()
        if sid in roster and sid not in taken and sid not in chosen:
            chosen.append(sid)
    if len(chosen) < 2:
        flash('A group needs at least two students who are not already in a group.', 'danger')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    if not name:
        name = f'Group {len(assignment.groups or []) + 1}'
    group = WrittenAssignmentGroup(assignment_id=assignment.id, name=name)
    db.session.add(group)
    db.session.flush()
    for sid in chosen:
        stu = roster[sid]
        db.session.add(WrittenAssignmentMember(
            group_id=group.id,
            student_id=sid,
            student_name=(stu.name or sid)[:100],
        ))
    _notify(assignment, chosen)
    db.session.commit()
    flash(f'{name} created.', 'success')
    return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))


@written_assignment_bp.route('/groups/<int:group_id>/members', methods=['POST'])
@login_required
def add_member(group_id):
    group = WrittenAssignmentGroup.query.get_or_404(group_id)
    assignment, session_obj, _teacher = _assignment_for_teacher(group.assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    sid = (request.form.get('student_id') or '').strip()
    roster = {stu.student_id: stu for stu in _roster(session_obj.id)}
    if sid not in roster or sid in _taken_student_ids(assignment):
        flash('That student cannot be added to this group.', 'danger')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    stu = roster[sid]
    db.session.add(WrittenAssignmentMember(
        group_id=group.id,
        student_id=sid,
        student_name=(stu.name or sid)[:100],
    ))
    part = WrittenAssignmentPart.query.filter_by(assignment_id=assignment.id, student_id=sid).first()
    if part:
        part.group_id = group.id
    _notify(assignment, [sid])
    db.session.commit()
    flash('Student added to the group.', 'success')
    return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))


@written_assignment_bp.route('/groups/<int:group_id>/members/remove', methods=['POST'])
@login_required
def remove_member(group_id):
    group = WrittenAssignmentGroup.query.get_or_404(group_id)
    assignment, _session_obj, _teacher = _assignment_for_teacher(group.assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    sid = (request.form.get('student_id') or '').strip()
    member = WrittenAssignmentMember.query.filter_by(group_id=group.id, student_id=sid).first()
    if not member:
        flash('That student is not in this group.', 'warning')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    if WrittenAssignmentMember.query.filter_by(group_id=group.id).count() <= 2:
        flash('A group must keep at least two students. Delete the group instead.', 'danger')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    WrittenAssignmentPart.query.filter_by(assignment_id=assignment.id, student_id=sid).delete()
    db.session.delete(member)
    db.session.commit()
    flash('Student removed. Their writing for this assignment was deleted.', 'success')
    return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))


@written_assignment_bp.route('/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    group = WrittenAssignmentGroup.query.get_or_404(group_id)
    assignment, _session_obj, _teacher = _assignment_for_teacher(group.assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    member_ids = [member.student_id for member in group.members]
    if member_ids:
        WrittenAssignmentPart.query.filter(
            WrittenAssignmentPart.assignment_id == assignment.id,
            WrittenAssignmentPart.student_id.in_(member_ids),
        ).delete(synchronize_session=False)
    db.session.delete(group)
    db.session.commit()
    flash('Group deleted.', 'success')
    return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))


@written_assignment_bp.route('/groups/<int:group_id>/mark', methods=['POST'])
@login_required
def mark_group(group_id):
    group = WrittenAssignmentGroup.query.get_or_404(group_id)
    assignment, _session_obj, _teacher = _assignment_for_teacher(group.assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    member_ids = [member.student_id for member in (group.members or [])]
    submitted = 0
    if member_ids:
        submitted = WrittenAssignmentPart.query.filter(
            WrittenAssignmentPart.assignment_id == assignment.id,
            WrittenAssignmentPart.student_id.in_(member_ids),
            WrittenAssignmentPart.status == WrittenAssignmentPart.STATUS_SUBMITTED,
        ).count()
    if not submitted:
        flash('Evaluate this group after at least one member submits.', 'warning')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    mark, error = _parse_mark(request.form.get('teacher_mark'), assignment.marks_out_of)
    if error:
        flash(error, 'danger')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    group.teacher_mark = mark
    group.teacher_comment = (request.form.get('teacher_comment') or '').strip()[:4000]
    db.session.commit()
    flash('Group mark saved.', 'success')
    return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))


@written_assignment_bp.route('/<int:assignment_id>/delete', methods=['POST'])
@login_required
def delete_assignment(assignment_id):
    assignment, session_obj, _teacher = _assignment_for_teacher(assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    session_id = session_obj.id
    try:
        posts = WrittenAssignmentPost.query.filter_by(assignment_id=assignment.id).all()
        for post in posts:
            _delete_post_files(post.files)
    except Exception:
        db.session.rollback()
    for model in (WrittenAssignmentPost, WrittenAssignmentEvaluation):
        try:
            model.query.filter_by(assignment_id=assignment.id).delete(synchronize_session=False)
            db.session.flush()
        except Exception:
            db.session.rollback()
            assignment = WrittenAssignment.query.get(assignment_id)
            if not assignment:
                flash('Assignment deleted.', 'success')
                return redirect(url_for('written_assignment.teacher_course', session_id=session_id))
    db.session.delete(assignment)
    db.session.commit()
    flash('Assignment deleted.', 'success')
    return redirect(url_for('written_assignment.teacher_course', session_id=session_id))


@written_assignment_bp.route('/parts/<int:part_id>/mark', methods=['POST'])
@login_required
def mark_part(part_id):
    part = WrittenAssignmentPart.query.get_or_404(part_id)
    assignment, _session_obj, _teacher = _assignment_for_teacher(part.assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    if part.status != WrittenAssignmentPart.STATUS_SUBMITTED:
        flash('You can read the draft. Mark this student after they submit.', 'warning')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    mark, error = _parse_mark(request.form.get('teacher_mark'), assignment.marks_out_of)
    if error:
        flash(error, 'danger')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    part.teacher_mark = mark
    part.teacher_comment = (request.form.get('teacher_comment') or '').strip()[:4000]
    db.session.commit()
    who = part.student_name or part.student_id
    flash(f'Mark saved for {who}.', 'success')
    return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))


def _assignment_mark_map(assignment):
    """student_id -> final mark. Group members without their own mark fall back to the group mark."""
    parts = _parts_by_student(assignment)
    marks = {}
    if assignment.mode == WrittenAssignment.MODE_GROUP:
        for group in assignment.groups or []:
            for member in group.members or []:
                part = parts.get(member.student_id)
                value = part.teacher_mark if part and part.teacher_mark is not None else group.teacher_mark
                if value is not None:
                    marks[member.student_id] = float(value)
    else:
        for sid, part in parts.items():
            if part.teacher_mark is not None:
                marks[sid] = float(part.teacher_mark)
    return marks


def _assessment_slot_max(session_obj, field):
    """Highest mark the chosen Class Management column will accept."""
    try:
        from utils.academic_rules import assessment_cfg
        cfg = assessment_cfg()
        slot = float(cfg.get('slot_max') or 10)
        if field.startswith('assessment') and session_obj.course_type == 'theory':
            from blueprints.class_management.routes import (
                _effective_assessment_mode,
                _external_assessment_mark_max,
            )
            return float(_external_assessment_mark_max(_effective_assessment_mode(session_obj)))
        return slot
    except Exception:
        return 10.0


def _scale_assignment_mark(value, assignment, slot_max):
    """Map an assignment mark onto the assessment column, still in half-steps."""
    from decimal import Decimal, ROUND_HALF_UP
    out_of = Decimal(str(int(assignment.marks_out_of or 10)))
    cap = Decimal(str(slot_max or 10))
    if out_of <= 0:
        out_of = Decimal('10')
    if cap <= 0:
        cap = Decimal('10')
    raw = Decimal(str(value)) * cap / out_of
    halves = (raw * 2).to_integral_value(rounding=ROUND_HALF_UP)
    return float(max(Decimal('0'), min(cap, halves / 2)))


def _assessment_target_fields(session_obj):
    """(field, label) assessment columns this teacher may fill for the course type."""
    if session_obj.course_type == 'theory':
        indices = {1, 2, 3, 4}
        try:
            from blueprints.class_management.routes import _get_editable_assessment_indices
            indices = _get_editable_assessment_indices(session_obj)
        except Exception:
            pass
        return [(f'assessment{i}', f'Assessment {i}') for i in sorted(indices)]
    if session_obj.course_type == 'sessional' and getattr(session_obj, 'category', None) == 'ug':
        return [('sessional_report', 'Sessional Report'), ('sessional_viva', 'Sessional Viva')]
    return []


@written_assignment_bp.route('/<int:assignment_id>/fetch-to-assessment', methods=['POST'])
@login_required
def fetch_to_assessment(assignment_id):
    """Copy this assignment's marks into one empty assessment column of the course."""
    assignment, session_obj, _teacher = _assignment_for_teacher(assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    back = redirect(url_for('class_management.assessment', session_id=session_obj.id))
    target = (request.form.get('target') or '').strip()
    valid = dict(_assessment_target_fields(session_obj))
    if target not in valid:
        flash('Pick a valid assessment column.', 'danger')
        return back
    occupied = ClassStudent.query.filter(
        ClassStudent.session_id == session_obj.id,
        getattr(ClassStudent, target).isnot(None),
    ).count()
    if occupied:
        flash(f'{valid[target]} already has marks. Marks can only be fetched into an empty column.', 'warning')
        return back
    marks = _assignment_mark_map(assignment)
    if not marks:
        flash('This assignment has no marks yet. Mark the submissions first.', 'warning')
        return back
    slot_max = _assessment_slot_max(session_obj, target)
    updated = 0
    skipped = 0
    for student in ClassStudent.query.filter_by(session_id=session_obj.id).all():
        value = marks.get(student.student_id)
        if value is None:
            continue
        if getattr(student, target, None) is not None:
            skipped += 1
            continue
        setattr(student, target, _scale_assignment_mark(value, assignment, slot_max))
        updated += 1
    if not updated:
        db.session.rollback()
        flash('No enrolled student matched the assignment marks.', 'warning')
        return back
    if session_obj.course_type == 'theory':
        try:
            from blueprints.class_management.routes import _recalculate_assessment_totals
            _recalculate_assessment_totals(session_obj)
        except Exception:
            current_app.logger.exception('Could not recalculate assessment totals after fetch')
    db.session.commit()
    flash(
        f'Fetched {updated} mark(s) from "{assignment.title}" into {valid[target]} '
        f'(out of {assignment.marks_out_of}).',
        'success',
    )
    return back


def _run_writing_evaluation(assignment, session_obj, pieces, notes):
    from utils.rate_limit import AI_USER, reject_if_user_limited
    limited = reject_if_user_limited(
        'ai.assignment',
        AI_USER,
        json_message='অনেকবার চেষ্টা করা হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।',
    )
    if limited:
        return None, limited
    from utils.ai.assignment_eval import evaluate_writing
    from utils.public_errors import client_message
    from utils.ai.client import user_facing_generation_error
    plain_instructions = html_to_plain_text(assignment.instructions or '')
    try:
        return evaluate_writing(
            title=assignment.title,
            instructions=plain_instructions,
            course_label=_course_label(session_obj),
            marks_out_of=assignment.marks_out_of,
            pieces=pieces,
            integrity_notes=notes,
        ), None
    except ValueError as exc:
        return None, (jsonify({'success': False, 'message': client_message(exc)}), 400)
    except Exception as exc:
        current_app.logger.error('Written assignment evaluation failed: %s', exc, exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        return None, (jsonify({'success': False, 'message': user_facing_generation_error(exc)}), 500)


@written_assignment_bp.route('/parts/<int:part_id>/evaluate', methods=['POST'])
@login_required
def evaluate_part(part_id):
    part = WrittenAssignmentPart.query.get_or_404(part_id)
    assignment, session_obj, _teacher = _assignment_for_teacher(part.assignment_id)
    if not assignment:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    if assignment.mode == WrittenAssignment.MODE_GROUP:
        return jsonify({'success': False, 'message': 'Evaluate the group, not one member.'}), 400
    if part.status != WrittenAssignmentPart.STATUS_SUBMITTED:
        return jsonify({'success': False, 'message': 'Evaluate after the student submits.'}), 403
    if html_is_empty(part.html_body):
        return jsonify({'success': False, 'message': 'There is no writing to evaluate.'}), 400
    assignment_id = assignment.id
    marks_target = part.id
    pieces = [{
        'author': part.student_name or part.student_id,
        'text': html_to_plain_text(part.html_body or ''),
    }]
    notes = _integrity_notes(part)
    evaluation, error = _run_writing_evaluation(assignment, session_obj, pieces, notes)
    if error is not None:
        return error
    try:
        _save_evaluation(assignment_id, WrittenAssignmentEvaluation.TARGET_PART, marks_target, evaluation)
    except Exception:
        return jsonify({
            'success': False,
            'message': 'Evaluation could not be saved. Add the written_assignment_evaluation table.',
        }), 503
    return jsonify({'success': True})


@written_assignment_bp.route('/groups/<int:group_id>/evaluate', methods=['POST'])
@login_required
def evaluate_group(group_id):
    group = WrittenAssignmentGroup.query.get_or_404(group_id)
    assignment, session_obj, _teacher = _assignment_for_teacher(group.assignment_id)
    if not assignment:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    pieces = []
    notes = []
    noted_parts = set()
    ordered = _group_sections(assignment, group)
    if ordered:
        # Feed the AI the document in its serial order, one piece per section.
        for index, section in enumerate(ordered, start=1):
            part = section.part
            if part.status != WrittenAssignmentPart.STATUS_SUBMITTED:
                continue
            if html_is_empty(section.html_body):
                continue
            author = part.student_name or part.student_id
            pieces.append({
                'author': f'{index}. {section.display_title(index)} — {author}',
                'text': html_to_plain_text(section.html_body or ''),
            })
            if part.id not in noted_parts:
                noted_parts.add(part.id)
                notes.extend(_integrity_notes(part))
    else:
        parts = {
            part.student_id: part
            for part in WrittenAssignmentPart.query.filter_by(assignment_id=assignment.id).all()
        }
        for member in group.members or []:
            part = parts.get(member.student_id)
            if not part or part.status != WrittenAssignmentPart.STATUS_SUBMITTED:
                continue
            if html_is_empty(part.html_body):
                continue
            pieces.append({
                'author': member.student_name or member.student_id,
                'text': html_to_plain_text(part.html_body or ''),
            })
            notes.extend(_integrity_notes(part))
    if not pieces:
        return jsonify({'success': False, 'message': 'Evaluate after at least one member submits.'}), 403
    assignment_id = assignment.id
    target_id = group.id
    evaluation, error = _run_writing_evaluation(assignment, session_obj, pieces, notes)
    if error is not None:
        return error
    try:
        _save_evaluation(assignment_id, WrittenAssignmentEvaluation.TARGET_GROUP, target_id, evaluation)
    except Exception:
        return jsonify({
            'success': False,
            'message': 'Evaluation could not be saved. Add the written_assignment_evaluation table.',
        }), 503
    return jsonify({'success': True})


@written_assignment_bp.route('/parts/<int:part_id>/reopen', methods=['POST'])
@login_required
def reopen_part(part_id):
    part = WrittenAssignmentPart.query.get_or_404(part_id)
    assignment, _session_obj, _teacher = _assignment_for_teacher(part.assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    part.status = WrittenAssignmentPart.STATUS_DRAFT
    part.deadline_exempt = True
    part.submitted_at = None
    db.session.commit()
    flash(f'{part.student_name or part.student_id} can edit again.', 'success')
    return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))


@written_assignment_bp.route('/<int:assignment_id>/download/<fmt>')
@login_required
def teacher_download(assignment_id, fmt):
    assignment, session_obj, _teacher = _assignment_for_teacher(assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    scope = (request.args.get('scope') or 'all').strip().lower()
    student_id = (request.args.get('student_id') or '').strip() or None
    group_id = request.args.get('group_id', type=int)
    marked = (request.args.get('marked') or '').strip().lower() in ('1', 'true', 'yes')
    if scope not in ('all', 'student', 'group'):
        scope = 'all'
    sections = _sections_for(
        assignment,
        scope,
        student_id=student_id,
        group_id=group_id,
        highlight=True,
        include_marks=marked,
    )
    who = student_id or (f'group{group_id}' if group_id else 'all')
    stem = _download_stem(session_obj.course_code, assignment.title, who, 'marked' if marked else '')
    response = _send_download(
        assignment, session_obj, sections, fmt, stem, include_legend=(fmt == 'pdf'),
    )
    if response is None:
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    return response


@written_assignment_bp.route('/student')
@login_required
def student_list():
    from utils.dashboard_settings import require_student_dashboard_card
    blocked = require_student_dashboard_card('assignments')
    if blocked:
        return blocked
    student_id = current_user.username
    enrolled = _student_sessions(student_id)
    cards = []
    if enrolled:
        rows = (
            WrittenAssignment.query.filter(WrittenAssignment.session_id.in_(enrolled.keys()))
            .order_by(WrittenAssignment.created_at.desc())
            .all()
        )
        for assignment in rows:
            group = None
            part = WrittenAssignmentPart.query.filter_by(
                assignment_id=assignment.id,
                student_id=student_id,
            ).first()
            needs_group = False
            if assignment.mode == WrittenAssignment.MODE_GROUP:
                group = _member_group(assignment, student_id)
                needs_group = group is None
            cards.append({
                'assignment': assignment,
                'session': assignment.session,
                'group': group,
                'part': part,
                'needs_group': needs_group,
                'course_label': _course_label(assignment.session),
            })
    return render_template('written_assignment/student_list.html', cards=cards)


@written_assignment_bp.route('/student/<int:assignment_id>')
@login_required
def student_write(assignment_id):
    from utils.dashboard_settings import require_student_dashboard_card
    blocked = require_student_dashboard_card('assignments')
    if blocked:
        return blocked
    ctx, error = _student_context(assignment_id)
    if error:
        return _deny(error)
    assignment = ctx['assignment']
    class_student = ctx['class_student']
    group = ctx['group']
    part = None
    active_section = None
    own_sections = []
    group_doc = []
    if not ctx['needs_group']:
        part = _get_or_create_part(
            assignment,
            class_student.student_id,
            class_student.name or current_user.full_name,
            group.id if group else None,
        )
        _lock_overdue(part, assignment)
        if group:
            active_section = _ensure_section(part)
            wanted = request.args.get('section', type=int)
            if wanted:
                for section in part.sections:
                    if section.id == wanted:
                        active_section = section
                        break
        db.session.commit()
        if group:
            own_sections = _ordered_own_sections(part)
            group_doc = _section_payload(assignment, group, me=class_student.student_id)
    warning = student_writing_warning(part, assignment) if part else None
    config = {
        'canEdit': bool(part and part.can_edit(assignment)),
        'pasteMode': assignment.paste_mode(),
        'pasteMaxWords': assignment.paste_max_words,
        'pasteMaxEvents': assignment.paste_max_events,
        'pasteEventsUsed': int(part.paste_events_used or 0) if part else 0,
        'saveUrl': url_for('written_assignment.student_save', assignment_id=assignment.id),
        'submitUrl': url_for('written_assignment.student_submit', assignment_id=assignment.id),
        'unsubmitUrl': url_for('written_assignment.student_unsubmit', assignment_id=assignment.id),
        'allowUnsubmit': bool(assignment.is_open()),
        'integrityUrl': url_for('written_assignment.student_integrity', assignment_id=assignment.id),
        'peersUrl': url_for('written_assignment.student_peers', assignment_id=assignment.id) if group else '',
        'moveUrl': url_for('written_assignment.student_move_section', assignment_id=assignment.id) if group else '',
        'kalpurushUrl': url_for('static', filename='Fonts/kalpurush.ttf'),
        'warningText': SOCRATES_AI_USE_WARNING,
        'groupMode': assignment.mode == WrittenAssignment.MODE_GROUP,
        'sectionId': active_section.id if active_section else None,
    }
    editor_body = ''
    if part:
        editor_body = active_section.html_body if active_section else part.html_body
    return render_template(
        'written_assignment/student_write.html',
        assignment=assignment,
        session=assignment.session,
        course_label=_course_label(assignment.session),
        group=group,
        part=part,
        own_sections=own_sections,
        active_section=active_section,
        group_doc=group_doc,
        needs_group=ctx['needs_group'],
        can_edit=config['canEdit'],
        can_unsubmit=bool(
            part
            and part.status == WrittenAssignmentPart.STATUS_SUBMITTED
            and assignment.is_open()
        ),
        warning=warning,
        instructions_html=Markup(sanitize_outline_html(assignment.instructions or '')),
        editor_html=Markup(_editor_source(editor_body or '')),
        editor_config=config,
        docx_url=url_for('written_assignment.student_download', assignment_id=assignment.id, fmt='docx'),
        pdf_url=url_for('written_assignment.student_download', assignment_id=assignment.id, fmt='pdf'),
        **_discussion_view(assignment, actor_key=f'student:{class_student.student_id}'),
    )


@written_assignment_bp.route('/student/<int:assignment_id>/save', methods=['POST'])
@login_required
def student_save(assignment_id):
    ctx, error = _student_context(assignment_id)
    if error:
        return error
    if ctx['needs_group']:
        return jsonify({'ok': False, 'error': 'You are not in a group for this assignment yet.'}), 403
    assignment = ctx['assignment']
    class_student = ctx['class_student']
    group = ctx['group']
    part = _get_or_create_part(
        assignment,
        class_student.student_id,
        class_student.name or current_user.full_name,
        group.id if group else None,
    )
    _lock_overdue(part, assignment)
    if not part.can_edit(assignment):
        db.session.commit()
        return jsonify({
            'ok': False,
            'error': 'This assignment is closed or already submitted.',
            'html': part.html_body or '',
            'status': part.status,
        }), 403
    data = request.get_json(silent=True) or {}
    raw_html = data.get('html') if isinstance(data.get('html'), str) else ''
    if len(raw_html) > _MAX_HTML:
        return jsonify({'ok': False, 'error': 'The assignment is too long to save.'}), 400
    clean = sanitize_outline_html(raw_html)
    plain = html_to_plain_text(clean)
    new_words = plain_word_count(plain)
    section = None
    total_after = new_words
    if group:
        section = _own_section(assignment, part, data.get('section_id'))
        if section is None:
            return jsonify({'ok': False, 'error': 'Section not found.'}), 404
        total_after = int(part.word_count or 0) - int(section.word_count or 0) + new_words
    paste_events = _json_int(data, 'paste_events', 20)
    pasted_chars = _json_int(data, 'pasted_chars', 20000)
    paste_words = _json_int(data, 'paste_words', 5000)
    paste_error = evaluate_paste(
        assignment,
        part,
        pasted_chars=pasted_chars,
        paste_events=paste_events,
        paste_words=paste_words,
        old_words=int(part.word_count or 0),
        new_words=total_after,
    )
    if paste_error:
        db.session.commit()
        return jsonify({
            'ok': False,
            'code': 'paste_blocked',
            'error': paste_error,
            'html': (section.html_body if section else part.html_body) or '',
            'warning': SOCRATES_AI_USE_WARNING,
        }), 400
    if section:
        section.html_body = clean
        section.word_count = new_words
        rebuild_part_from_sections(part)
        plain = html_to_plain_text(part.html_body or '')
    else:
        part.html_body = clean
        part.word_count = new_words
    part.student_name = (class_student.name or part.student_name or class_student.student_id)[:100]
    record_composition(
        part,
        plain,
        typed_chars=_json_int(data, 'typed_chars', 20000),
        pasted_chars=pasted_chars,
        paste_events=paste_events,
        compose_ms=_json_int(data, 'compose_ms', 1_800_000),
        paste_snippets=_json_snippets(data),
    )
    db.session.commit()
    warning = student_writing_warning(part, assignment)
    return jsonify({
        'ok': True,
        'word_count': part.word_count,
        'section_words': int(section.word_count or 0) if section else part.word_count,
        'status': part.status,
        'updated_at': _iso(part.updated_at),
        'warning': warning,
        'paste_events_used': int(part.paste_events_used or 0),
        'style_flag': part_integrity(part)['style_flag'],
    })


@written_assignment_bp.route('/student/<int:assignment_id>/sections', methods=['POST'])
@login_required
def student_add_section(assignment_id):
    ctx, error = _student_context(assignment_id)
    if error:
        return _deny(error)
    if ctx['needs_group'] or not ctx['group']:
        flash('Sections are available once you are in a group.', 'warning')
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id))
    assignment = ctx['assignment']
    class_student = ctx['class_student']
    part = _get_or_create_part(assignment, class_student.student_id, class_student.name, ctx['group'].id)
    _lock_overdue(part, assignment)
    if not part.can_edit(assignment):
        db.session.commit()
        flash('This assignment is closed or already submitted.', 'warning')
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id))
    if len(part.sections or []) >= 20:
        flash('You already have 20 sections.', 'warning')
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id))
    _ensure_section(part)
    title = (request.form.get('title') or '').strip()[:200]
    section = WrittenAssignmentSection(
        assignment_id=assignment.id,
        part_id=part.id,
        title=title or None,
        html_body='',
        word_count=0,
        sort_order=_next_sort_order(part),
    )
    db.session.add(section)
    db.session.commit()
    return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id, section=section.id))


@written_assignment_bp.route('/student/<int:assignment_id>/sections/<int:section_id>/rename', methods=['POST'])
@login_required
def student_rename_section(assignment_id, section_id):
    ctx, error = _student_context(assignment_id)
    if error:
        return _deny(error)
    assignment = ctx['assignment']
    class_student = ctx['class_student']
    part = _get_or_create_part(assignment, class_student.student_id, class_student.name, ctx['group'].id if ctx['group'] else None)
    section = _own_section(assignment, part, section_id)
    if section is None:
        flash('Section not found.', 'danger')
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id))
    if not part.can_edit(assignment):
        flash('This assignment is closed or already submitted.', 'warning')
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id, section=section.id))
    section.title = (request.form.get('title') or '').strip()[:200] or None
    rebuild_part_from_sections(part)
    db.session.commit()
    return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id, section=section.id))


@written_assignment_bp.route('/student/<int:assignment_id>/sections/<int:section_id>/delete', methods=['POST'])
@login_required
def student_delete_section(assignment_id, section_id):
    ctx, error = _student_context(assignment_id)
    if error:
        return _deny(error)
    assignment = ctx['assignment']
    class_student = ctx['class_student']
    part = _get_or_create_part(assignment, class_student.student_id, class_student.name, ctx['group'].id if ctx['group'] else None)
    section = _own_section(assignment, part, section_id)
    if section is None:
        flash('Section not found.', 'danger')
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id))
    if not part.can_edit(assignment):
        flash('This assignment is closed or already submitted.', 'warning')
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id))
    if len(part.sections or []) <= 1:
        flash('Keep at least one section. Clear the text instead.', 'warning')
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id, section=section.id))
    db.session.delete(section)
    db.session.flush()
    rebuild_part_from_sections(part)
    db.session.commit()
    flash('Section deleted.', 'success')
    return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id))


@written_assignment_bp.route('/student/<int:assignment_id>/sections/move', methods=['POST'])
@login_required
def student_move_section(assignment_id):
    ctx, error = _student_context(assignment_id)
    if error:
        return error
    if ctx['needs_group'] or not ctx['group']:
        return jsonify({'ok': False, 'error': 'Sections are available once you are in a group.'}), 403
    assignment = ctx['assignment']
    if not assignment.is_open():
        return jsonify({'ok': False, 'error': 'The assignment is closed. Ask your teacher to reorder.'}), 403
    data = request.get_json(silent=True) or {}
    direction = 'up' if (data.get('direction') or request.form.get('direction')) == 'up' else 'down'
    section_id = data.get('section_id') or request.form.get('section_id', type=int)
    try:
        section_id = int(section_id)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Section not found.'}), 404
    class_student = ctx['class_student']
    part = _get_or_create_part(
        assignment,
        class_student.student_id,
        class_student.name or current_user.full_name,
        ctx['group'].id,
    )
    section = _own_section(assignment, part, section_id)
    if section is None:
        return jsonify({'ok': False, 'error': 'You can only rearrange your own sections.'}), 403
    scope = str(data.get('scope') or request.form.get('scope') or 'group').strip().lower()
    if scope == 'own':
        move_error = _move_own_section(part, section.id, direction)
    else:
        move_error = _move_section(assignment, ctx['group'], section.id, direction)
    if move_error:
        return jsonify({'ok': False, 'error': move_error}), 404
    return jsonify({
        'ok': True,
        'sections': _section_payload(assignment, ctx['group'], me=class_student.student_id),
        'own_sections': _own_section_payload(part),
    })


@written_assignment_bp.route('/sections/<int:section_id>/move', methods=['POST'])
@login_required
def teacher_move_section(section_id):
    section = WrittenAssignmentSection.query.get_or_404(section_id)
    part = WrittenAssignmentPart.query.get_or_404(section.part_id)
    assignment, _session_obj, _teacher = _assignment_for_teacher(part.assignment_id)
    if not assignment:
        return redirect(url_for('class_management.index'))
    group = WrittenAssignmentGroup.query.filter_by(id=part.group_id, assignment_id=assignment.id).first()
    if not group:
        flash('This section is not in a group.', 'warning')
        return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))
    direction = 'up' if request.form.get('direction') == 'up' else 'down'
    _move_section(assignment, group, section.id, direction)
    return redirect(url_for('written_assignment.teacher_manage', assignment_id=assignment.id))


@written_assignment_bp.route('/student/<int:assignment_id>/submit', methods=['POST'])
@login_required
def student_submit(assignment_id):
    ctx, error = _student_context(assignment_id)
    if error:
        return error
    if ctx['needs_group']:
        return jsonify({'ok': False, 'error': 'You are not in a group for this assignment yet.'}), 403
    assignment = ctx['assignment']
    class_student = ctx['class_student']
    group = ctx['group']
    part = _get_or_create_part(
        assignment,
        class_student.student_id,
        class_student.name,
        group.id if group else None,
    )
    _lock_overdue(part, assignment)
    if part.status == WrittenAssignmentPart.STATUS_SUBMITTED:
        db.session.commit()
        return jsonify({'ok': True, 'status': part.status, 'already': True})
    if not part.can_edit(assignment):
        db.session.commit()
        return jsonify({'ok': False, 'error': 'The deadline has passed.'}), 403
    if html_is_empty(part.html_body):
        return jsonify({'ok': False, 'error': 'Write something before submitting.'}), 400
    plain = html_to_plain_text(part.html_body or '')
    record_composition(part, plain, typed_chars=0, pasted_chars=0, paste_events=0, compose_ms=0)
    part.status = WrittenAssignmentPart.STATUS_SUBMITTED
    part.submitted_at = datetime.utcnow()
    part.deadline_exempt = False
    db.session.commit()
    return jsonify({
        'ok': True,
        'status': part.status,
        'warning': student_writing_warning(part, assignment),
    })


@written_assignment_bp.route('/student/<int:assignment_id>/unsubmit', methods=['POST'])
@login_required
def student_unsubmit(assignment_id):
    """Return a submitted part to draft while the deadline has not passed."""
    ctx, error = _student_context(assignment_id)
    if error:
        return error
    if ctx['needs_group']:
        return jsonify({'ok': False, 'error': 'You are not in a group for this assignment yet.'}), 403
    assignment = ctx['assignment']
    class_student = ctx['class_student']
    group = ctx['group']
    part = _get_or_create_part(
        assignment,
        class_student.student_id,
        class_student.name,
        group.id if group else None,
    )
    if part.status != WrittenAssignmentPart.STATUS_SUBMITTED:
        return jsonify({'ok': True, 'status': part.status, 'already': True})
    if not assignment.is_open():
        return jsonify({
            'ok': False,
            'error': 'The deadline has passed. Ask your teacher to reopen it.',
        }), 403
    part.status = WrittenAssignmentPart.STATUS_DRAFT
    part.submitted_at = None
    db.session.commit()
    return jsonify({'ok': True, 'status': part.status})


@written_assignment_bp.route('/student/<int:assignment_id>/integrity', methods=['POST'])
@login_required
def student_integrity(assignment_id):
    ctx, error = _student_context(assignment_id)
    if error:
        return error
    if ctx['needs_group']:
        return jsonify({'ok': False}), 403
    assignment = ctx['assignment']
    class_student = ctx['class_student']
    group = ctx['group']
    part = _get_or_create_part(
        assignment,
        class_student.student_id,
        class_student.name,
        group.id if group else None,
    )
    if not part.can_edit(assignment):
        return jsonify({'ok': True, 'ignored': True})
    data = request.get_json(silent=True) or {}
    event = (data.get('event') or '').strip()
    if event == 'focus_loss':
        part.focus_loss_count = min(100000, int(part.focus_loss_count or 0) + 1)
    elif event == 'screenshot_hint':
        part.screenshot_hint_count = min(100000, int(part.screenshot_hint_count or 0) + 1)
    else:
        return jsonify({'ok': False, 'error': 'Unknown event.'}), 400
    db.session.commit()
    return jsonify({
        'ok': True,
        'focus_loss_count': part.focus_loss_count,
        'screenshot_hint_count': part.screenshot_hint_count,
    })


@written_assignment_bp.route('/student/<int:assignment_id>/peers')
@login_required
def student_peers(assignment_id):
    ctx, error = _student_context(assignment_id)
    if error:
        return error
    group = ctx['group']
    if not group:
        return jsonify({'ok': True, 'sections': []})
    assignment = ctx['assignment']
    me = ctx['class_student'].student_id
    return jsonify({
        'ok': True,
        'open': assignment.is_open(),
        'sections': _section_payload(assignment, group, me=me),
    })


@written_assignment_bp.route('/student/<int:assignment_id>/download/<fmt>')
@login_required
def student_download(assignment_id, fmt):
    from utils.dashboard_settings import require_student_dashboard_card
    blocked = require_student_dashboard_card('assignments')
    if blocked:
        return blocked
    ctx, error = _student_context(assignment_id)
    if error:
        return _deny(error)
    if ctx['needs_group']:
        flash('You are not in a group for this assignment yet.', 'warning')
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment_id))
    assignment = ctx['assignment']
    session_obj = assignment.session
    student_id = ctx['class_student'].student_id
    scope = 'group' if assignment.mode == WrittenAssignment.MODE_GROUP else 'student'
    group_id = ctx['group'].id if ctx['group'] else None
    sections = _sections_for(
        assignment,
        'group' if scope == 'group' else 'student',
        student_id=student_id,
        group_id=group_id,
    )
    who = ctx['group'].name if ctx['group'] else student_id
    stem = _download_stem(session_obj.course_code if session_obj else '', assignment.title, who)
    response = _send_download(assignment, session_obj, sections, fmt, stem)
    if response is None:
        return redirect(url_for('written_assignment.student_write', assignment_id=assignment.id))
    return response
