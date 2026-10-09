"""In-AMS written assignments: individual or group, with live writing and integrity signals."""
import json
from datetime import datetime

from markupsafe import escape

from extensions import db

from blueprints.class_management.models import (
    SOCRATES_AI_USE_WARNING,
    SOCRATES_NO_PASTE_MESSAGE,
    classify_socrates_input,
    estimate_socrates_ai_style,
    socrates_word_count,
)


class WrittenAssignment(db.Model):
    """Teacher-set essay students write inside AMS."""
    __tablename__ = 'written_assignment'
    MODE_INDIVIDUAL = 'individual'
    MODE_GROUP = 'group'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    mode = db.Column(db.String(20), nullable=False, default=MODE_INDIVIDUAL)
    paste_disabled = db.Column(db.Boolean, nullable=False, default=True)
    paste_max_words = db.Column(db.Integer, nullable=True)
    paste_max_events = db.Column(db.Integer, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    marks_out_of = db.Column(db.Integer, nullable=False, default=10)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = db.relationship(
        'Session',
        backref=db.backref('written_assignments', lazy='dynamic', cascade='all, delete-orphan'),
    )
    teacher = db.relationship('Teacher', backref=db.backref('written_assignments', lazy='dynamic'))
    groups = db.relationship(
        'WrittenAssignmentGroup',
        backref='assignment',
        lazy='selectin',
        cascade='all, delete-orphan',
        order_by='WrittenAssignmentGroup.id',
    )
    parts = db.relationship(
        'WrittenAssignmentPart',
        backref='assignment',
        lazy='selectin',
        cascade='all, delete-orphan',
    )

    def is_open(self):
        if not self.is_active:
            return False
        if self.deadline and datetime.utcnow().date() > self.deadline.date():
            return False
        return True

    def paste_mode(self):
        """disabled | limited | unlimited"""
        if self.paste_disabled:
            return 'disabled'
        if self.paste_max_words or self.paste_max_events:
            return 'limited'
        return 'unlimited'

    def deadline_label(self):
        if not self.deadline:
            return None
        return self.deadline.strftime('%d %b %Y')

    def days_left(self):
        """Whole days until the deadline date. Negative when past, None without a deadline."""
        if not self.deadline:
            return None
        return (self.deadline.date() - datetime.utcnow().date()).days


class WrittenAssignmentGroup(db.Model):
    __tablename__ = 'written_assignment_group'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('written_assignment.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    teacher_mark = db.Column(db.Float, nullable=True)
    teacher_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship(
        'WrittenAssignmentMember',
        backref='group',
        lazy='selectin',
        cascade='all, delete-orphan',
        order_by='WrittenAssignmentMember.id',
    )


class WrittenAssignmentMember(db.Model):
    __tablename__ = 'written_assignment_member'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('written_assignment_group.id'), nullable=False, index=True)
    student_id = db.Column(db.String(50), nullable=False, index=True)
    student_name = db.Column(db.String(100), nullable=True)


class WrittenAssignmentPart(db.Model):
    """One student's rich-text section. Group work is the set of member parts."""
    __tablename__ = 'written_assignment_part'
    __table_args__ = (
        db.UniqueConstraint('assignment_id', 'student_id', name='uq_written_part_student'),
    )
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('written_assignment.id'), nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('written_assignment_group.id'), nullable=True, index=True)
    student_id = db.Column(db.String(50), nullable=False, index=True)
    student_name = db.Column(db.String(100), nullable=True)
    html_body = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT)
    focus_loss_count = db.Column(db.Integer, nullable=False, default=0)
    screenshot_hint_count = db.Column(db.Integer, nullable=False, default=0)
    paste_events_used = db.Column(db.Integer, nullable=False, default=0)
    input_meta = db.Column(db.Text, nullable=True)
    word_count = db.Column(db.Integer, nullable=False, default=0)
    deadline_exempt = db.Column(db.Boolean, nullable=False, default=False)
    teacher_mark = db.Column(db.Float, nullable=True)
    teacher_comment = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = db.relationship('WrittenAssignmentGroup', backref=db.backref('parts', lazy='selectin'))
    sections = db.relationship(
        'WrittenAssignmentSection',
        backref='part',
        lazy='selectin',
        cascade='all, delete-orphan',
        order_by='WrittenAssignmentSection.sort_order, WrittenAssignmentSection.id',
    )

    def parsed_meta(self):
        if not self.input_meta:
            return {}
        try:
            data = json.loads(self.input_meta)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def can_edit(self, assignment):
        if self.status != self.STATUS_DRAFT:
            return False
        if assignment.is_open() or self.deadline_exempt:
            return True
        return False


def evaluate_paste(assignment, part, *, pasted_chars, paste_events, paste_words, old_words, new_words):
    """Return an error message when this save's paste is outside the assignment rules.

    Explicit paste signals are blocked when paste is off. A large typed burst is
    recorded for the teacher and is not rejected here, so Bangla IME input still saves.
    """
    pasted_chars = max(0, int(pasted_chars or 0))
    paste_events = max(0, int(paste_events or 0))
    paste_words = max(0, int(paste_words or 0))
    reported_paste = paste_events > 0 or pasted_chars >= 24 or paste_words > 0
    if not reported_paste:
        return None

    mode = assignment.paste_mode()
    if mode == 'disabled':
        return SOCRATES_NO_PASTE_MESSAGE
    if mode != 'limited':
        return None

    used = int(part.paste_events_used or 0)
    if assignment.paste_max_events and used + max(1, paste_events) > int(assignment.paste_max_events):
        return f'পেস্ট সীমা শেষ ({int(assignment.paste_max_events)} বার)।'
    growth = max(paste_words, max(0, int(new_words or 0) - int(old_words or 0)))
    if assignment.paste_max_words and growth > int(assignment.paste_max_words):
        return f'প্রতি পেস্টে সর্বোচ্চ {int(assignment.paste_max_words)} শব্দ।'
    return None


def record_composition(part, plain_text, *, typed_chars, pasted_chars, paste_events, compose_ms, paste_snippets=None):
    """Merge this save's typing stats and refresh the AI-style estimate."""
    from utils.integrity_highlight import collect_ai_snippets, remember_paste_snippets

    meta = part.parsed_meta()

    def _add(key, amount, cap):
        try:
            current = int(meta.get(key) or 0)
        except (TypeError, ValueError):
            current = 0
        try:
            extra = int(amount or 0)
        except (TypeError, ValueError):
            extra = 0
        meta[key] = max(0, min(cap, current + max(0, extra)))

    _add('typed_chars', typed_chars, 2_000_000)
    _add('pasted_chars', pasted_chars, 2_000_000)
    _add('paste_events', paste_events, 100_000)
    _add('compose_ms', compose_ms, 86_400_000)
    remember_paste_snippets(meta, paste_snippets)
    classified = classify_socrates_input(plain_text or '', meta)
    meta['source'] = classified.get('source')
    meta['style'] = estimate_socrates_ai_style(plain_text or '')
    meta['ai_snippets'] = collect_ai_snippets(plain_text or '')
    part.input_meta = json.dumps(meta, ensure_ascii=False)
    if paste_events:
        part.paste_events_used = int(part.paste_events_used or 0) + int(paste_events)
    return meta


def part_integrity(part):
    """Teacher-facing integrity snapshot for one writing part."""
    meta = part.parsed_meta() if part else {}
    style = meta.get('style') if isinstance(meta.get('style'), dict) else {}
    source = meta.get('source') or ''
    labels = {
        'typed': 'Typed',
        'pasted': 'Pasted',
        'mixed': 'Pasted + typed',
        'burst': 'Entered very fast',
    }
    return {
        'focus_loss_count': int(getattr(part, 'focus_loss_count', 0) or 0),
        'screenshot_hint_count': int(getattr(part, 'screenshot_hint_count', 0) or 0),
        'paste_events_used': int(getattr(part, 'paste_events_used', 0) or 0),
        'source': source,
        'source_label': labels.get(source),
        'style_flag': bool(style.get('flag')),
        'style_label': style.get('label') if style.get('flag') else None,
        'style_score': style.get('score'),
    }


def student_writing_warning(part, assignment):
    """Student-facing warning when the draft looks pasted against the rules, burst, or AI-styled."""
    if not part:
        return None
    info = part_integrity(part)
    if info['style_flag'] or info['source'] == 'burst':
        return SOCRATES_AI_USE_WARNING
    if assignment.paste_mode() == 'disabled' and info['paste_events_used']:
        return SOCRATES_AI_USE_WARNING
    return None


def plain_word_count(plain):
    return socrates_word_count(plain or '')


class WrittenAssignmentSection(db.Model):
    """One ordered chunk of a group assignment. A student may own several sections
    (e.g. the introduction and the conclusion); sort_order is the serial across the group."""
    __tablename__ = 'written_assignment_section'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('written_assignment.id'), nullable=False, index=True)
    part_id = db.Column(db.Integer, db.ForeignKey('written_assignment_part.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=True)
    html_body = db.Column(db.Text, nullable=True)
    word_count = db.Column(db.Integer, nullable=False, default=0)
    sort_order = db.Column(db.Integer, nullable=False, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def display_title(self, index=None):
        title = (self.title or '').strip()
        if title:
            return title
        return f'Section {index}' if index else 'Section'


def rebuild_part_from_sections(part):
    """Recompose the per-student body and word count from that student's sections."""
    chunks = []
    total = 0
    for section in part.sections or []:
        body = (section.html_body or '').strip()
        title = (section.title or '').strip()
        if title:
            chunks.append(f'<h4>{escape(title)}</h4>')
        if body:
            chunks.append(body)
        total += int(section.word_count or 0)
    part.html_body = '\n'.join(chunks)
    part.word_count = total


class WrittenAssignmentPost(db.Model):
    """Class discussion on one assignment. Teachers and enrolled students share one thread."""
    __tablename__ = 'written_assignment_post'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('written_assignment.id'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('written_assignment_post.id'), nullable=True, index=True)
    author_role = db.Column(db.String(20), nullable=False)
    author_key = db.Column(db.String(80), nullable=False)
    author_name = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    mentions_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    assignment = db.relationship(
        'WrittenAssignment',
        backref=db.backref('posts', lazy='dynamic', cascade='all, delete-orphan'),
    )
    parent = db.relationship(
        'WrittenAssignmentPost',
        remote_side=[id],
        backref=db.backref('replies', lazy='selectin'),
    )
    votes = db.relationship(
        'WrittenAssignmentPostVote',
        backref='post',
        lazy='selectin',
        cascade='all, delete-orphan',
    )
    files = db.relationship(
        'WrittenAssignmentPostFile',
        backref='post',
        lazy='selectin',
        cascade='all, delete-orphan',
    )


class WrittenAssignmentPostVote(db.Model):
    """One like or dislike per person on a discussion post."""
    __tablename__ = 'written_assignment_post_vote'
    __table_args__ = (
        db.UniqueConstraint('post_id', 'author_key', name='uq_wa_post_vote_author'),
    )
    LIKE = 1
    DISLIKE = -1

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('written_assignment_post.id'), nullable=False, index=True)
    author_key = db.Column(db.String(80), nullable=False)
    value = db.Column(db.SmallInteger, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WrittenAssignmentPostFile(db.Model):
    """Image or document attached to a discussion post."""
    __tablename__ = 'written_assignment_post_file'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('written_assignment_post.id'), nullable=False, index=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    mime = db.Column(db.String(80), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)
    is_image = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WrittenAssignmentEvaluation(db.Model):
    """Stored AI evaluation for one submitted part or one group."""
    __tablename__ = 'written_assignment_evaluation'
    __table_args__ = (
        db.UniqueConstraint('assignment_id', 'target_type', 'target_id', name='uq_wa_evaluation_target'),
    )
    TARGET_PART = 'part'
    TARGET_GROUP = 'group'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('written_assignment.id'), nullable=False, index=True)
    target_type = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    body_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
