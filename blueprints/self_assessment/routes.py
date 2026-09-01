"""Self Assessment and PSAC Committee routes."""
import json
import os
import secrets
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from extensions import csrf
from role_utils import parse_roles, get_teachers_excluding_head
from utils.tenant import current_tenant, load_survey_pack
from utils.window_utils import get_for_window, get_or_404_for_window, query_for_window, stamp_window_id, get_effective_window_id

from . import self_assessment_bp
from .models import PsacCommittee, PsacCommitteeMember, SurveyLink, SurveyResponse, AlumniSurveyResponse, SurveyInsightSnapshot
from blueprints.class_management.models import Teacher

SURVEY_TYPES = ('alumni', 'employer', 'faculty', 'non_academic', 'student')


def _survey_form_template(survey_type):
    pack = load_survey_pack(survey_type)
    if pack and current_tenant().surveys_use_pack:
        return 'self_assessment/survey_from_pack.html', pack
    mapping = {
        'alumni': 'self_assessment/alumni_survey.html',
        'employer': 'self_assessment/employer_survey.html',
        'student': 'self_assessment/student_survey.html',
        'faculty': 'self_assessment/faculty_survey.html',
        'non_academic': 'self_assessment/non_academic_survey.html',
    }
    return mapping.get(survey_type, 'self_assessment/survey_placeholder.html'), pack


def _survey_pdf_template(survey_type):
    pack = load_survey_pack(survey_type)
    if pack and current_tenant().surveys_use_pack:
        return 'self_assessment/survey_from_pack_pdf.html', pack
    mapping = {
        'alumni': 'self_assessment/alumni_form_pdf.html',
        'employer': 'self_assessment/employer_form_pdf.html',
        'student': 'self_assessment/student_form_pdf.html',
        'faculty': 'self_assessment/faculty_form_pdf.html',
        'non_academic': 'self_assessment/non_academic_form_pdf.html',
    }
    return mapping.get(survey_type, 'self_assessment/generic_form_pdf.html'), pack


def _committee_ids_subquery():
    return query_for_window(PsacCommittee).with_entities(PsacCommittee.id)


def _members_in_window():
    return PsacCommitteeMember.query.filter(PsacCommitteeMember.committee_id.in_(_committee_ids_subquery()))


def _survey_link_by_code(survey_type, code):
    """Public access: access_code is globally unique (no window filter)."""
    return SurveyLink.query.filter_by(
        survey_type=survey_type,
        access_code=(code or '').strip(),
    ).first()


def _get_kalpurush_font_path():
    """Return absolute path to Kalpurush font for WeasyPrint PDF (Bengali support), or None."""
    root = current_app.root_path
    for rel in ('static/Fonts/kalpurush.ttf', 'static/fonts/kalpurush.ttf',
                'static/Fonts/Kalpurush.ttf', 'static/fonts/Kalpurush.ttf'):
        path = os.path.join(root, *rel.split('/'))
        if os.path.exists(path):
            return os.path.abspath(path).replace(os.sep, '/')
    return None


def _write_self_assessment_pdf(html_content):
    """Embed Liberation Serif fallback and render HTML to PDF bytes."""
    import io
    from weasyprint import HTML
    from utils.pdf_fonts import resolve_formal_pdf_fonts, formal_font_face_css

    formal_fonts = resolve_formal_pdf_fonts()
    if formal_fonts:
        face = f"<style>{formal_font_face_css(formal_fonts)}</style>"
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', face + '</head>', 1)
        html_content = html_content.replace(
            'Tahoma, Arial, sans-serif',
            "'PDFSerif', 'Times New Roman', Times, serif",
        )
        base_url = formal_fonts['fonts_dir'].as_uri() + '/'
    else:
        base_url = request.url_root

    pdf_buffer = io.BytesIO()
    HTML(string=html_content, base_url=base_url).write_pdf(pdf_buffer)
    return pdf_buffer.getvalue()


def _client_ip():
    """Client IP for one-per-IP check (ProxyFix-aware; ignores spoofed X-Forwarded-For)."""
    from utils.request_ip import client_ip
    return client_ip()


def _current_teacher():
    """Return Teacher for current user by full_name match (exact, trimmed, then case-insensitive)."""
    if not current_user.is_authenticated:
        return None
    from extensions import db
    name = (current_user.full_name or '').strip()
    if not name:
        return None
    t = Teacher.query.filter_by(name=current_user.full_name).first()
    if t:
        return t
    t = Teacher.query.filter(Teacher.name == name).first()
    if t:
        return t
    t = Teacher.query.filter(db.func.lower(Teacher.name) == name.lower()).first()
    if t:
        return t
    # Match when Teacher.name is "Full Name (Designation)" and user.full_name is "Full Name"
    t = Teacher.query.filter(db.func.lower(Teacher.name).startswith(name.lower())).first()
    return t


def is_psac_head():
    """True if current user is Head/Dean and is the PSAC committee head."""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles:
        return False
    teacher = _current_teacher()
    if not teacher:
        return False
    committee = query_for_window(PsacCommittee).filter_by(head_teacher_id=teacher.id).first()
    return committee is not None


def _name_matches_user(teacher_name, user_full_name):
    """True if teacher_name matches user_full_name (exact match only, case-insensitive,
    trimmed, and tolerant of a trailing "(Designation)" suffix on Teacher.name).

    Prefix/substring matching was previously used here but that allowed a short
    name (e.g. "Ali") to match unrelated teachers whose name merely contained
    it as a substring (e.g. "Natalie Khan"), letting one user's identity
    resolve to another teacher's PSAC/self-assessment records.
    """
    if not teacher_name or not user_full_name:
        return False
    u = (user_full_name or '').strip().lower()
    t_raw = (teacher_name or '').strip()
    t = t_raw.lower()
    if u == t:
        return True
    # Teacher.name often "Full Name (Designation)" – compare without part in parentheses
    if ' (' in t_raw:
        t_base = t_raw.split(' (')[0].strip().lower()
        if u == t_base:
            return True
    return False


def is_psac_member_or_head():
    """True if current user can see Self Assessment (Head, or PSAC member, or ad-hoc member)."""
    if not current_user.is_authenticated:
        return False
    roles = parse_roles(current_user.role)
    user_name = (current_user.full_name or '').strip()

    # 1) Head/Dean who is PSAC committee head
    teacher = _current_teacher()
    if teacher:
        if 'head' in roles or 'dean' in roles:
            if query_for_window(PsacCommittee).filter_by(head_teacher_id=teacher.id).first():
                return True
        if _members_in_window().filter_by(teacher_id=teacher.id).first():
            return True

    # 2) Fallback: নাম দিয়ে ম্যাচ – কোনো PSAC মেম্বার/হেডের Teacher.name কি এই ইউজারের full_name এর সাথে মিলে?
    for committee in query_for_window(PsacCommittee).all():
        head = Teacher.query.get(committee.head_teacher_id)
        if head and _name_matches_user(head.name, user_name):
            return True
    for m in _members_in_window().all():
        t = Teacher.query.get(m.teacher_id)
        if t and _name_matches_user(t.name, user_name):
            return True
    return False


@self_assessment_bp.route('/')
@login_required
def index():
    """Self Assessment landing: 5 survey types (forms to be planned later)."""
    # Ensure Head has a PSAC committee so they can access (create on first visit)
    roles = parse_roles(current_user.role)
    teacher = _current_teacher()
    if teacher and ('head' in roles or 'dean' in roles):
        from extensions import db
        committee = query_for_window(PsacCommittee).filter_by(head_teacher_id=teacher.id).first()
        if not committee:
            committee = PsacCommittee(head_teacher_id=teacher.id)
            stamp_window_id(committee)
            db.session.add(committee)
            db.session.commit()
    if not is_psac_member_or_head():
        flash('Self Assessment is available only to PSAC Committee (Head, members, and ad-hoc members).', 'danger')
        return redirect(url_for('index'))
    # Links per survey type (for copy URL / view responses)
    links_by_type = {}
    for st in SURVEY_TYPES:
        links_by_type[st] = query_for_window(SurveyLink).filter_by(survey_type=st).order_by(SurveyLink.created_at.desc()).limit(20).all()
    survey_types = [
        {'id': 'alumni', 'title': 'Alumni Survey', 'icon': 'fas fa-user-graduate', 'desc': 'Survey for alumni.'},
        {'id': 'employer', 'title': 'Employer Survey', 'icon': 'fas fa-briefcase', 'desc': 'Survey for employers.'},
        {'id': 'faculty', 'title': 'Faculty Survey', 'icon': 'fas fa-chalkboard-teacher', 'desc': 'Survey for faculty.'},
        {'id': 'non_academic', 'title': 'Non Academic Staff Survey', 'icon': 'fas fa-users-cog', 'desc': 'Survey for non-academic staff.'},
        {'id': 'student', 'title': 'Student Survey', 'icon': 'fas fa-graduation-cap', 'desc': 'Survey for students.'},
    ]
    return render_template(
        'self_assessment/index.html',
        survey_types=survey_types,
        links_by_type=links_by_type,
        is_psac_head=is_psac_head(),
    )


@self_assessment_bp.route('/generate-link', methods=['POST'])
@login_required
def generate_link():
    """Create a new survey link and return public URL (Head/members only)."""
    if not is_psac_member_or_head():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    survey_type = (request.form.get('survey_type') or (request.get_json() or {}).get('survey_type') or '').strip().lower()
    if survey_type not in SURVEY_TYPES:
        return jsonify({'success': False, 'message': 'Invalid survey_type'}), 400
    from extensions import db
    committee_id = None
    teacher = _current_teacher()
    if teacher:
        c = query_for_window(PsacCommittee).filter_by(head_teacher_id=teacher.id).first()
        if c:
            committee_id = c.id
        else:
            m = _members_in_window().filter_by(teacher_id=teacher.id).first()
            if m:
                committee_id = m.committee_id
    access_code = secrets.token_urlsafe(24)
    while SurveyLink.query.filter_by(access_code=access_code).first():
        access_code = secrets.token_urlsafe(24)
    link = SurveyLink(survey_type=survey_type, access_code=access_code, committee_id=committee_id)
    stamp_window_id(link)
    db.session.add(link)
    db.session.commit()
    base = request.url_root.rstrip('/')
    public_url = f"{base}/self-assessment/s/{survey_type}/{link.access_code}"
    return jsonify({'success': True, 'url': public_url, 'link_id': link.id, 'access_code': link.access_code})


@self_assessment_bp.route('/link/<int:link_id>/delete', methods=['POST'])
@login_required
def delete_survey_link(link_id):
    """Delete a generated survey link (Head/members only). Allowed only when the link has no responses."""
    if not is_psac_member_or_head():
        flash('You are not authorized to delete links.', 'danger')
        return redirect(url_for('self_assessment.index'))
    link = get_or_404_for_window(SurveyLink, link_id)
    alumni_count = AlumniSurveyResponse.query.filter_by(survey_link_id=link.id).count()
    generic_count = SurveyResponse.query.filter_by(survey_link_id=link.id).count()
    if alumni_count > 0 or generic_count > 0:
        flash('Cannot delete: this link has responses. Remove or reassign responses first.', 'danger')
        return redirect(url_for('self_assessment.index'))
    from extensions import db
    db.session.delete(link)
    db.session.commit()
    flash('Link deleted.', 'success')
    return redirect(url_for('self_assessment.index'))


@self_assessment_bp.route('/psac-committee')
@login_required
def psac_committee():
    """Manage PSAC Committee: Head adds/removes members and ad-hoc members."""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles:
        flash('Only Head can manage PSAC Committee.', 'danger')
        return redirect(url_for('self_assessment.index'))
    teacher = _current_teacher()
    if not teacher:
        flash('Teacher profile not found.', 'danger')
        return redirect(url_for('index'))
    committee = query_for_window(PsacCommittee).filter_by(head_teacher_id=teacher.id).first()
    if not committee:
        committee = PsacCommittee(head_teacher_id=teacher.id)
        stamp_window_id(committee)
        from extensions import db
        db.session.add(committee)
        db.session.commit()
    members = PsacCommitteeMember.query.filter_by(committee_id=committee.id).order_by(PsacCommitteeMember.is_adhoc, PsacCommitteeMember.id).all()
    all_teachers = get_teachers_excluding_head()
    member_teacher_ids = {m.teacher_id for m in members}
    return render_template(
        'self_assessment/psac_committee.html',
        committee=committee,
        members=members,
        all_teachers=all_teachers,
        member_teacher_ids=member_teacher_ids,
    )


@self_assessment_bp.route('/psac-committee/add-member', methods=['POST'])
@login_required
def psac_add_member():
    """Add a teacher as member or ad-hoc member."""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    teacher = _current_teacher()
    if not teacher:
        return jsonify({'success': False, 'message': 'Teacher not found'}), 404
    committee = query_for_window(PsacCommittee).filter_by(head_teacher_id=teacher.id).first()
    if not committee:
        committee = PsacCommittee(head_teacher_id=teacher.id)
        stamp_window_id(committee)
        from extensions import db
        db.session.add(committee)
        db.session.commit()
    teacher_id = request.values.get('teacher_id')
    if not teacher_id and request.is_json:
        try:
            teacher_id = request.get_json(silent=True) or {}
            teacher_id = teacher_id.get('teacher_id')
        except Exception:
            teacher_id = None
    is_adhoc = request.values.get('is_adhoc') == '1' or request.values.get('is_adhoc') == 'true'
    if request.is_json:
        try:
            j = request.get_json(silent=True) or {}
            is_adhoc = j.get('is_adhoc', False) in (True, 1, '1', 'true')
        except Exception:
            pass
    if not teacher_id:
        return jsonify({'success': False, 'message': 'teacher_id required'}), 400
    try:
        teacher_id = int(teacher_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid teacher_id'}), 400
    if _members_in_window().filter_by(committee_id=committee.id, teacher_id=teacher_id).first():
        return jsonify({'success': False, 'message': 'Already a member'}), 400
    from extensions import db
    m = PsacCommitteeMember(committee_id=committee.id, teacher_id=teacher_id, is_adhoc=is_adhoc)
    db.session.add(m)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Member added'})


@self_assessment_bp.route('/psac-committee/remove-member/<int:member_id>', methods=['POST'])
@login_required
def psac_remove_member(member_id):
    """Remove a member from PSAC committee."""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    teacher = _current_teacher()
    if not teacher:
        return jsonify({'success': False, 'message': 'Teacher not found'}), 404
    committee = query_for_window(PsacCommittee).filter_by(head_teacher_id=teacher.id).first()
    if not committee:
        return jsonify({'success': False, 'message': 'Committee not found'}), 404
    m = _members_in_window().filter_by(id=member_id, committee_id=committee.id).first()
    if not m:
        return jsonify({'success': False, 'message': 'Member not found'}), 404
    from extensions import db
    db.session.delete(m)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Member removed'})


@self_assessment_bp.route('/s/<survey_type>/<code>', methods=['GET', 'POST'])
@csrf.exempt
def public_survey_form(survey_type, code):
    """Public survey form by link (no login). Multiple submissions per link allowed."""
    if survey_type not in SURVEY_TYPES:
        return render_template('self_assessment/survey_invalid.html'), 404
    link = _survey_link_by_code(survey_type, code)
    if not link:
        return render_template('self_assessment/survey_invalid.html'), 404
    client_ip = _client_ip()

    if request.method == 'POST':
        if survey_type == 'alumni':
            return _save_alumni_response(link, client_ip, survey_type, code)
        return _save_generic_response(link, client_ip, survey_type, code)

    template_name, pack = _survey_form_template(survey_type)
    return render_template(
        template_name,
        link=link,
        survey_type=survey_type,
        pack=pack,
    )


def _save_alumni_response(link, client_ip, survey_type, code):
    """Save alumni form and redirect to success. New form (Law Program Accreditation) saves to payload; legacy form uses columns."""
    from extensions import db
    form_version = (request.form.get('form_version') or '').strip()
    if form_version and form_version != 'legacy':
        skip = {'csrf_token', 'form_version'}
        payload = {}
        for key in request.form:
            if key in skip:
                continue
            vals = request.form.getlist(key)
            if not vals:
                continue
            payload[key] = vals[0] if len(vals) == 1 else vals
        response = AlumniSurveyResponse(
            survey_link_id=link.id,
            payload=json.dumps(payload),
            ip_address=client_ip
        )
        db.session.add(response)
        db.session.commit()
        return redirect(url_for('self_assessment.public_survey_success', survey_type=survey_type, code=code))
    # Legacy form
    name = request.form.get('name')
    batch = request.form.get('batch')
    graduation_year = request.form.get('graduation_year')
    degree_completed = request.form.getlist('degree_completed')
    current_designation = request.form.get('current_designation')
    organization = request.form.get('organization')
    employment_sector = request.form.get('employment_sector')
    employment_sector_other = request.form.get('employment_sector_other')
    if employment_sector == 'Other' and employment_sector_other:
        employment_sector = employment_sector_other
    is_enrolled = request.form.get('is_enrolled') == '1'
    enrollment_time = request.form.get('enrollment_time')
    rating_fields = [
        'curriculum_balance', 'knowledge_skills', 'critical_thinking', 'ethical_values',
        'gen_ed_usefulness', 'assessment_methods', 'moot_court', 'library_resources',
        'faculty_support', 'career_counseling', 'academic_calendar', 'admin_staff'
    ]
    ratings = {}
    for field in rating_fields:
        val = request.form.get(field)
        ratings[field] = int(val) if val and str(val).isdigit() else None
    time_to_first_job = request.form.get('time_to_first_job')
    job_market_competitiveness = request.form.get('job_market_competitiveness')
    skills_acquired = request.form.getlist('skills_acquired')
    beneficial_course_activity = request.form.get('beneficial_course_activity')
    am = request.form.get('alumni_association_member')
    alumni_association_member = True if am == '1' else (False if am == '0' else None)
    contribute_to_discipline = request.form.getlist('contributions')
    curriculum_suggestions = request.form.get('curriculum_suggestions')
    other_comments = request.form.get('other_comments')
    response = AlumniSurveyResponse(
        survey_link_id=link.id,
        name=name, batch=batch, graduation_year=graduation_year, degree_completed=degree_completed,
        current_designation=current_designation, organization=organization,
        employment_sector=employment_sector, employment_sector_other=employment_sector_other,
        is_enrolled=is_enrolled, enrollment_time=enrollment_time,
        **ratings,
        time_to_first_job=time_to_first_job, job_market_competitiveness=job_market_competitiveness,
        skills_acquired=skills_acquired,
        beneficial_course_activity=beneficial_course_activity,
        alumni_association_member=alumni_association_member,
        contribute_to_discipline=contribute_to_discipline,
        curriculum_suggestions=curriculum_suggestions,
        other_comments=other_comments,
        ip_address=client_ip
    )
    db.session.add(response)
    db.session.commit()
    return redirect(url_for('self_assessment.public_survey_success', survey_type=survey_type, code=code))


def _save_generic_response(link, client_ip, survey_type, code):
    """Save generic survey form (payload JSON) and redirect to success. Preserves multi-value fields (e.g. checkboxes)."""
    from extensions import db
    payload = {}
    for key in request.form:
        vals = request.form.getlist(key)
        if len(vals) > 1:
            payload[key] = vals
        elif len(vals) == 1:
            payload[key] = vals[0]
    resp = SurveyResponse(survey_type=survey_type, survey_link_id=link.id, payload=json.dumps(payload), ip_address=client_ip)
    db.session.add(resp)
    db.session.commit()
    return redirect(url_for('self_assessment.public_survey_success', survey_type=survey_type, code=code))


@self_assessment_bp.route('/s/<survey_type>/<code>/form-pdf')
def public_survey_form_pdf(survey_type, code):
    """Download the survey form as PDF (blank form for offline filling). No login required."""
    if survey_type not in SURVEY_TYPES:
        from flask import abort
        abort(404)
    link = _survey_link_by_code(survey_type, code)
    if not link:
        from flask import abort
        abort(404)
    font_path = _get_kalpurush_font_path()
    template_name, pack = _survey_pdf_template(survey_type)
    html_content = render_template(
        template_name,
        link=link,
        survey_type=survey_type,
        pack=pack,
        kalpurush_font_path=font_path,
    )
    try:
        from flask import Response
        import io
        from weasyprint import HTML
    except ImportError:
        return jsonify({'error': 'WeasyPrint not available'}), 503
    try:
        pdf_data = _write_self_assessment_pdf(html_content)
        pdf_buffer = io.BytesIO(pdf_data)
        pdf_data = pdf_buffer.getvalue()
    except Exception as e:
        current_app.logger.error(f"Form PDF error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    filename = f"{survey_type}_survey_form.pdf"
    resp = Response(pdf_data, mimetype='application/pdf')
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    resp.headers['Content-Length'] = str(len(pdf_data))
    return resp


@self_assessment_bp.route('/s/<survey_type>/<code>/success')
def public_survey_success(survey_type, code):
    """Public success page after survey submit."""
    link = _survey_link_by_code(survey_type, code)
    return render_template('self_assessment/survey_success.html', link=link, survey_type=survey_type)


def _can_access_responses():
    """True if current user (Head or PSAC member) can view/download responses."""
    return is_psac_member_or_head()


@self_assessment_bp.route('/survey/<survey_type>/response/<int:response_id>/view')
@login_required
def survey_response_view(survey_type, response_id):
    """View a single survey response (Head/members only)."""
    if survey_type not in SURVEY_TYPES:
        flash('Invalid survey type.', 'danger')
        return redirect(url_for('self_assessment.index'))
    if not _can_access_responses():
        flash('You are not authorized to view responses.', 'danger')
        return redirect(url_for('self_assessment.index'))
    links = query_for_window(SurveyLink).filter_by(survey_type=survey_type).order_by(SurveyLink.created_at.desc()).all()
    link_ids = [l.id for l in links]
    titles = {'alumni': 'Alumni Survey', 'employer': 'Employer Survey', 'faculty': 'Faculty Survey',
              'non_academic': 'Non Academic Staff Survey', 'student': 'Student Survey'}
    survey_title = titles.get(survey_type, survey_type)
    # Try to get serial from query param first
    requested_serial = request.args.get('serial', type=int)
    serial_no = None

    if survey_type == 'alumni':
        resp = AlumniSurveyResponse.query.get_or_404(response_id)
        if resp.survey_link_id is not None and (not link_ids or resp.survey_link_id not in link_ids):
            flash('Response not found for this survey type.', 'danger')
            return redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))
        from extensions import db
        resp.is_read = True
        db.session.commit()
        # Compute serial number if not provided
        if requested_serial:
            serial_no = requested_serial
        else:
            q = AlumniSurveyResponse.query.filter(
                AlumniSurveyResponse.survey_link_id.in_(link_ids)
            ).order_by(AlumniSurveyResponse.created_at.desc())
            id_list = [row.id for row in q.with_entities(AlumniSurveyResponse.id).all()]
            if resp.id in id_list:
                serial_no = id_list.index(resp.id) + 1

        try:
            alumni_payload = json.loads(resp.payload) if resp.payload else None
        except (TypeError, ValueError):
            alumni_payload = None
        return render_template(
            'self_assessment/response_view.html',
            survey_type=survey_type,
            survey_title=survey_title,
            response_type='alumni',
            r=resp,
            serial_no=serial_no,
            alumni_payload=alumni_payload,
        )
    resp = SurveyResponse.query.filter_by(id=response_id, survey_type=survey_type).first_or_404()
    if resp.survey_link_id not in link_ids:
        flash('Response not found for this survey type.', 'danger')
        return redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))
    from extensions import db
    resp.is_read = True
    db.session.commit()
    # Compute serial number if not provided
    if requested_serial:
        serial_no = requested_serial
    else:
        q = SurveyResponse.query.filter_by(survey_type=survey_type).filter(
            SurveyResponse.survey_link_id.in_(link_ids)
        ).order_by(SurveyResponse.created_at.desc())
        id_list = [row.id for row in q.with_entities(SurveyResponse.id).all()]
        if resp.id in id_list:
            serial_no = id_list.index(resp.id) + 1

    try:
        payload = json.loads(resp.payload or '{}')
    except (TypeError, ValueError):
        payload = {}
    return render_template(
        'self_assessment/response_view.html',
        survey_type=survey_type,
        survey_title=survey_title,
        response_type='generic',
        r=resp,
        serial_no=serial_no,
        payload=payload,
    )


@self_assessment_bp.route('/survey/<survey_type>/response/<int:response_id>/delete', methods=['POST'])
@login_required
def delete_survey_response(survey_type, response_id):
    """Delete a single survey response (Head/members only)."""
    if survey_type not in SURVEY_TYPES:
        flash('Invalid survey type.', 'danger')
        return redirect(url_for('self_assessment.index'))
    if not _can_access_responses():
        flash('You are not authorized to delete responses.', 'danger')
        return redirect(url_for('self_assessment.index'))
    from extensions import db
    links = query_for_window(SurveyLink).filter_by(survey_type=survey_type).all()
    link_ids = [l.id for l in links]
    if survey_type == 'alumni':
        resp = AlumniSurveyResponse.query.get_or_404(response_id)
        if resp.survey_link_id is not None and (not link_ids or resp.survey_link_id not in link_ids):
            flash('Response not found for this survey type.', 'danger')
            return redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))
        db.session.delete(resp)
    else:
        resp = SurveyResponse.query.filter_by(id=response_id, survey_type=survey_type).first_or_404()
        if resp.survey_link_id not in link_ids:
            flash('Response not found for this survey type.', 'danger')
            return redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))
        db.session.delete(resp)
    db.session.commit()
    flash('Response deleted.', 'success')
    return redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))


def _get_response_for_toggle(survey_type, response_id):
    """Get AlumniSurveyResponse or SurveyResponse for this survey type and id; return (resp, None) or (None, error_redirect)."""
    if survey_type not in SURVEY_TYPES:
        return None, redirect(url_for('self_assessment.index'))
    if not _can_access_responses():
        flash('You are not authorized.', 'danger')
        return None, redirect(url_for('self_assessment.index'))
    links = query_for_window(SurveyLink).filter_by(survey_type=survey_type).all()
    link_ids = [l.id for l in links]
    if survey_type == 'alumni':
        resp = AlumniSurveyResponse.query.get_or_404(response_id)
        if resp.survey_link_id is not None and (not link_ids or resp.survey_link_id not in link_ids):
            flash('Response not found for this survey type.', 'danger')
            return None, redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))
    else:
        resp = SurveyResponse.query.filter_by(id=response_id, survey_type=survey_type).first_or_404()
        if resp.survey_link_id not in link_ids:
            flash('Response not found for this survey type.', 'danger')
            return None, redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))
    return resp, None


@self_assessment_bp.route('/survey/<survey_type>/response/<int:response_id>/toggle-read', methods=['POST'])
@login_required
def survey_response_toggle_read(survey_type, response_id):
    """Toggle read/unread for a response (Head/members only)."""
    resp, err = _get_response_for_toggle(survey_type, response_id)
    if err:
        return err
    from extensions import db
    resp.is_read = not resp.is_read
    db.session.commit()
    flash('Marked as ' + ('read' if resp.is_read else 'unread') + '.', 'success')
    return redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))


@self_assessment_bp.route('/survey/<survey_type>/response/<int:response_id>/toggle-star', methods=['POST'])
@login_required
def survey_response_toggle_star(survey_type, response_id):
    """Toggle starred (important) for a response (Head/members only)."""
    resp, err = _get_response_for_toggle(survey_type, response_id)
    if err:
        return err
    from extensions import db
    resp.is_starred = not resp.is_starred
    db.session.commit()
    flash('Marked as ' + ('important' if resp.is_starred else 'not important') + '.', 'success')
    return redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))


@self_assessment_bp.route('/survey/<survey_type>/responses/delete-all', methods=['POST'])
@login_required
def delete_all_survey_responses(survey_type):
    """Delete all responses for this survey type (Head/members only)."""
    if survey_type not in SURVEY_TYPES:
        flash('Invalid survey type.', 'danger')
        return redirect(url_for('self_assessment.index'))
    if not _can_access_responses():
        flash('You are not authorized to delete responses.', 'danger')
        return redirect(url_for('self_assessment.index'))
    from extensions import db
    links = query_for_window(SurveyLink).filter_by(survey_type=survey_type).all()
    link_ids = [l.id for l in links]
    if not link_ids:
        flash('No responses to delete.', 'info')
        return redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))
    if survey_type == 'alumni':
        count = AlumniSurveyResponse.query.filter(
            AlumniSurveyResponse.survey_link_id.in_(link_ids)
        ).delete(synchronize_session=False)
    else:
        count = SurveyResponse.query.filter_by(survey_type=survey_type).filter(
            SurveyResponse.survey_link_id.in_(link_ids)
        ).delete(synchronize_session=False)
    db.session.commit()
    flash(f'{count} response(s) deleted.', 'success')
    return redirect(url_for('self_assessment.survey_responses_list', survey_type=survey_type))


@self_assessment_bp.route('/survey/<survey_type>/responses')
@login_required
def survey_responses_list(survey_type):
    """List responses for a survey type (Head/members only)."""
    if survey_type not in SURVEY_TYPES:
        flash('Invalid survey type.', 'danger')
        return redirect(url_for('self_assessment.index'))
    if not _can_access_responses():
        flash('You are not authorized to view responses.', 'danger')
        return redirect(url_for('self_assessment.index'))
    links = query_for_window(SurveyLink).filter_by(survey_type=survey_type).order_by(SurveyLink.created_at.desc()).all()
    link_ids = [l.id for l in links]
    if survey_type == 'alumni':
        if not link_ids:
            responses = []
        else:
            responses = AlumniSurveyResponse.query.filter(
                AlumniSurveyResponse.survey_link_id.in_(link_ids)
            ).order_by(AlumniSurveyResponse.created_at.desc()).all()
        response_type = 'alumni'
    else:
        if not link_ids:
            responses = []
        else:
            responses = SurveyResponse.query.filter_by(survey_type=survey_type).filter(
                SurveyResponse.survey_link_id.in_(link_ids)
            ).order_by(SurveyResponse.created_at.desc()).all()
        response_type = 'generic'
    titles = {'alumni': 'Alumni Survey', 'employer': 'Employer Survey', 'faculty': 'Faculty Survey',
              'non_academic': 'Non Academic Staff Survey', 'student': 'Student Survey'}
    return render_template(
        'self_assessment/responses_list.html',
        survey_type=survey_type,
        survey_title=titles.get(survey_type, survey_type),
        links=links,
        responses=responses,
        response_type=response_type,
    )


def _survey_responses_for_type(survey_type):
    links = query_for_window(SurveyLink).filter_by(survey_type=survey_type).order_by(SurveyLink.created_at.desc()).all()
    link_ids = [l.id for l in links]
    if not link_ids:
        return []
    if survey_type == 'alumni':
        return AlumniSurveyResponse.query.filter(
            AlumniSurveyResponse.survey_link_id.in_(link_ids)
        ).order_by(AlumniSurveyResponse.created_at.desc()).all()
    return SurveyResponse.query.filter_by(survey_type=survey_type).filter(
        SurveyResponse.survey_link_id.in_(link_ids)
    ).order_by(SurveyResponse.created_at.desc()).all()


@self_assessment_bp.route('/survey/<survey_type>/insights', methods=['GET', 'POST'])
@login_required
def survey_insights(survey_type):
    if survey_type not in SURVEY_TYPES:
        flash('Invalid survey type.', 'danger')
        return redirect(url_for('self_assessment.index'))
    if not _can_access_responses():
        flash('You are not authorized to view responses.', 'danger')
        return redirect(url_for('self_assessment.index'))

    from datetime import datetime
    from extensions import db

    titles = {'alumni': 'Alumni Survey', 'employer': 'Employer Survey', 'faculty': 'Faculty Survey',
              'non_academic': 'Non Academic Staff Survey', 'student': 'Student Survey'}
    window_id = get_effective_window_id()
    snapshot = SurveyInsightSnapshot.query.filter_by(
        survey_type=survey_type, window_id=window_id
    ).order_by(SurveyInsightSnapshot.generated_at.desc()).first()
    summary = None
    if snapshot and snapshot.summary_json:
        try:
            summary = json.loads(snapshot.summary_json)
        except (json.JSONDecodeError, TypeError):
            summary = None

    if request.method == 'POST':
        responses = _survey_responses_for_type(survey_type)
        try:
            from utils.ai.client import AIClientError, get_active_provider_setting, user_facing_generation_error
            from utils.ai.survey_summary import summarize_survey_comments
            from utils.ai.session_utils import reset_db_session

            get_active_provider_setting()
            summary = summarize_survey_comments(survey_type, responses)
            reset_db_session()
            row = SurveyInsightSnapshot(
                survey_type=survey_type,
                window_id=window_id,
                summary_json=json.dumps(summary, ensure_ascii=False),
                generated_at=datetime.utcnow(),
                generated_by_user_id=getattr(current_user, 'id', None),
            )
            db.session.add(row)
            db.session.commit()
            snapshot = row
            flash('থিম সারাংশ তৈরি হয়েছে।', 'success')
        except AIClientError as exc:
            flash(str(exc), 'danger')
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f'SAR insight failed for {survey_type}: {exc}', exc_info=True)
            from utils.ai.client import user_facing_generation_error
            flash(user_facing_generation_error(exc), 'danger')
        return redirect(url_for('self_assessment.survey_insights', survey_type=survey_type))

    return render_template(
        'self_assessment/survey_insights.html',
        survey_type=survey_type,
        survey_title=titles.get(survey_type, survey_type),
        summary=summary,
        snapshot=snapshot,
    )


@self_assessment_bp.route('/survey/<survey_type>/responses/pdf')
@login_required
def survey_responses_pdf(survey_type):
    """Download all responses for a survey type as one PDF (Head/members only)."""
    if survey_type not in SURVEY_TYPES:
        from flask import abort
        abort(404)
    if not _can_access_responses():
        from flask import abort
        abort(403)
    links = query_for_window(SurveyLink).filter_by(survey_type=survey_type).order_by(SurveyLink.created_at.desc()).all()
    link_ids = [l.id for l in links]
    titles = {'alumni': 'Alumni Survey', 'employer': 'Employer Survey', 'faculty': 'Faculty Survey',
              'non_academic': 'Non Academic Staff Survey', 'student': 'Student Survey'}
    survey_title = titles.get(survey_type, survey_type)
    only_starred = request.args.get('only_starred', type=int) == 1
    font_path = _get_kalpurush_font_path()
    if survey_type == 'alumni':
        if link_ids:
            q = AlumniSurveyResponse.query.filter(
                AlumniSurveyResponse.survey_link_id.in_(link_ids)
            )
            if only_starred:
                q = q.filter_by(is_starred=True)
            responses = q.order_by(AlumniSurveyResponse.created_at.desc()).all()
        else:
            responses = []
        if responses:
            # Merge one PDF per response so page numbers restart (1, 2, …) for each response
            try:
                import io
                try:
                    from PyPDF2 import PdfMerger
                except ImportError:
                    from PyPDF2 import PdfFileMerger as PdfMerger
            except ImportError:
                msg = 'PyPDF2 not installed. Install it for "Download All" PDF: pip install PyPDF2'
                if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json':
                    return jsonify({'error': msg}), 503
                return f'<html><body style="font-family:sans-serif;padding:2em;"><h2>Download All PDF</h2><p>{msg}</p><p><a href="{url_for("self_assessment.survey_responses_list", survey_type=survey_type)}">Back to responses</a></p></body></html>', 503
            try:
                merger = PdfMerger()
                for idx, resp in enumerate(responses, start=1):
                    pdf_bytes = _get_alumni_pdf_bytes(resp, serial_no=idx)
                    if pdf_bytes:
                        merger.append(io.BytesIO(pdf_bytes))
                out = io.BytesIO()
                merger.write(out)
                pdf_data = out.getvalue()
                merger.close()
                suffix = "starred_responses" if only_starred else "all_responses"
                filename = f"{survey_type}_survey_{suffix}.pdf"
                from flask import Response
                resp = Response(pdf_data, mimetype='application/pdf')
                resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
                resp.headers['Content-Length'] = str(len(pdf_data))
                return resp
            except Exception as e:
                current_app.logger.warning('Alumni all-responses PDF merge failed: %s', e, exc_info=True)
                msg = str(e) or 'PDF merge failed'
                if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json':
                    return jsonify({'error': msg}), 500
                return f'<html><body style="font-family:sans-serif;padding:2em;"><h2>Download All PDF</h2><p>{msg}</p><p><a href="{url_for("self_assessment.survey_responses_list", survey_type=survey_type)}">Back to responses</a></p></body></html>', 500
        # No responses: single PDF with "No responses" message
        html_content = render_template(
            'self_assessment/alumni_all_responses_pdf.html',
            responses=[],
            kalpurush_font_path=font_path,
        )
    else:
        if link_ids:
            q = SurveyResponse.query.filter_by(survey_type=survey_type).filter(
                SurveyResponse.survey_link_id.in_(link_ids)
            )
            if only_starred:
                q = q.filter_by(is_starred=True)
            responses = q.order_by(SurveyResponse.created_at.desc()).all()
        else:
            responses = []
        if responses:
            # Merge one PDF per response (same design as Alumni: page numbers restart per response)
            try:
                import io
                try:
                    from PyPDF2 import PdfMerger
                except ImportError:
                    from PyPDF2 import PdfFileMerger as PdfMerger
            except ImportError:
                msg = 'PyPDF2 not installed. Install it for "Download All" PDF: pip install PyPDF2'
                if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json':
                    return jsonify({'error': msg}), 503
                return f'<html><body style="font-family:sans-serif;padding:2em;"><h2>Download All PDF</h2><p>{msg}</p><p><a href="{url_for("self_assessment.survey_responses_list", survey_type=survey_type)}">Back to responses</a></p></body></html>', 503
            try:
                merger = PdfMerger()
                for idx, resp in enumerate(responses, start=1):
                    pdf_bytes = _get_generic_survey_pdf_bytes(resp, serial_no=idx)
                    if pdf_bytes:
                        merger.append(io.BytesIO(pdf_bytes))
                out = io.BytesIO()
                merger.write(out)
                pdf_data = out.getvalue()
                merger.close()
                suffix = "starred_responses" if only_starred else "all_responses"
                filename = f"{survey_type}_survey_{suffix}.pdf"
                from flask import Response
                resp = Response(pdf_data, mimetype='application/pdf')
                resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
                resp.headers['Content-Length'] = str(len(pdf_data))
                return resp
            except Exception as e:
                current_app.logger.warning('Generic all-responses PDF merge failed: %s', e, exc_info=True)
                msg = str(e) or 'PDF merge failed'
                if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json':
                    return jsonify({'error': msg}), 500
                return f'<html><body style="font-family:sans-serif;padding:2em;"><h2>Download All PDF</h2><p>{msg}</p><p><a href="{url_for("self_assessment.survey_responses_list", survey_type=survey_type)}">Back to responses</a></p></body></html>', 500
        # No responses: single PDF with "No responses" message (same pattern as alumni)
        html_content = render_template(
            'self_assessment/generic_all_responses_pdf.html',
            survey_type=survey_type,
            survey_title=survey_title,
            responses=[],
            kalpurush_font_path=font_path,
        )
    try:
        from flask import current_app, Response
        import io
        from weasyprint import HTML
    except ImportError:
        return jsonify({'error': 'WeasyPrint not available'}), 503
    try:
        pdf_data = _write_self_assessment_pdf(html_content)
        pdf_buffer = io.BytesIO(pdf_data)
        pdf_data = pdf_buffer.getvalue()
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"All responses PDF error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    filename = f"{survey_type}_survey_all_responses.pdf"
    resp = Response(pdf_data, mimetype='application/pdf')
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    resp.headers['Content-Length'] = str(len(pdf_data))
    return resp


@self_assessment_bp.route('/survey/alumni/response/<int:response_id>/pdf')
@login_required
def alumni_response_pdf(response_id):
    """Download a single Alumni survey response as PDF (Head/members only)."""
    if not _can_access_responses():
        from flask import abort
        abort(403)
    resp = AlumniSurveyResponse.query.get_or_404(response_id)
    if resp.survey_link_id:
        link = get_for_window(SurveyLink, resp.survey_link_id)
        if not link or link.survey_type != 'alumni':
            from flask import abort
            abort(404)
    # Determine serial number consistent with list view (newest first)
    requested_serial = request.args.get('serial', type=int)
    serial_no = None
    if requested_serial:
        serial_no = requested_serial
    else:
        links = query_for_window(SurveyLink).filter_by(survey_type='alumni').order_by(SurveyLink.created_at.desc()).all()
        link_ids = [l.id for l in links]
        if link_ids:
            q = AlumniSurveyResponse.query.filter(
                AlumniSurveyResponse.survey_link_id.in_(link_ids)
            ).order_by(AlumniSurveyResponse.created_at.desc())
            id_list = [row.id for row in q.with_entities(AlumniSurveyResponse.id).all()]
            if resp.id in id_list:
                serial_no = id_list.index(resp.id) + 1

    try:
        out = _render_alumni_pdf(resp, serial_no=serial_no)
        return out
    except Exception as e:
        current_app.logger.error(f"Alumni response PDF error: {e}", exc_info=True)
        back_url = url_for('self_assessment.survey_responses_list', survey_type='alumni')
        if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json':
            return jsonify({'error': 'PDF generation failed', 'detail': str(e)}), 500
        return _pdf_fallback_html('alumni', response_id, back_url), 503


@self_assessment_bp.route('/survey/<survey_type>/response/<int:response_id>/pdf')
@login_required
def generic_response_pdf(survey_type, response_id):
    """Download a single generic survey response as PDF (Head/members only)."""
    if survey_type not in SURVEY_TYPES or survey_type == 'alumni':
        from flask import abort
        abort(404)
    if not _can_access_responses():
        from flask import abort
        abort(403)
    resp = SurveyResponse.query.filter_by(id=response_id, survey_type=survey_type).first_or_404()
    # Determine serial number consistent with list view (newest first)
    requested_serial = request.args.get('serial', type=int)
    serial_no = None
    if requested_serial:
        serial_no = requested_serial
    else:
        links = query_for_window(SurveyLink).filter_by(survey_type=survey_type).order_by(SurveyLink.created_at.desc()).all()
        link_ids = [l.id for l in links]
        if link_ids:
            q = SurveyResponse.query.filter_by(survey_type=survey_type).filter(
                SurveyResponse.survey_link_id.in_(link_ids)
            ).order_by(SurveyResponse.created_at.desc())
            id_list = [row.id for row in q.with_entities(SurveyResponse.id).all()]
            if resp.id in id_list:
                serial_no = id_list.index(resp.id) + 1
    try:
        out = _render_generic_pdf(resp, serial_no=serial_no)
        return out
    except Exception as e:
        current_app.logger.error(f"Survey response PDF error: {e}", exc_info=True)
        back_url = url_for('self_assessment.survey_responses_list', survey_type=survey_type)
        if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json':
            return jsonify({'error': 'PDF generation failed', 'detail': str(e)}), 500
        return _pdf_fallback_html(survey_type, response_id, back_url), 503


def _get_alumni_pdf_bytes(alumni_response, serial_no=None):
    """Return PDF bytes for one AlumniSurveyResponse (for merging into all-responses PDF).

    serial_no is an optional 1-based index used in the PDF header when generating
    merged "Download All" PDFs so that each response gets the correct serial number.
    """
    import io
    try:
        from weasyprint import HTML
    except ImportError:
        return None
    try:
        payload = json.loads(alumni_response.payload) if alumni_response.payload else None
        html_content = render_template(
            'self_assessment/alumni_response_pdf.html',
            r=alumni_response,
            payload=payload,
            serial_no=serial_no,
            kalpurush_font_path=_get_kalpurush_font_path(),
        )
        pdf_data = _write_self_assessment_pdf(html_content)
        pdf_buffer = io.BytesIO(pdf_data)
        return pdf_buffer.getvalue()
    except Exception as e:
        current_app.logger.error(f"Alumni response PDF error: {e}", exc_info=True)
        return None


def _pdf_fallback_html(survey_type, response_id, back_url):
    """HTML when PDF generation fails: link to view response + Print to PDF instructions."""
    view_url = url_for('self_assessment.survey_response_view', survey_type=survey_type, response_id=response_id)
    return (
        '<html><body style="font-family:sans-serif;padding:2em;max-width:600px;">'
        '<h2>PDF ডাউনলোড এই সার্ভারে উপলব্ধ নয়</h2>'
        '<p>রেসপন্সটি ব্রাউজারে খুলে <strong>Print (Ctrl+P)</strong> চাপুন এবং <strong>Save as PDF</strong> বা "প্রিন্ট করুন" থেকে PDF হিসেবে সেভ করুন।</p>'
        f'<p><a href="{view_url}" style="display:inline-block;padding:0.5em 1em;background:#0d6efd;color:white;text-decoration:none;border-radius:6px;">রেসপন্স দেখুন ও প্রিন্ট করুন</a></p>'
        f'<p><a href="{back_url}">Responses তালিকায় ফিরে যান</a></p>'
        '</body></html>'
    )


def _render_alumni_pdf(alumni_response, serial_no=None):
    """Generate PDF for one AlumniSurveyResponse using WeasyPrint.

    serial_no is a 1-based index matching the frontend list (newest first).
    """
    from flask import Response
    back_url = url_for('self_assessment.survey_responses_list', survey_type='alumni')
    try:
        pdf_bytes = _get_alumni_pdf_bytes(alumni_response, serial_no=serial_no)
        if pdf_bytes is None:
            return _pdf_fallback_html('alumni', alumni_response.id, back_url), 503
        effective_serial = serial_no or alumni_response.id
        filename = f"alumni_survey_response_{effective_serial}.pdf"
        resp = Response(pdf_bytes, mimetype='application/pdf')
        resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        resp.headers['Content-Length'] = str(len(pdf_bytes))
        return resp
    except Exception as e:
        current_app.logger.error(f"Alumni PDF render error: {e}", exc_info=True)
        return _pdf_fallback_html('alumni', alumni_response.id, back_url), 503


def _get_generic_survey_pdf_bytes(survey_response, serial_no=None):
    """Return PDF bytes for one SurveyResponse using type-specific template (for single PDF or merge).

    serial_no is an optional 1-based index used in the PDF header when generating
    merged "Download All" PDFs so that each response gets the correct serial number.
    """
    import io
    try:
        from weasyprint import HTML
    except ImportError:
        return None
    try:
        payload = json.loads(survey_response.payload or '{}')
    except (TypeError, ValueError):
        payload = {}
    template_map = {
        'employer': 'self_assessment/employer_response_pdf.html',
        'student': 'self_assessment/student_response_pdf.html',
        'faculty': 'self_assessment/faculty_response_pdf.html',
        'non_academic': 'self_assessment/non_academic_response_pdf.html',
    }
    template_name = template_map.get(survey_response.survey_type, 'self_assessment/generic_response_pdf.html')
    try:
        html_content = render_template(
            template_name,
            r=survey_response,
            payload=payload,
            serial_no=serial_no,
            kalpurush_font_path=_get_kalpurush_font_path(),
        )
        pdf_data = _write_self_assessment_pdf(html_content)
        pdf_buffer = io.BytesIO(pdf_data)
        return pdf_buffer.getvalue()
    except Exception as e:
        current_app.logger.error(f"Survey response PDF error: {e}", exc_info=True)
        return None


def _render_generic_pdf(survey_response, serial_no=None):
    """Generate PDF for one SurveyResponse (payload JSON) using type-specific template (same design as Alumni).

    serial_no is a 1-based index matching the frontend list (newest first).
    """
    from flask import current_app, Response
    back_url = url_for('self_assessment.survey_responses_list', survey_type=survey_response.survey_type)
    try:
        pdf_bytes = _get_generic_survey_pdf_bytes(survey_response, serial_no=serial_no)
        if pdf_bytes is None:
            return _pdf_fallback_html(survey_response.survey_type, survey_response.id, back_url), 503
        effective_serial = serial_no or survey_response.id
        filename = f"{survey_response.survey_type}_survey_response_{effective_serial}.pdf"
        resp = Response(pdf_bytes, mimetype='application/pdf')
        resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        resp.headers['Content-Length'] = str(len(pdf_bytes))
        return resp
    except Exception as e:
        current_app.logger.error(f"Generic PDF render error: {e}", exc_info=True)
        return _pdf_fallback_html(survey_response.survey_type, survey_response.id, back_url), 503


@self_assessment_bp.route('/alumni-survey', methods=['GET', 'POST'])
def alumni_survey():
    """Public Alumni Survey form (Law Program Accreditation). No link: survey_link_id=None."""
    if request.method == 'POST':
        from extensions import db
        from .models import AlumniSurveyResponse
        if request.form.get('form_version') == 'law_accreditation':
            payload = {}
            for i in range(1, 22):
                val = request.form.get(f'q{i}')
                payload[f'q{i}'] = int(val) if val and str(val).isdigit() and 1 <= int(val) <= 5 else None
            for i in range(22, 26):
                payload[f'q{i}'] = (request.form.get(f'q{i}') or '').strip() or None
            payload['name'] = (request.form.get('name') or '').strip() or None
            payload['batch'] = (request.form.get('batch') or '').strip() or None
            payload['graduation_year'] = (request.form.get('graduation_year') or '').strip() or None
            response = AlumniSurveyResponse(survey_link_id=None, payload=json.dumps(payload), ip_address=request.remote_addr)
            db.session.add(response)
            db.session.commit()
            return redirect(url_for('self_assessment.alumni_survey_success'))
        # Legacy form (no link)
        name = request.form.get('name')
        batch = request.form.get('batch')
        graduation_year = request.form.get('graduation_year')
        degree_completed = request.form.getlist('degree_completed')
        current_designation = request.form.get('current_designation')
        organization = request.form.get('organization')
        employment_sector = request.form.get('employment_sector')
        employment_sector_other = request.form.get('employment_sector_other')
        if employment_sector == 'Other' and employment_sector_other:
            employment_sector = employment_sector_other
        is_enrolled = request.form.get('is_enrolled') == '1'
        enrollment_time = request.form.get('enrollment_time')
        ratings = {}
        rating_fields = [
            'curriculum_balance', 'knowledge_skills', 'critical_thinking', 'ethical_values',
            'gen_ed_usefulness', 'assessment_methods', 'moot_court', 'library_resources',
            'faculty_support', 'career_counseling', 'academic_calendar', 'admin_staff'
        ]
        for field in rating_fields:
            val = request.form.get(field)
            ratings[field] = int(val) if val and val.isdigit() else None
        time_to_first_job = request.form.get('time_to_first_job')
        job_market_competitiveness = request.form.get('job_market_competitiveness')
        skills_acquired = request.form.getlist('skills_acquired')
        beneficial_course_activity = request.form.get('beneficial_course_activity')
        am = request.form.get('alumni_association_member')
        alumni_association_member = True if am == '1' else (False if am == '0' else None)
        contribute_to_discipline = request.form.getlist('contributions')
        curriculum_suggestions = request.form.get('curriculum_suggestions')
        other_comments = request.form.get('other_comments')
        response = AlumniSurveyResponse(
            name=name,
            batch=batch,
            graduation_year=graduation_year,
            degree_completed=degree_completed,
            current_designation=current_designation,
            organization=organization,
            employment_sector=employment_sector,
            employment_sector_other=employment_sector_other,
            is_enrolled=is_enrolled,
            enrollment_time=enrollment_time,
            **ratings,
            time_to_first_job=time_to_first_job,
            job_market_competitiveness=job_market_competitiveness,
            skills_acquired=skills_acquired,
            beneficial_course_activity=beneficial_course_activity,
            alumni_association_member=alumni_association_member,
            contribute_to_discipline=contribute_to_discipline,
            curriculum_suggestions=curriculum_suggestions,
            other_comments=other_comments,
            ip_address=request.remote_addr
        )
        db.session.add(response)
        db.session.commit()
        
        return redirect(url_for('self_assessment.alumni_survey_success'))

    template_name, pack = _survey_form_template('alumni')
    return render_template(template_name, pack=pack, survey_type='alumni')


@self_assessment_bp.route('/alumni-survey/success')
def alumni_survey_success():
    """Public success page for Alumni Survey."""
    return render_template('self_assessment/alumni_survey_success.html')
