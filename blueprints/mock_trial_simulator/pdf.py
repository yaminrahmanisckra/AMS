"""Formal PDF papers for mock-trial vakalatnama, exhibits, and witness lists."""
import html
import re
from io import BytesIO
from pathlib import Path

from flask import Response, current_app, flash, redirect, render_template, request, url_for
from markupsafe import Markup

from utils.email_safety import content_disposition_attachment

from .models import SIDE_DEFENCE, SIDE_PROSECUTION

_BANGLA_RUN = re.compile(r'[\u0980-\u09FF\u0964\u0965\u09E6-\u09EF]+')


def pdf_rich_text(text):
    """Escape text and wrap Bengali runs so WeasyPrint cannot pick Kalpurush for Latin."""
    if text is None:
        return Markup('')
    raw = str(text)
    if not raw:
        return Markup('')
    parts = []
    last = 0
    for match in _BANGLA_RUN.finditer(raw):
        if match.start() > last:
            parts.append(html.escape(raw[last:match.start()]))
        parts.append(f'<span class="bn">{html.escape(match.group(0))}</span>')
        last = match.end()
    if last < len(raw):
        parts.append(html.escape(raw[last:]))
    return Markup(''.join(parts))


def kalpurush_file_uri():
    try:
        root = current_app.root_path
    except Exception:
        return None
    for rel in ('static/Fonts/Kalpurush.ttf', 'static/fonts/Kalpurush.ttf',
                'static/Fonts/kalpurush.ttf', 'static/fonts/kalpurush.ttf'):
        path = Path(root, *rel.split('/'))
        if path.is_file():
            return path.resolve().as_uri()
    return None


def write_html_pdf(html_content):
    from weasyprint import HTML
    from utils.pdf_fonts import inject_weasyprint_fonts

    html_content, base = inject_weasyprint_fonts(html_content)
    buffer = BytesIO()
    HTML(string=html_content, base_url=base or (request.url_root or '.')).write_pdf(buffer)
    return buffer.getvalue()


def _slug(text, fallback='paper'):
    raw = ''.join(ch.lower() if ch.isalnum() else '-' for ch in (text or ''))
    raw = '-'.join(part for part in raw.split('-') if part)
    return (raw or fallback)[:60]


def paper_filename(case, stem):
    return f"mock-trial-{case.id}-{_slug(stem, 'paper')}.pdf"


def _lines(*values):
    out = []
    for value in values:
        if isinstance(value, (list, tuple)):
            out.extend(str(item).strip() for item in value if str(item).strip())
        else:
            text = str(value or '').strip()
            if text:
                out.append(text)
    return out


def section(heading, body='', subheading='', meta=None, rows=None, note=''):
    return {
        'heading': heading,
        'subheading': subheading,
        'body': (body or '').strip(),
        'meta': [(str(k), str(v)) for k, v in (meta or []) if v not in (None, '')],
        'rows': rows or [],
        'note': (note or '').strip(),
    }


def factsheet_section(case):
    sheet = case.factsheet() or {}
    accused = sheet.get('accused') or []
    accused_names = []
    for item in accused:
        if isinstance(item, dict):
            accused_names.append((item.get('name') or '').strip())
        else:
            accused_names.append(str(item).strip())
    victim = sheet.get('victim') if isinstance(sheet.get('victim'), dict) else {}
    facts = _lines(sheet.get('facts'))
    provisions = _lines(sheet.get('legal_provisions'))
    body_parts = _lines(sheet.get('incident_summary'))
    if facts:
        body_parts.append('Key facts:\n' + '\n'.join(f'• {item}' for item in facts))
    if provisions:
        body_parts.append('Legal provisions:\n' + '\n'.join(f'• {item}' for item in provisions))
    return section(
        'Master factsheet',
        '\n\n'.join(body_parts),
        meta=[
            ('Case', case.title),
            ('Type', case.case_type_label()),
            ('Date / time', sheet.get('date_time')),
            ('Place', sheet.get('place')),
            ('Accused', ', '.join(name for name in accused_names if name)),
            ('Victim', victim.get('name')),
        ],
        note='Teacher copy — students do not receive the master factsheet.',
    )


def fir_section(case):
    fir = case.fir() or {}
    return section(
        'First Information Report (FIR)',
        fir.get('narrative'),
        meta=[
            ('Police station', fir.get('police_station')),
            ('GD / FIR no.', fir.get('gd_entry')),
        ],
        note='Prosecution starting paper. Defence does not receive this copy.',
    )


def accused_section(case):
    accused = case.accused_statement() or {}
    return section(
        'Accused’s first statement',
        accused.get('narrative'),
        note='Defence starting paper. Prosecution does not receive this copy.',
    )


def vakalatnama_section(petition, side):
    label = 'Defence' if side == SIDE_DEFENCE else 'Prosecution'
    team = getattr(petition, 'team', None) if petition else None
    members = []
    if team:
        members = [
            (member.student_name or member.student_id or '').strip()
            for member in (team.members or [])
            if (member.student_name or member.student_id)
        ]
    status = (petition.status if petition else 'missing') or 'missing'
    note = petition.teacher_note() if petition else ''
    return section(
        f'ওকালতনামা — {label}',
        (petition.draft_text if petition else '') or 'No vakalatnama has been filed yet.',
        meta=[
            ('Side', label),
            ('Status', status),
            ('Counsel', ', '.join(members)),
        ],
        note=f'Teacher note: {note}' if note else '',
    )


def exhibit_section(exhibit, index=None):
    body = (exhibit.body() or {}).get('body') or exhibit.summary or '—'
    heading = exhibit.title or 'Exhibit'
    if index is not None:
        heading = f'Exhibit {index} — {heading}'
    return section(
        heading,
        body,
        meta=[
            ('Type', exhibit.exhibit_key),
            ('Summary', exhibit.summary),
        ],
    )


def witness_list_section(identities, note=''):
    rows = []
    for item in identities or []:
        player = (item.get('player_name') or '').strip()
        player_id = (item.get('player_id') or '').strip()
        if player and player_id and player != player_id:
            player_label = f'{player} · {player_id}'
        else:
            player_label = player or player_id or 'Not assigned'
        rows.append({
            'name': item.get('name') or '—',
            'side': item.get('side_label') or '',
            'role': item.get('role_label') or '',
            'designation': item.get('designation') or '',
            'player': player_label,
        })
    return section(
        'Witness list',
        '' if rows else 'No witness identities are available on this copy.',
        rows=rows,
        note=note or 'Character name and the student playing them. Instruction cards are not included.',
    )


def witness_card_section(witness):
    card = witness.card() or {}
    if witness.role == 'io':
        parts = [
            ('Investigation timeline', card.get('timeline')),
            ('Seizure', card.get('seizure')),
            ('s.161 summaries', card.get('s161_summaries')),
            ('Hidden truth / procedural flaws', card.get('procedural_flaws')),
        ]
    elif witness.role == 'expert':
        parts = [
            ('Professional experience', card.get('expertise')),
            ('Scientific findings', card.get('findings')),
            ('Hidden margin of error', card.get('margin_of_error')),
        ]
    else:
        parts = [
            ('1) Direct evidence', card.get('direct_evidence')),
            ('2) s.161 statement', card.get('section_161')),
            ('3) Hidden truth', card.get('hidden_truth')),
            ('4) Hearsay', card.get('hearsay')),
        ]
    parts.append(('Behaviour', card.get('behaviour')))
    body = '\n\n'.join(
        f'{label}\n{(text or "—").strip()}'
        for label, text in parts
    )
    return section(
        f'Instruction card — {witness.name}',
        body,
        meta=[
            ('Called by', witness.side_label()),
            ('Role', witness.role_label()),
            ('Designation', witness.designation),
            ('Played by', ' · '.join(
                part for part in (
                    (witness.assigned_student_name or '').strip(),
                    (witness.assigned_student_id or '').strip(),
                ) if part
            ) or 'Not assigned'),
        ],
        note='Confidential coaching card. Do not show this to prosecution or defence counsel.',
    )


def render_paper_response(case, course_label, title, filename, sections, fallback_url):
    html_content = render_template(
        'mock_trial_simulator/paper_pdf.html',
        case=case,
        course_label=course_label,
        title=title,
        sections=sections,
        kalpurush_uri=kalpurush_file_uri(),
    )
    try:
        pdf_data = write_html_pdf(html_content)
    except ImportError:
        flash('PDF generation is not available on this server.', 'danger')
        return redirect(fallback_url)
    except Exception as exc:
        current_app.logger.exception('Mock trial PDF failed')
        from utils.public_errors import flash_exception
        flash_exception(exc, 'Could not generate PDF', 'danger')
        return redirect(fallback_url)
    if not pdf_data:
        flash('Could not generate PDF.', 'danger')
        return redirect(fallback_url)
    resp = Response(pdf_data, mimetype='application/pdf')
    resp.headers['Content-Disposition'] = content_disposition_attachment(filename)
    resp.headers['Content-Length'] = str(len(pdf_data))
    return resp


def deny_paper(message, fallback_url):
    flash(message, 'warning')
    return redirect(fallback_url)


def normalize_side(raw):
    value = (raw or '').strip().lower()
    if value in ('defence', 'defense', 'd', 'accused'):
        return SIDE_DEFENCE
    if value in ('prosecution', 'p', 'state'):
        return SIDE_PROSECUTION
    return None
