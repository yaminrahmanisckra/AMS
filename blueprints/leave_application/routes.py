import os
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from extensions import db
from . import leave_application_bp
from role_utils import has_teacher_privileges, get_teachers_excluding_head


def _require_teacher():
    """Allow only users with teacher privileges to use Leave Application."""
    if not current_user.is_authenticated or not has_teacher_privileges(current_user):
        flash('Leave Application is available only for teacher accounts.', 'danger')
        return redirect(url_for('index'))
    return None


def _get_kalpurush_font_path():
    """Return absolute path to Kalpurush font for WeasyPrint PDF (Bengali support), or None."""
    root = current_app.root_path
    for rel in ('static/Fonts/kalpurush.ttf', 'static/fonts/kalpurush.ttf',
                'static/Fonts/Kalpurush.ttf', 'static/fonts/Kalpurush.ttf'):
        path = os.path.join(root, *rel.split('/'))
        if os.path.exists(path):
            return os.path.abspath(path).replace(os.sep, '/')
    return None


def _render_leave_pdf(template_name, context, filename):
    """Render a leave application HTML template as PDF and return Flask Response."""
    try:
        from flask import Response
        import io
        from weasyprint import HTML
        from utils.pdf_fonts import resolve_formal_pdf_fonts, formal_font_face_css
    except ImportError:
        return jsonify({'error': 'WeasyPrint not available'}), 503

    formal_fonts = resolve_formal_pdf_fonts()
    context = dict(context)
    if formal_fonts:
        context.update({
            'pdf_font_regular': formal_fonts['regular'],
            'pdf_font_bold': formal_fonts['bold'],
            'pdf_font_italic': formal_fonts.get('italic'),
            'pdf_font_bold_italic': formal_fonts.get('bold_italic'),
        })

    html_content = render_template(template_name, **context)
    if formal_fonts:
        face = f"<style>{formal_font_face_css(formal_fonts)}</style>"
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', face + '</head>', 1)
        html_content = html_content.replace(
            'Tahoma, Arial, sans-serif',
            "'PDFSerif', 'Times New Roman', Times, serif",
        )
    try:
        pdf_buffer = io.BytesIO()
        base = (formal_fonts['fonts_dir'].as_uri() + '/') if formal_fonts else request.url_root
        HTML(string=html_content, base_url=base).write_pdf(pdf_buffer)
        pdf_data = pdf_buffer.getvalue()
    except Exception as e:
        current_app.logger.error(f"Leave Application PDF error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

    resp = Response(pdf_data, mimetype='application/pdf')
    resp.headers['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
    resp.headers['Content-Length'] = str(len(pdf_data))
    return resp


@leave_application_bp.route('/')
@login_required
def index():
    restriction = _require_teacher()
    if restriction:
        return restriction
    return render_template('leave_application/index.html')


def _common_form_context(form_title):
    """Base context for all leave forms."""
    applicant_name = (current_user.full_name or '').strip() if hasattr(current_user, 'full_name') else ''
    return {
        'form_title': form_title,
        'applicant_name': applicant_name,
        'kalpurush_font_path': _get_kalpurush_font_path(),
    }


def _get_leave_form_teacher_context():
    """Internal teachers list and applicant designation for leave forms (from Teacher by current user name)."""
    from blueprints.class_management.models import Teacher
    internal_teachers = get_teachers_excluding_head(external_only=False)
    applicant_designation = ''
    if hasattr(current_user, 'full_name') and current_user.full_name and Teacher:
        t = Teacher.query.filter(Teacher.name == current_user.full_name.strip()).first()
        if not t:
            t = Teacher.query.filter(db.func.lower(Teacher.name) == current_user.full_name.strip().lower()).first()
        if not t and current_user.full_name:
            t = Teacher.query.filter(db.func.lower(Teacher.name).like('%' + current_user.full_name.strip().lower() + '%')).first()
        if t and getattr(t, 'designation', None):
            applicant_designation = t.designation or ''
    return {'internal_teachers': internal_teachers, 'applicant_designation': applicant_designation}


@leave_application_bp.route('/station', methods=['GET', 'POST'])
@login_required
def station_leave():
    restriction = _require_teacher()
    if restriction:
        return restriction
    if request.method == 'GET':
        ctx = _common_form_context('ষ্টেশন ত্যাগের আবেদন পত্র')
        ctx.update(_get_leave_form_teacher_context())
        return render_template('leave_application/form_station.html', **ctx)

    # POST – generate PDF
    data = request.form
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    total_days = data.get('total_days', '').strip()
    if not total_days and date_from and date_to:
        d1, d2 = _parse_date(date_from), _parse_date(date_to)
        if d1 and d2 and d2 >= d1:
            total_days = str((d2 - d1).days + 1)
    ctx = _common_form_context('ষ্টেশন ত্যাগের আবেদন পত্র')
    ctx.update(
        applicant_name=data.get('applicant_name', '').strip(),
        applicant_designation=data.get('applicant_designation', '').strip(),
        department=data.get('department', '').strip(),
        reason=data.get('reason', '').strip(),
        date_from=_format_date_for_pdf(date_from),
        date_to=_format_date_for_pdf(date_to),
        total_days=total_days or '',
        address_during_leave=data.get('address_during_leave', '').strip(),
        substitute_name=data.get('substitute_name', '').strip(),
        substitute_designation=data.get('substitute_designation', '').strip(),
    )
    return _render_leave_pdf('leave_application/pdf_station.html', ctx, 'station_leave_application.pdf')


@leave_application_bp.route('/non-numeric-station', methods=['GET', 'POST'])
@login_required
def non_numeric_station_leave():
    restriction = _require_teacher()
    if restriction:
        return restriction
    if request.method == 'GET':
        ctx = _common_form_context('কর্তব্য ছুটির আবেদন পত্র')
        ctx.update(_get_leave_form_teacher_context())
        return render_template('leave_application/form_non_numeric_station.html', **ctx)

    data = request.form
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    total_days = data.get('total_days', '').strip()
    if not total_days and date_from and date_to:
        d1, d2 = _parse_date(date_from), _parse_date(date_to)
        if d1 and d2 and d2 >= d1:
            total_days = str((d2 - d1).days + 1)
    ctx = _common_form_context('কর্তব্য ছুটির আবেদন পত্র')
    ctx.update(
        applicant_name=data.get('applicant_name', '').strip(),
        applicant_designation=data.get('applicant_designation', '').strip(),
        department=data.get('department', '').strip(),
        reason=data.get('reason', '').strip(),
        date_from=_format_date_for_pdf(date_from),
        date_to=_format_date_for_pdf(date_to),
        total_days=total_days or '',
        address_during_leave=data.get('address_during_leave', '').strip(),
        substitute_name=data.get('substitute_name', '').strip(),
        substitute_designation=data.get('substitute_designation', '').strip(),
    )
    return _render_leave_pdf('leave_application/pdf_non_numeric_station.html', ctx, 'Duty leave.pdf')


@leave_application_bp.route('/special', methods=['GET', 'POST'])
@login_required
def special_leave():
    restriction = _require_teacher()
    if restriction:
        return restriction
    if request.method == 'GET':
        ctx = _common_form_context('নৈমিত্তিক ছুটির আবেদন পত্র')
        ctx.update(_get_leave_form_teacher_context())
        return render_template('leave_application/form_special.html', **ctx)

    data = request.form
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    total_days = data.get('total_days', '').strip()
    if not total_days and date_from and date_to:
        d1, d2 = _parse_date(date_from), _parse_date(date_to)
        if d1 and d2 and d2 >= d1:
            total_days = str((d2 - d1).days + 1)
    from datetime import datetime
    leave_year = data.get('leave_year', '').strip() or str(datetime.now().year)
    ctx = _common_form_context('নৈমিত্তিক ছুটির আবেদন পত্র')
    ctx.update(
        applicant_name=data.get('applicant_name', '').strip(),
        applicant_designation=data.get('applicant_designation', '').strip(),
        department=data.get('department', '').strip(),
        reason=data.get('reason', '').strip(),
        date_from=_format_date_for_pdf(date_from),
        date_to=_format_date_for_pdf(date_to),
        total_days=total_days or '',
        leave_year=leave_year,
        address_during_leave=data.get('address_during_leave', '').strip(),
        substitute_name=data.get('substitute_name', '').strip(),
        substitute_designation=data.get('substitute_designation', '').strip(),
        casual_leave_entitlement=data.get('casual_leave_entitlement', '').strip(),
        casual_leave_availed=data.get('casual_leave_availed', '').strip(),
        casual_leave_total_with_proposed=data.get('casual_leave_total_with_proposed', '').strip(),
    )
    return _render_leave_pdf('leave_application/pdf_special.html', ctx, 'casual leave application.pdf')


def _parse_date(s):
    """Parse date string (YYYY-MM-DD or DD/MM/YYYY or D/M/YYYY) to date; return None if invalid."""
    if not s:
        return None
    s = s.strip()
    from datetime import datetime
    # YYYY-MM-DD
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        try:
            return datetime.strptime(s, '%Y-%m-%d').date()
        except ValueError:
            pass
    # DD/MM/YYYY or D/M/YYYY
    parts = s.replace('-', '/').split('/')
    if len(parts) == 3:
        try:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y < 100:
                y += 2000 if y < 50 else 1900
            return datetime(y, m, d).date()
        except (ValueError, TypeError):
            pass
    return None


def _format_date_for_pdf(s):
    """Format date string for PDF display as DD/MM/YYYY. Accepts YYYY-MM-DD or DD/MM/YYYY."""
    if not s:
        return ''
    s = s.strip()
    d = _parse_date(s)
    if d is None:
        return s
    return d.strftime('%d/%m/%Y')


@leave_application_bp.route('/casual-station', methods=['GET', 'POST'])
@login_required
def casual_station_leave():
    restriction = _require_teacher()
    if restriction:
        return restriction
    if request.method == 'GET':
        from datetime import datetime
        ctx = _common_form_context('নৈমিত্তিক ছুটিসহ স্টেশন লীভের আবেদন ফরম')
        ctx['current_year'] = datetime.now().year
        ctx.update(_get_leave_form_teacher_context())
        return render_template('leave_application/form_casual_station.html', **ctx)

    from datetime import datetime
    data = request.form
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    total_days = data.get('total_days', '').strip()
    if not total_days and date_from and date_to:
        d1, d2 = _parse_date(date_from), _parse_date(date_to)
        if d1 and d2 and d2 >= d1:
            total_days = str((d2 - d1).days + 1)
    leave_year = data.get('leave_year', '').strip()

    ctx = _common_form_context('নৈমিত্তিক ছুটিসহ স্টেশন লীভের আবেদন ফরম')
    ctx.update(
        applicant_name=data.get('applicant_name', '').strip(),
        applicant_designation=data.get('applicant_designation', '').strip(),
        department=data.get('department', '').strip(),
        date_from=_format_date_for_pdf(date_from),
        date_to=_format_date_for_pdf(date_to),
        total_days=total_days or '',
        reason=data.get('reason', '').strip(),
        address_during_leave=data.get('address_during_leave', '').strip(),
        substitute_name=data.get('substitute_name', '').strip(),
        substitute_designation=data.get('substitute_designation', '').strip(),
        leave_year=leave_year,
        annual_entitlement=data.get('annual_entitlement', '').strip(),
        leave_availed=data.get('leave_availed', '').strip(),
        leave_availed_days=data.get('leave_availed_days', '').strip(),
    )
    return _render_leave_pdf('leave_application/pdf_casual_station.html', ctx, 'casual with station leave application.pdf')


@leave_application_bp.route('/sick-other', methods=['GET', 'POST'])
@login_required
def sick_other_leave():
    restriction = _require_teacher()
    if restriction:
        return restriction
    if request.method == 'GET':
        ctx = _common_form_context('অর্জিত/শ্রান্তিবিনোদন/মেডিকেল ছুটির আবেদন পত্র')
        ctx.update(_get_leave_form_teacher_context())
        return render_template('leave_application/form_sick_other.html', **ctx)

    data = request.form
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    total_days = data.get('total_days', '').strip()
    if not total_days and date_from and date_to:
        d1, d2 = _parse_date(date_from), _parse_date(date_to)
        if d1 and d2 and d2 >= d1:
            total_days = str((d2 - d1).days + 1)
    ctx = _common_form_context('অর্জিত/শ্রান্তিবিনোদন/মেডিকেল ছুটির আবেদন পত্র')
    ctx.update(
        applicant_name=data.get('applicant_name', '').strip(),
        applicant_designation=data.get('applicant_designation', '').strip(),
        department=data.get('department', '').strip(),
        reason=data.get('reason', '').strip(),
        date_from=_format_date_for_pdf(date_from),
        date_to=_format_date_for_pdf(date_to),
        total_days=total_days or '',
        address_during_leave=data.get('address_during_leave', '').strip(),
        substitute_name=data.get('substitute_name', '').strip(),
        substitute_designation=data.get('substitute_designation', '').strip(),
        full_pay_summary=data.get('full_pay_summary', '').strip(),
        half_pay_summary=data.get('half_pay_summary', '').strip(),
        total_sick_summary=data.get('total_sick_summary', '').strip(),
    )
    return _render_leave_pdf('leave_application/pdf_sick_other.html', ctx, 'recreation and other leave application.pdf')

