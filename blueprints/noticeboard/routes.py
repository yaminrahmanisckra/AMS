"""Noticeboard routes: compose, board, PDF, AI draft, notifications."""
from __future__ import annotations

import io
import re
from datetime import date, datetime

from flask import (
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from extensions import db
from role_utils import parse_roles
from user_models import User
from utils.tenant import current_tenant
from utils.window_utils import get_or_404_for_window, query_for_window, stamp_window_id

from . import noticeboard_bp
from .audience import (
    audience_options_for_user,
    can_broadcast,
    can_compose_notices,
    can_manage_notice,
    format_audience_summary,
    is_student_viewer,
    notices_visible_to_student,
    parse_targets_from_form,
    resolve_recipient_users,
    student_matches_notice,
    validate_targets_for_user,
)
from .models import Notice, NoticeTarget


def _require_composer():
    if not can_compose_notices(current_user):
        flash('Only teachers, head, or admin can manage notices.', 'danger')
        return redirect(url_for('index'))
    return None


def _plain_preview(html: str, limit: int = 140) -> str:
    text = re.sub(r'<[^>]+>', ' ', html or '')
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + '…'
    return text


def _bd_today() -> date:
    from utils.timezone import bd_now
    return bd_now().date()


def _parse_notice_date(raw: str | None) -> date:
    raw = (raw or '').strip()
    if not raw:
        return _bd_today()
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return _bd_today()


def _absolute_notice_url(notice_id: int) -> str:
    try:
        return url_for('noticeboard.notice_detail', notice_id=notice_id, _external=True)
    except Exception:
        return url_for('noticeboard.notice_detail', notice_id=notice_id)


def _fanout_notifications_and_email(notice: Notice, recipients: list[User]):
    """Create StudentNotification rows and send notification emails."""
    from blueprints.class_management.models import StudentNotification
    from utils.notification_email import _notification_smtp_configured, send_notification_batch

    link_url = url_for('noticeboard.notice_detail', notice_id=notice.id)
    absolute_url = _absolute_notice_url(notice.id)
    author_name = (notice.author.full_name if notice.author else None) or 'Faculty'
    title = (notice.title or 'New notice')[:300]

    seen = set()
    for user in recipients:
        if not user or user.id in seen:
            continue
        seen.add(user.id)
        db.session.add(
            StudentNotification(
                user_id=user.id,
                type='notice',
                title=title,
                link_url=link_url,
            )
        )
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.warning('Notice in-app notifications failed: %s', e)
        db.session.rollback()

    if not _notification_smtp_configured():
        current_app.logger.error(
            'notice email skipped: set NOTIFICATION_MAIL_USERNAME/PASSWORD/SENDER'
        )
        return

    entries = []
    seen_emails = set()
    for user in recipients:
        email = (user.email or '').strip()
        if not email:
            continue
        key = email.lower()
        if key in seen_emails:
            continue
        seen_emails.add(key)
        name = (user.full_name or user.username or 'Student').strip()
        sid = (user.username or '').strip()
        subject = f'New notice: {title} — {name} ({sid})'
        t = current_tenant()
        text_body = (
            f'Dear {name},\n\n'
            'A new notice has been posted on the Academic Management System (AMS) '
            f'noticeboard of the {t.display_with_university}.\n\n'
            f'- Title: {title}\n'
            f'- Posted by: {author_name}\n'
            f'- Notice date: {notice.notice_date.isoformat() if notice.notice_date else ""}\n\n'
            'Open the noticeboard link below (sign in with your AMS student account):\n'
            f'{absolute_url}\n\n'
            'Regards,\n'
            'Academic Management System\n'
            f'{t.display_with_university}\n'
        )
        html_body = (
            f'<p>Dear {name},</p>'
            '<p>A new notice has been posted on the AMS noticeboard '
            f'({t.display_with_university}).</p>'
            '<ul>'
            f'<li><strong>Title:</strong> {title}</li>'
            f'<li><strong>Posted by:</strong> {author_name}</li>'
            f'<li><strong>Notice date:</strong> {notice.notice_date.isoformat() if notice.notice_date else ""}</li>'
            '</ul>'
            f'<p><a href="{absolute_url}">Open notice on noticeboard</a></p>'
            f'<p style="word-break:break-all;">{absolute_url}</p>'
            '<p>Regards,<br>Academic Management System<br>'
            f'{t.display_with_university}</p>'
        )
        entries.append({
            'recipient': email,
            'subject': subject,
            'text_body': text_body,
            'html_body': html_body,
        })

    try:
        sent = send_notification_batch(None, entries)
        current_app.logger.info(
            'Notice %s email: %s sent (recipients=%s)',
            notice.id,
            sent,
            len(entries),
        )
    except Exception as e:
        current_app.logger.error('Notice email failed: %s', e, exc_info=True)


def _user_can_view_notice(notice: Notice) -> bool:
    if notice.deleted_at and not can_manage_notice(notice):
        return False
    if can_manage_notice(notice) or can_compose_notices(current_user):
        # Composers may preview any notice they can manage; head/admin see all;
        # teachers may open their own. For other teachers viewing peers' notices:
        if can_manage_notice(notice) or can_broadcast(current_user):
            return True
        if notice.author_user_id == current_user.id:
            return True
    # Student path (active window sessions only)
    username = current_user.username
    from blueprints.class_management.models import ClassStudent, Session
    from blueprints.student_management.models import Student

    student = Student.query.filter_by(student_id=username).first()
    batch = student.batch if student else None
    window_session_ids = {
        r[0] for r in query_for_window(Session).with_entities(Session.id).all()
    }
    if window_session_ids:
        session_ids = {
            r[0]
            for r in ClassStudent.query.filter(
                ClassStudent.student_id == username,
                ClassStudent.session_id.in_(window_session_ids),
            ).with_entities(ClassStudent.session_id).all()
        }
    else:
        session_ids = set()
    if notice.deleted_at:
        return False
    return student_matches_notice(notice, username, batch, session_ids)


def _render_notice_pdf(notice: Notice):
    try:
        from weasyprint import HTML
        from utils.pdf_fonts import formal_font_face_css, resolve_formal_pdf_fonts
    except ImportError:
        flash('PDF generation is not available on this server.', 'danger')
        return redirect(url_for('noticeboard.notice_detail', notice_id=notice.id))

    formal_fonts = resolve_formal_pdf_fonts()
    author = notice.author
    author_name = (author.full_name if author else '') or '—'
    signature_data_uri = None
    try:
        from utils.user_signature import user_signature_data_uri
        signature_data_uri = user_signature_data_uri(author)
    except Exception as e:
        current_app.logger.warning('Notice PDF signature lookup failed: %s', e)

    ctx = {
        'notice': notice,
        'author_name': author_name,
        'audience_summary': format_audience_summary(notice),
        'signature_data_uri': signature_data_uri,
    }
    if formal_fonts:
        ctx.update({
            'pdf_font_regular': formal_fonts['regular'],
            'pdf_font_bold': formal_fonts['bold'],
        })
    html_content = render_template('noticeboard/notice_pdf.html', **ctx)
    if formal_fonts:
        face = f'<style>{formal_font_face_css(formal_fonts)}</style>'
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', face + '</head>', 1)

    try:
        pdf_buffer = io.BytesIO()
        base = (formal_fonts['fonts_dir'].as_uri() + '/') if formal_fonts else request.url_root
        HTML(string=html_content, base_url=base).write_pdf(pdf_buffer)
        pdf_data = pdf_buffer.getvalue()
    except Exception as e:
        current_app.logger.error('Notice PDF error: %s', e, exc_info=True)
        flash(f'Could not generate PDF: {e}', 'danger')
        return redirect(url_for('noticeboard.notice_detail', notice_id=notice.id))

    safe_title = re.sub(r'[^\w\-]+', '_', (notice.title or 'notice'))[:60]
    filename = f'notice_{notice.id}_{safe_title}.pdf'
    resp = Response(pdf_data, mimetype='application/pdf')
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    resp.headers['Content-Length'] = str(len(pdf_data))
    return resp


@noticeboard_bp.route('/')
@login_required
def index():
    if is_student_viewer(current_user) or (
        'student' in parse_roles(getattr(current_user, 'active_role', None) or current_user.role)
        and not can_compose_notices(current_user)
    ):
        return redirect(url_for('noticeboard.board'))

    restriction = _require_composer()
    if restriction:
        return restriction

    if can_broadcast(current_user):
        notices = (
            query_for_window(Notice)
            .filter(Notice.deleted_at.is_(None))
            .order_by(Notice.notice_date.desc(), Notice.created_at.desc())
            .all()
        )
    else:
        notices = (
            query_for_window(Notice)
            .filter(
                Notice.deleted_at.is_(None),
                Notice.author_user_id == current_user.id,
            )
            .order_by(Notice.notice_date.desc(), Notice.created_at.desc())
            .all()
        )

    rows = []
    for n in notices:
        rows.append({
            'notice': n,
            'preview': _plain_preview(n.body_html),
            'audience': format_audience_summary(n),
            'author': (n.author.full_name if n.author else '') or '—',
            'can_manage': can_manage_notice(n),
        })
    return render_template(
        'noticeboard/manage.html',
        rows=rows,
        can_broadcast=can_broadcast(current_user),
    )


@noticeboard_bp.route('/board')
@login_required
def board():
    if can_compose_notices(current_user) and not is_student_viewer(current_user):
        # Staff preview: show all non-deleted (head/admin) or own + targeted to their teaching context
        if can_broadcast(current_user):
            notices = (
                query_for_window(Notice)
                .filter(Notice.deleted_at.is_(None))
                .order_by(Notice.notice_date.desc(), Notice.created_at.desc())
                .all()
            )
        else:
            # Teachers see notices they authored on the board preview
            notices = (
                query_for_window(Notice)
                .filter(
                    Notice.deleted_at.is_(None),
                    Notice.author_user_id == current_user.id,
                )
                .order_by(Notice.notice_date.desc(), Notice.created_at.desc())
                .all()
            )
    else:
        notices = notices_visible_to_student(current_user.username)

    cards = []
    for i, n in enumerate(notices):
        cards.append({
            'notice': n,
            'preview': _plain_preview(n.body_html, 160),
            'author': (n.author.full_name if n.author else '') or '—',
            'rotation': ((i % 5) - 2) * 1.2,  # slight tilt variety
        })
    return render_template(
        'noticeboard/board.html',
        cards=cards,
        is_composer=can_compose_notices(current_user),
    )


@noticeboard_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    restriction = _require_composer()
    if restriction:
        return restriction

    options = audience_options_for_user(current_user)

    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        body_html = (request.form.get('body_html') or '').strip()
        notice_date = _parse_notice_date(request.form.get('notice_date'))
        raw_targets = parse_targets_from_form(request.form)
        targets, err = validate_targets_for_user(raw_targets, current_user)

        if not title:
            flash('Title is required.', 'danger')
        elif not body_html or body_html in ('<p></p>', '<p><br></p>'):
            flash('Notice body is required.', 'danger')
        elif err:
            flash(err, 'danger')
        else:
            notice = Notice(
                title=title[:300],
                body_html=body_html,
                author_user_id=current_user.id,
                notice_date=notice_date,
            )
            stamp_window_id(notice)
            db.session.add(notice)
            db.session.flush()
            for ttype, value in targets:
                db.session.add(
                    NoticeTarget(
                        notice_id=notice.id,
                        target_type=ttype,
                        target_value=value,
                    )
                )
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error('Notice create failed: %s', e, exc_info=True)
                flash(f'Could not save notice: {e}', 'danger')
                return render_template(
                    'noticeboard/compose.html',
                    mode='create',
                    notice=None,
                    options=options,
                    form_title=title,
                    form_body=body_html,
                    form_date=notice_date.isoformat(),
                    selected=raw_targets,
                )

            recipients = resolve_recipient_users(targets)
            _fanout_notifications_and_email(notice, recipients)
            flash(
                f'Notice published to {len(recipients)} student account(s).',
                'success',
            )
            return redirect(url_for('noticeboard.index'))

        return render_template(
            'noticeboard/compose.html',
            mode='create',
            notice=None,
            options=options,
            form_title=title,
            form_body=body_html,
            form_date=notice_date.isoformat(),
            selected=raw_targets,
        )

    return render_template(
        'noticeboard/compose.html',
        mode='create',
        notice=None,
        options=options,
        form_title='',
        form_body='',
        form_date=_bd_today().isoformat(),
        selected=[],
    )


@noticeboard_bp.route('/<int:notice_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(notice_id):
    restriction = _require_composer()
    if restriction:
        return restriction

    notice = get_or_404_for_window(Notice, notice_id)
    if notice.deleted_at:
        flash('This notice was deleted.', 'warning')
        return redirect(url_for('noticeboard.index'))
    if not can_manage_notice(notice):
        flash('You cannot edit this notice.', 'danger')
        return redirect(url_for('noticeboard.index'))

    options = audience_options_for_user(current_user)
    selected = [(t.target_type, t.target_value) for t in (notice.targets or [])]

    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        body_html = (request.form.get('body_html') or '').strip()
        notice_date = _parse_notice_date(request.form.get('notice_date'))
        raw_targets = parse_targets_from_form(request.form)
        targets, err = validate_targets_for_user(raw_targets, current_user)

        if not title:
            flash('Title is required.', 'danger')
        elif not body_html or body_html in ('<p></p>', '<p><br></p>'):
            flash('Notice body is required.', 'danger')
        elif err:
            flash(err, 'danger')
        else:
            notice.title = title[:300]
            notice.body_html = body_html
            notice.notice_date = notice_date
            notice.updated_at = datetime.utcnow()
            NoticeTarget.query.filter_by(notice_id=notice.id).delete()
            for ttype, value in targets:
                db.session.add(
                    NoticeTarget(
                        notice_id=notice.id,
                        target_type=ttype,
                        target_value=value,
                    )
                )
            try:
                db.session.commit()
                flash('Notice updated. Recipients were not re-notified.', 'success')
                return redirect(url_for('noticeboard.index'))
            except Exception as e:
                db.session.rollback()
                flash(f'Could not update notice: {e}', 'danger')

        selected = raw_targets
        return render_template(
            'noticeboard/compose.html',
            mode='edit',
            notice=notice,
            options=options,
            form_title=title,
            form_body=body_html,
            form_date=notice_date.isoformat(),
            selected=selected,
        )

    return render_template(
        'noticeboard/compose.html',
        mode='edit',
        notice=notice,
        options=options,
        form_title=notice.title,
        form_body=notice.body_html,
        form_date=notice.notice_date.isoformat() if notice.notice_date else _bd_today().isoformat(),
        selected=selected,
    )


@noticeboard_bp.route('/<int:notice_id>/delete', methods=['POST'])
@login_required
def delete(notice_id):
    restriction = _require_composer()
    if restriction:
        return restriction

    notice = get_or_404_for_window(Notice, notice_id)
    if not can_manage_notice(notice):
        flash('You cannot delete this notice.', 'danger')
        return redirect(url_for('noticeboard.index'))

    notice.deleted_at = datetime.utcnow()
    db.session.commit()
    flash('Notice deleted.', 'info')
    return redirect(url_for('noticeboard.index'))


@noticeboard_bp.route('/<int:notice_id>')
@login_required
def notice_detail(notice_id):
    notice = get_or_404_for_window(Notice, notice_id)
    if not _user_can_view_notice(notice):
        flash('You do not have access to this notice.', 'danger')
        return redirect(url_for('noticeboard.board' if not can_compose_notices(current_user) else 'noticeboard.index'))

    # Mark matching student notifications as read
    try:
        from blueprints.class_management.models import StudentNotification

        link_suffix = f'/noticeboard/{notice_id}'
        notifs = StudentNotification.query.filter(
            StudentNotification.user_id == current_user.id,
            StudentNotification.type == 'notice',
            StudentNotification.read_at.is_(None),
            or_(
                StudentNotification.link_url == url_for('noticeboard.notice_detail', notice_id=notice_id),
                StudentNotification.link_url.endswith(link_suffix),
            ),
        ).all()
        if notifs:
            now = datetime.utcnow()
            for n in notifs:
                n.read_at = now
            db.session.commit()
    except Exception as e:
        current_app.logger.warning('Could not mark notice notifications read: %s', e)
        db.session.rollback()

    return render_template(
        'noticeboard/detail.html',
        notice=notice,
        author_name=(notice.author.full_name if notice.author else '') or '—',
        audience_summary=format_audience_summary(notice),
        can_manage=can_manage_notice(notice),
        is_composer=can_compose_notices(current_user),
    )


@noticeboard_bp.route('/<int:notice_id>/pdf')
@login_required
def notice_pdf(notice_id):
    notice = get_or_404_for_window(Notice, notice_id)
    if not _user_can_view_notice(notice):
        flash('You do not have access to this notice.', 'danger')
        return redirect(url_for('noticeboard.board'))
    return _render_notice_pdf(notice)


@noticeboard_bp.route('/api/audience-options')
@login_required
def api_audience_options():
    if not can_compose_notices(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(audience_options_for_user(current_user))


@noticeboard_bp.route('/ai/draft', methods=['POST'])
@login_required
def ai_draft():
    if not can_compose_notices(current_user):
        return jsonify({'ok': False, 'error': 'Forbidden'}), 403

    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return jsonify({'ok': False, 'error': 'Prompt is required.'}), 400

    system_prompt = (
        f'You write official academic notices for {current_tenant().display_with_university}. '
        'Return ONLY an HTML fragment suitable for a rich-text editor body '
        '(use <p>, <ul>, <ol>, <li>, <strong>, <em>, <h3>). '
        'Do not wrap in <html> or <body>. Do not invent official letterheads. '
        'Be clear, formal, and concise. Match the language of the user prompt '
        '(Bangla or English).'
    )
    user_prompt = (
        'Write a notice body based on this request:\n\n'
        f'{prompt}\n\n'
        'Return HTML only.'
    )

    try:
        from utils.ai.client import AIClientError, generate_text_with_meta

        meta = generate_text_with_meta(system_prompt, user_prompt)
        html = (meta.get('text') or '').strip()
        # Strip markdown fences if the model wraps them
        if html.startswith('```'):
            html = re.sub(r'^```(?:html)?\s*', '', html)
            html = re.sub(r'\s*```$', '', html)
        if not html:
            return jsonify({'ok': False, 'error': 'AI returned an empty draft.'}), 502
        return jsonify({
            'ok': True,
            'html': html,
            'provider': meta.get('provider'),
            'model_name': meta.get('model_name'),
        })
    except Exception as e:
        msg = str(e)
        current_app.logger.warning('Notice AI draft failed: %s', e)
        return jsonify({'ok': False, 'error': msg}), 502
