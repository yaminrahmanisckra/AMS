"""Teacher HITL case builder and student gateway for the Mock Trial Simulator."""
from datetime import datetime

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from role_utils import has_teacher_privileges, parse_roles
from utils.ownership import resolve_caller_teacher
from utils.public_errors import flash_exception
from utils.window_utils import filter_by_window_sessions, get_or_404_for_window, query_for_window

from blueprints.class_management.models import ClassStudent, Session, StudentNotification

from . import mock_trial_simulator_bp
from .pdf import (
    accused_section,
    deny_paper,
    exhibit_section,
    factsheet_section,
    fir_section,
    normalize_side,
    paper_filename,
    render_paper_response,
    vakalatnama_section,
    witness_card_section,
    witness_list_section,
)
from .models import (
    CASE_TYPES,
    CASE_TYPE_LABELS,
    WITNESS_ROLES,
    PHASE_DISCOVERY,
    PHASE_LABELS,
    PHASE_QUIZ,
    SIDE_DEFENCE,
    SIDE_PROSECUTION,
    WITNESS_EXPERT,
    WITNESS_IO,
    STATUS_ARCHIVED,
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    MockTrialCase,
    MockTrialPetition,
    add_manual_witness,
    apply_cast,
    apply_generated_pack,
    delete_case_witness,
    build_discovery_quiz,
    filter_mock_trial_sessions,
    next_quiz_id,
    normalize_quiz_question,
    public_quiz,
    resolve_cast,
    grade_discovery_quiz,
    session_is_mock_trial_enabled,
    team_for_side,
    locked_witness_unlocks,
    unlocked_exhibits_for_score,
    unlocked_witnesses_for_score,
    get_or_create_witness_paper,
    MockTrialWitnessPaper,
)
from .paper_templates import get_template, paper_rows_for_witness, template_fields

try:
    from blueprints.student_management.models import Student
except ImportError:
    Student = None

try:
    from user_models import User
except ImportError:
    User = None


def _roles():
    return parse_roles(getattr(current_user, 'role', None))


def _is_student():
    return 'student' in _roles() and not has_teacher_privileges(current_user)


def _guard():
    if _is_student():
        from utils.dashboard_settings import require_student_dashboard_card
        return require_student_dashboard_card('mock_trial_simulator')
    if has_teacher_privileges(current_user):
        from utils.dashboard_settings import require_teacher_dashboard_card
        return require_teacher_dashboard_card('mock_trial_simulator')
    flash('Mock Trial Simulator is available for teachers and students.', 'warning')
    return redirect(url_for('index'))


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
        flash('You can manage mock trials only for your own courses.', 'danger')
        return None, None
    if not session_is_mock_trial_enabled(session_obj):
        flash('Mock Trial is not enabled for this course. Ask an administrator to turn it on.', 'warning')
        return None, None
    return session_obj, teacher


def _case_for_teacher(case_id):
    case = MockTrialCase.query.get_or_404(case_id)
    session_obj, teacher = _owned_session(case.session_id)
    if not session_obj:
        return None, None, None
    return case, session_obj, teacher


def _teacher_sessions(teacher):
    sessions = (
        query_for_window(Session)
        .filter_by(teacher_id=teacher.id, archived=False)
        .order_by(Session.created_at.desc())
        .all()
    )
    return filter_mock_trial_sessions(sessions)


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
        current_app.logger.exception('Window filter failed for mock trial roster')
    return {row.session_id: row for row in query.all()}


def _roster_label(row):
    name = (getattr(row, 'name', None) or '').strip()
    sid = (getattr(row, 'student_id', None) or '').strip()
    if name and sid and name != sid:
        return f'{name} ({sid})'
    return name or sid or 'Student'


def _notify_role(case, student_id, role_label):
    if User is None or not student_id:
        return
    user = User.query.filter_by(username=student_id).first()
    if not user:
        return
    window_id = case.session.window_id if case.session else None
    db.session.add(StudentNotification(
        user_id=user.id,
        type='mock_trial',
        title=f'Mock trial role: {role_label} — {(case.title or "Case")[:60]}',
        link_url=url_for('mock_trial_simulator.student_case', case_id=case.id),
        window_id=window_id,
    ))


def _team_petition(case, team, petition_type=None, create=False):
    if not case or not team:
        return None
    types = MockTrialPetition.types_for_side(team.side)
    if petition_type:
        types = (petition_type,) + tuple(t for t in types if t != petition_type)
    row = (
        MockTrialPetition.query
        .filter_by(case_id=case.id, team_id=team.id)
        .filter(MockTrialPetition.petition_type.in_(types))
        .order_by(MockTrialPetition.id.desc())
        .first()
    )
    if row is None and create:
        row = MockTrialPetition(
            case_id=case.id,
            team_id=team.id,
            petition_type=MockTrialPetition.TYPE_VAKALATNAMA,
            status=MockTrialPetition.STATUS_DRAFT,
        )
        db.session.add(row)
        db.session.flush()
    return row


def _assigned_side_teams(case):
    teams = []
    for side in (SIDE_PROSECUTION, SIDE_DEFENCE):
        team = team_for_side(case, side)
        if team and team.members:
            teams.append(team)
    return teams


def _vakalatnamas_accepted(case):
    teams = _assigned_side_teams(case)
    if not teams:
        return False
    for team in teams:
        petition = _team_petition(case, team)
        if not petition or petition.status != MockTrialPetition.STATUS_ACCEPTED:
            return False
    return True


def _notify_published(case):
    if User is None:
        return
    link = url_for('mock_trial_simulator.student_case', case_id=case.id)
    window_id = case.session.window_id if case.session else None
    title = f"Mock trial: {(case.title or 'New case')[:80]}"
    seen = set()
    for stu in _roster(case.session_id):
        if stu.student_id in seen:
            continue
        seen.add(stu.student_id)
        user = User.query.filter_by(username=stu.student_id).first()
        if not user:
            continue
        db.session.add(StudentNotification(
            user_id=user.id,
            type='mock_trial',
            title=title,
            link_url=link,
            window_id=window_id,
        ))


def _read_create_form():
    title = (request.form.get('title') or '').strip()
    case_type = (request.form.get('case_type') or 'murder').strip()
    if case_type not in CASE_TYPE_LABELS:
        case_type = 'murder'
    extra_brief = (request.form.get('extra_brief') or '').strip()
    if not title:
        title = CASE_TYPE_LABELS[case_type]
    return title[:300], case_type, extra_brief or None


def _form_witness_count(name, current=None):
    raw = request.form.get(name)
    if raw is None:
        return current
    raw = str(raw).strip()
    if not raw:
        return None
    try:
        return max(1, min(12, int(raw)))
    except (TypeError, ValueError):
        return current


TEACHER_PANELS = frozenset({
    'settings', 'pack', 'cast', 'gateway', 'quiz', 'witnesses', 'exhibits', 'papers',
})
STUDENT_PANELS = frozenset({
    'wait', 'brief', 'vakalat', 'quiz', 'witnesses', 'exhibits',
    'character', 'notes', 'papers', 'paper', 'provisions', 'interview', 'trial',
})
ACTION_PANEL = {
    'generate': 'pack',
    'publish': 'pack',
    'unpublish': 'pack',
    'assign': 'cast',
    'accept_petition': 'gateway',
    'reject_petition': 'gateway',
    'save_quiz': 'quiz',
    'add_quiz_question': 'quiz',
    'generate_quiz': 'quiz',
    'save_petition': 'vakalat',
    'submit_petition': 'vakalat',
    'submit_quiz': 'quiz',
    'save_witness_notes': 'character',
    'save_witness_paper': 'paper',
    'add_witness': 'witnesses',
    'delete_witness': 'witnesses',
}


def _requested_panel(allowed):
    raw = (request.form.get('panel') or request.args.get('panel') or '').strip()
    if raw in allowed:
        return raw
    inferred = ACTION_PANEL.get((request.form.get('action') or '').strip())
    if inferred in allowed:
        return inferred
    return ''


def _teacher_case_url(case_id, panel=None):
    panel = _requested_panel(TEACHER_PANELS) if panel is None else panel
    if panel:
        return url_for('mock_trial_simulator.teacher_case', case_id=case_id, panel=panel)
    return url_for('mock_trial_simulator.teacher_case', case_id=case_id)


def _student_case_url(case_id, panel=None, template=None):
    panel = _requested_panel(STUDENT_PANELS) if panel is None else panel
    query = {}
    if panel:
        query['panel'] = panel
    key = (template if template is not None else (request.form.get('template_key') or request.args.get('template') or '')).strip()
    if key:
        query['template'] = key
    return url_for('mock_trial_simulator.student_case', case_id=case_id, **query)


def _apply_case_edits(case):
    if 'title' in request.form:
        title = (request.form.get('title') or '').strip()
        if title:
            case.title = title[:300]
    if 'case_type' in request.form:
        case_type = (request.form.get('case_type') or case.case_type).strip()
        if case_type in CASE_TYPE_LABELS:
            case.case_type = case_type
    if 'extra_brief' in request.form:
        case.extra_brief = (request.form.get('extra_brief') or '').strip() or None
    if 'prosecution_witness_count' in request.form:
        case.prosecution_witness_count = _form_witness_count(
            'prosecution_witness_count', case.prosecution_witness_count,
        )
    if 'defence_witness_count' in request.form:
        case.defence_witness_count = _form_witness_count(
            'defence_witness_count', case.defence_witness_count,
        )

    fact_keys = ('incident_summary', 'date_time', 'place', 'legal_provisions', 'facts')
    if any(key in request.form for key in fact_keys):
        sheet = case.factsheet()
        if 'incident_summary' in request.form:
            sheet['incident_summary'] = (request.form.get('incident_summary') or '').strip()
        if 'date_time' in request.form:
            sheet['date_time'] = (request.form.get('date_time') or '').strip()
        if 'place' in request.form:
            sheet['place'] = (request.form.get('place') or '').strip()
        if 'legal_provisions' in request.form:
            sheet['legal_provisions'] = [
                line.strip()
                for line in (request.form.get('legal_provisions') or '').splitlines()
                if line.strip()
            ]
        if 'facts' in request.form:
            sheet['facts'] = [
                line.strip()
                for line in (request.form.get('facts') or '').splitlines()
                if line.strip()
            ]
        sheet['title'] = case.title
        sheet['case_type'] = case.case_type
        sheet.setdefault('accused', [])
        sheet.setdefault('victim', {})
        case.set_factsheet(sheet)
    if any(key in request.form for key in ('fir_police_station', 'fir_gd_entry', 'fir_narrative')):
        fir = case.fir()
        if 'fir_police_station' in request.form:
            fir['police_station'] = (request.form.get('fir_police_station') or '').strip()
        if 'fir_gd_entry' in request.form:
            fir['gd_entry'] = (request.form.get('fir_gd_entry') or '').strip()
        if 'fir_narrative' in request.form:
            fir['narrative'] = (request.form.get('fir_narrative') or '').strip()
        case.set_fir(fir)
    if 'accused_narrative' in request.form:
        case.set_accused_statement({
            'narrative': (request.form.get('accused_narrative') or '').strip(),
        })

    for witness in case.witnesses:
        prefix = f'w{witness.id}_'
        if prefix + 'name' in request.form:
            name = (request.form.get(prefix + 'name') or witness.name).strip()
            if name:
                witness.name = name[:120]
        if prefix + 'designation' in request.form:
            witness.designation = (request.form.get(prefix + 'designation') or '').strip()[:200] or None
        if witness.role in (WITNESS_IO, WITNESS_EXPERT):
            witness.called_by = SIDE_PROSECUTION
        elif prefix + 'called_by' in request.form:
            called_by = (request.form.get(prefix + 'called_by') or witness.called_by or SIDE_PROSECUTION).strip()
            if called_by in (SIDE_PROSECUTION, SIDE_DEFENCE):
                witness.called_by = called_by
        card = {}
        for key in (
            'direct_evidence', 'section_161', 'hidden_truth', 'hearsay', 'behaviour',
            'timeline', 'seizure', 's161_summaries', 'procedural_flaws',
            'expertise', 'findings', 'margin_of_error',
        ):
            if prefix + key in request.form:
                card[key] = (request.form.get(prefix + key) or '').strip()
        if card:
            merged = witness.card()
            merged.update(card)
            witness.set_card(merged)
        if witness.role in (WITNESS_IO, WITNESS_EXPERT):
            witness.unlock_min_score = 0
        elif prefix + 'unlock_min_score' in request.form:
            try:
                witness.unlock_min_score = max(
                    0,
                    min(100, int(request.form.get(prefix + 'unlock_min_score') or witness.unlock_min_score or 60)),
                )
            except (TypeError, ValueError):
                pass

    for exhibit in case.exhibits:
        prefix = f'e{exhibit.id}_'
        if not any(prefix + key in request.form for key in ('title', 'summary', 'body', 'unlock_min_score')):
            continue
        if prefix + 'title' in request.form:
            title = (request.form.get(prefix + 'title') or exhibit.title).strip()
            if title:
                exhibit.title = title[:200]
        if prefix + 'summary' in request.form:
            exhibit.summary = (request.form.get(prefix + 'summary') or '').strip() or None
        if prefix + 'body' in request.form:
            exhibit.set_body({'body': (request.form.get(prefix + 'body') or '').strip()})
        if prefix + 'unlock_min_score' in request.form:
            try:
                exhibit.unlock_min_score = max(
                    0,
                    min(100, int(request.form.get(prefix + 'unlock_min_score') or exhibit.unlock_min_score or 60)),
                )
            except (TypeError, ValueError):
                pass


def _read_quiz_form(case):
    pack = case.quiz_pack()
    if 'quiz_brief' in request.form:
        pack['brief'] = (request.form.get('quiz_brief') or '').strip()[:12000]
    if 'quiz_pass_score' in request.form:
        try:
            pack['pass_score'] = max(0, min(100, int(request.form.get('quiz_pass_score') or 60)))
        except (TypeError, ValueError):
            pass
    if 'quiz_witness_unlock_score' in request.form:
        try:
            pack['witness_unlock_score'] = max(
                0, min(100, int(request.form.get('quiz_witness_unlock_score') or pack.get('pass_score') or 60)),
            )
        except (TypeError, ValueError):
            pass
    if 'quiz_allow_retake_present' in request.form:
        pack['allow_retake'] = request.form.get('quiz_allow_retake') == '1'
    ids = request.form.getlist('quiz_id')
    if not ids:
        return pack
    questions = []
    for qid in ids:
        qid = (qid or '').strip()
        if not qid or request.form.get(f'quiz_{qid}_delete'):
            continue
        choices = [(request.form.get(f'quiz_{qid}_c{index}') or '').strip() for index in range(1, 5)]
        try:
            answer_index = int(request.form.get(f'quiz_{qid}_answer_index') or 1)
        except (TypeError, ValueError):
            answer_index = 1
        answer = choices[answer_index - 1] if 1 <= answer_index <= 4 else ''
        questions.append(normalize_quiz_question({
            'id': qid,
            'prompt': request.form.get(f'quiz_{qid}_prompt'),
            'choices': choices,
            'answer': answer,
            'side': request.form.get(f'quiz_{qid}_side'),
        }, qid))
    pack['questions'] = questions
    return pack


def _teacher_home_rows(teacher):
    sessions = _teacher_sessions(teacher)
    session_ids = [item.id for item in sessions]
    by_session = {}
    if session_ids:
        for case in (
            MockTrialCase.query
            .filter(MockTrialCase.session_id.in_(session_ids))
            .filter(MockTrialCase.status != STATUS_ARCHIVED)
            .order_by(MockTrialCase.updated_at.desc())
            .all()
        ):
            by_session.setdefault(case.session_id, []).append(case)
    rows = []
    for session_obj in sessions:
        cases = by_session.get(session_obj.id, [])
        rows.append({
            'session': session_obj,
            'course_label': _course_label(session_obj),
            'cases': cases,
            'published_count': sum(1 for case in cases if case.is_published()),
        })
    return rows


@mock_trial_simulator_bp.route('/')
@login_required
def index():
    blocked = _guard()
    if blocked is not None:
        return blocked
    if _is_student():
        return _student_index()
    teacher = resolve_caller_teacher(current_user)
    if not teacher:
        flash('শুধুমাত্র শিক্ষকরাই Mock Trial Simulator পরিচালনা করতে পারবেন।', 'danger')
        return redirect(url_for('index'))
    return render_template(
        'mock_trial_simulator/teacher_home.html',
        rows=_teacher_home_rows(teacher),
        dashboard_url=url_for('index'),
        phase_labels=PHASE_LABELS,
    )


def _student_index():
    student_id = getattr(current_user, 'username', None)
    enrolled = _student_sessions(student_id) if student_id else {}
    session_ids = list(enrolled.keys())
    cases = []
    if session_ids:
        cases = (
            MockTrialCase.query
            .filter(
                MockTrialCase.session_id.in_(session_ids),
                MockTrialCase.status == STATUS_PUBLISHED,
            )
            .order_by(MockTrialCase.published_at.desc(), MockTrialCase.id.desc())
            .all()
        )
    cards = []
    for case in cases:
        session_obj = case.session
        if not session_is_mock_trial_enabled(session_obj):
            continue
        cards.append({
            'case': case,
            'course_label': _course_label(session_obj),
            'caption': case.public_caption(),
            'role_label': resolve_cast(case, student_id).get('label'),
        })
    return render_template(
        'mock_trial_simulator/student_list.html',
        cards=cards,
        dashboard_url=url_for('student_dashboard'),
        phase_labels=PHASE_LABELS,
    )


@mock_trial_simulator_bp.route('/course/<int:session_id>', methods=['GET', 'POST'])
@login_required
def teacher_course(session_id):
    blocked = _guard()
    if blocked is not None:
        return blocked
    if _is_student():
        return redirect(url_for('mock_trial_simulator.index'))
    session_obj, teacher = _owned_session(session_id)
    if not session_obj:
        return redirect(url_for('mock_trial_simulator.index'))

    if request.method == 'POST':
        title, case_type, extra_brief = _read_create_form()
        case = MockTrialCase(
            session_id=session_id,
            teacher_id=teacher.id,
            title=title,
            case_type=case_type,
            extra_brief=extra_brief,
            prosecution_witness_count=_form_witness_count('prosecution_witness_count'),
            defence_witness_count=_form_witness_count('defence_witness_count'),
            status=STATUS_DRAFT,
            current_phase=1,
        )
        db.session.add(case)
        db.session.commit()
        flash('Draft case created. Review it, generate the AI pack, then publish.', 'success')
        return redirect(_teacher_case_url(case.id))

    cases = (
        MockTrialCase.query
        .filter_by(session_id=session_id)
        .filter(MockTrialCase.status != STATUS_ARCHIVED)
        .order_by(MockTrialCase.updated_at.desc())
        .all()
    )
    return render_template(
        'mock_trial_simulator/teacher_course.html',
        session=session_obj,
        course_label=_course_label(session_obj),
        cases=cases,
        case_types=CASE_TYPES,
        dashboard_url=url_for('mock_trial_simulator.index'),
        phase_labels=PHASE_LABELS,
    )


@mock_trial_simulator_bp.route('/case/<int:case_id>', methods=['GET', 'POST'])
@login_required
def teacher_case(case_id):
    blocked = _guard()
    if blocked is not None:
        return blocked
    if _is_student():
        return redirect(_student_case_url(case_id))
    case, session_obj, _teacher = _case_for_teacher(case_id)
    if not case:
        return redirect(url_for('mock_trial_simulator.index'))

    action = (request.form.get('action') or '').strip() if request.method == 'POST' else ''
    if request.method == 'POST' and action == 'generate':
        _apply_case_edits(case)
        db.session.commit()
        try:
            from utils.ai.client import AIClientError, user_facing_generation_error
            from utils.ai.mock_trial import generate_case_pack
            pack = generate_case_pack(
                case_type=case.case_type,
                case_type_label=case.case_type_label(),
                title=case.title,
                extra_brief=case.extra_brief,
                course_label=_course_label(session_obj),
                prosec_count=case.prosecution_witness_count,
                defence_count=case.defence_witness_count,
            )
            # generate_case_pack may reset the DB session; reload before writing.
            case = MockTrialCase.query.get(case_id)
            if not case:
                flash('Case could not be reloaded after generation.', 'danger')
                return redirect(url_for('mock_trial_simulator.index'))
            apply_generated_pack(case, pack)
            db.session.commit()
            flash('AI draft generated. Edit anything that looks wrong, then publish.', 'success')
        except AIClientError as exc:
            db.session.rollback()
            flash(user_facing_generation_error(exc), 'warning')
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'warning')
        except Exception as exc:
            db.session.rollback()
            from utils.ai.client import user_facing_generation_error
            friendly = user_facing_generation_error(exc)
            if friendly and friendly != 'Generation failed. Please try again.':
                flash(friendly, 'warning')
            else:
                flash_exception(exc, 'AI generation failed', 'danger')
        return redirect(_teacher_case_url(case_id))

    if request.method == 'POST' and action == 'add_witness':
        _apply_case_edits(case)
        try:
            add_manual_witness(
                case,
                request.form.get('new_witness_name'),
                role=(request.form.get('new_witness_role') or '').strip(),
                called_by=(request.form.get('new_witness_called_by') or '').strip(),
                designation=request.form.get('new_witness_designation'),
            )
            db.session.commit()
            flash('Witness added. Fill in the instruction card, then save.', 'success')
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'warning')
        return redirect(_teacher_case_url(case.id))

    if request.method == 'POST' and (
        action == 'delete_witness' or (request.form.get('delete_witness_id') or '').strip()
    ):
        _apply_case_edits(case)
        if delete_case_witness(case, request.form.get('delete_witness_id') or request.form.get('witness_id')):
            db.session.commit()
            flash('Witness removed.', 'success')
        else:
            flash('That witness was not found.', 'warning')
        return redirect(_teacher_case_url(case.id))

    if request.method == 'POST' and action == 'save':
        _apply_case_edits(case)
        db.session.commit()
        flash('Draft saved.', 'success')
        return redirect(_teacher_case_url(case.id))

    if request.method == 'POST' and action == 'publish':
        _apply_case_edits(case)
        if not (case.fir().get('narrative') or '').strip() and not (case.factsheet().get('incident_summary') or '').strip():
            flash('Add an FIR or incident summary (or generate the AI pack) before publishing.', 'warning')
            return redirect(_teacher_case_url(case.id))
        case.status = STATUS_PUBLISHED
        case.current_phase = max(int(case.current_phase or 1), PHASE_DISCOVERY)
        case.published_at = case.published_at or datetime.utcnow()
        _notify_published(case)
        db.session.commit()
        flash('Case published. Both teams must file a vakalatnama (ওকালতনামা) in Discovery.', 'success')
        return redirect(_teacher_case_url(case.id))

    if request.method == 'POST' and action == 'unpublish':
        case.status = STATUS_DRAFT
        db.session.commit()
        flash('Case returned to draft. Students will no longer see it.', 'success')
        return redirect(_teacher_case_url(case.id))

    if request.method == 'POST' and action == 'archive':
        case.status = STATUS_ARCHIVED
        db.session.commit()
        flash('Case archived.', 'success')
        return redirect(url_for('mock_trial_simulator.teacher_course', session_id=session_obj.id))

    if request.method == 'POST' and action == 'assign':
        roster = _roster(session_obj.id)
        witness_map = {}
        for witness in case.witnesses:
            raw = (request.form.get(f'witness_{witness.id}') or '').strip()
            witness_map[witness.id] = raw
        before = set()
        for team in case.teams:
            for member in team.members:
                before.add((team.side, member.student_id))
        for witness in case.witnesses:
            if witness.assigned_student_id:
                before.add(('witness', witness.assigned_student_id))
        try:
            prosecution_ids = list(request.form.getlist('prosecution_ids'))
            defence_ids = list(request.form.getlist('defence_ids'))
            for row in roster:
                sid = (getattr(row, 'student_id', None) or '').strip()
                role = (request.form.get(f'cast_{sid}') or '').strip()
                if role == SIDE_PROSECUTION and sid not in prosecution_ids:
                    prosecution_ids.append(sid)
                elif role == SIDE_DEFENCE and sid not in defence_ids:
                    defence_ids.append(sid)
            apply_cast(
                case,
                roster,
                prosecution_ids,
                defence_ids,
                witness_map,
            )
            db.session.flush()
            for team in case.teams:
                label = 'Prosecution' if team.side == SIDE_PROSECUTION else 'Defence'
                for member in team.members:
                    if (team.side, member.student_id) not in before:
                        _notify_role(case, member.student_id, label)
            for witness in case.witnesses:
                if witness.assigned_student_id and ('witness', witness.assigned_student_id) not in before:
                    _notify_role(case, witness.assigned_student_id, f'Witness — {witness.name}')
            db.session.commit()
            flash('Teams and witnesses saved. Assigned students will see only their side’s papers.', 'success')
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'warning')
        except Exception as exc:
            db.session.rollback()
            flash_exception(exc, 'Could not save assignments', 'danger')
        return redirect(_teacher_case_url(case.id))

    if request.method == 'POST' and action in ('accept_petition', 'reject_petition'):
        try:
            petition_id = int(request.form.get('petition_id') or 0)
        except (TypeError, ValueError):
            petition_id = 0
        petition = MockTrialPetition.query.get(petition_id)
        if not petition or petition.case_id != case.id:
            flash('That paper was not found.', 'warning')
            return redirect(_teacher_case_url(case.id))
        note = (request.form.get('teacher_note') or '').strip()
        petition.set_meta({'teacher_note': note})
        if action == 'accept_petition':
            petition.status = MockTrialPetition.STATUS_ACCEPTED
            db.session.flush()
            if _vakalatnamas_accepted(case):
                case.current_phase = max(int(case.current_phase or 1), PHASE_QUIZ)
                for team in case.teams:
                    for member in team.members:
                        _notify_role(case, member.student_id, 'Quiz is open')
                if build_discovery_quiz(case, SIDE_PROSECUTION) or build_discovery_quiz(case, SIDE_DEFENCE):
                    flash('Both vakalatnamas accepted. Phase 3 (Quiz) is open.', 'success')
                else:
                    flash('Both vakalatnamas accepted and Phase 3 is open. Add quiz questions so students can unlock exhibits.', 'warning')
            else:
                flash('Vakalatnama accepted. Phase 3 opens after you accept both sides.', 'success')
        else:
            petition.status = MockTrialPetition.STATUS_REJECTED
            flash('Vakalatnama returned. Students can revise and submit again.', 'warning')
        db.session.commit()
        return redirect(_teacher_case_url(case.id))

    if request.method == 'POST' and action in (
        'save_quiz', 'add_quiz_question', 'generate_quiz',
    ):
        pack = _read_quiz_form(case)
        if action == 'add_quiz_question':
            qid = next_quiz_id(pack.get('questions'))
            pack['questions'] = list(pack.get('questions') or []) + [
                normalize_quiz_question({
                    'id': qid,
                    'side': request.form.get('quiz_gen_side') or 'both',
                }, qid)
            ]
            case.set_quiz_pack(pack)
            db.session.commit()
            flash('Blank question added. Fill it in and save.', 'success')
            return redirect(_teacher_case_url(case.id))
        if action == 'generate_quiz':
            try:
                from utils.ai.client import AIClientError, user_facing_generation_error
                from utils.ai.mock_trial import generate_quiz_questions
                generated = generate_quiz_questions(
                    brief=request.form.get('quiz_brief') or pack.get('brief'),
                    count=request.form.get('quiz_count') or 5,
                    side=request.form.get('quiz_gen_side') or 'both',
                    title=case.title,
                    case_type_label=case.case_type_label(),
                    course_label=_course_label(session_obj),
                    factsheet=case.factsheet(),
                    fir=case.fir(),
                    accused=case.accused_statement(),
                )
                case = MockTrialCase.query.get(case_id) or case
                pack = _read_quiz_form(case)
                pack['brief'] = (request.form.get('quiz_brief') or pack.get('brief') or '').strip()[:12000]
                existing = [] if request.form.get('quiz_replace') else list(pack.get('questions') or [])
                for raw in generated:
                    qid = next_quiz_id(existing)
                    existing.append(normalize_quiz_question(dict(raw, id=qid), qid))
                pack['questions'] = existing
                case.set_quiz_pack(pack)
                db.session.commit()
                flash(f'AI added {len(generated)} question(s). Edit anything that looks wrong, then save.', 'success')
            except AIClientError as exc:
                db.session.rollback()
                flash(user_facing_generation_error(exc), 'warning')
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), 'warning')
            except Exception as exc:
                db.session.rollback()
                from utils.ai.client import user_facing_generation_error
                flash(user_facing_generation_error(exc), 'warning')
            return redirect(_teacher_case_url(case_id))
        case.set_quiz_pack(pack)
        db.session.commit()
        flash('Quiz saved.', 'success')
        return redirect(_teacher_case_url(case.id))

    sheet = case.factsheet()
    fir = case.fir()
    accused = case.accused_statement()
    roster = _roster(session_obj.id)
    prosec_ids = {
        member.student_id
        for team in case.teams if team.side == SIDE_PROSECUTION
        for member in team.members
    }
    defence_ids = {
        member.student_id
        for team in case.teams if team.side == SIDE_DEFENCE
        for member in team.members
    }
    petitions = {
        'prosecution': _team_petition(case, team_for_side(case, SIDE_PROSECUTION))
        if team_for_side(case, SIDE_PROSECUTION) else None,
        'defence': _team_petition(case, team_for_side(case, SIDE_DEFENCE))
        if team_for_side(case, SIDE_DEFENCE) else None,
    }
    return render_template(
        'mock_trial_simulator/teacher_case.html',
        case=case,
        session=session_obj,
        course_label=_course_label(session_obj),
        case_types=CASE_TYPES,
        witness_roles=WITNESS_ROLES,
        sheet=sheet,
        fir=fir,
        accused=accused,
        roster=roster,
        prosec_ids=prosec_ids,
        defence_ids=defence_ids,
        petitions=petitions,
        quiz_pack=case.quiz_pack(),
        dashboard_url=url_for('mock_trial_simulator.teacher_course', session_id=session_obj.id),
        phase_labels=PHASE_LABELS,
        roster_label=_roster_label,
        panel=_requested_panel(TEACHER_PANELS),
    )


def _student_play_context(case, student_id, is_student):
    cast = resolve_cast(case, student_id) if is_student else {
        'kind': None, 'team': None, 'witness': None, 'side': None, 'label': None,
    }
    petition = None
    if cast.get('kind') == 'counsel' and cast.get('team'):
        petition = _team_petition(case, cast['team'])
    teammates = []
    if cast.get('team'):
        teammates = [
            member.student_name or member.student_id
            for member in cast['team'].members
        ]
    phase = int(case.current_phase or 1)
    quiz = []
    unlocked_exhibits = []
    unlocked_witnesses = []
    quiz_passed = bool(petition and petition.quiz_passed())
    pack = case.quiz_pack() or {}
    pass_score = int(pack.get('pass_score') or 60)
    witness_unlock_score = int(pack.get('witness_unlock_score') or pass_score)
    quiz_score = petition.quiz_score() if petition else 0
    if cast.get('kind') == 'counsel' and phase >= PHASE_QUIZ:
        quiz = public_quiz(
            build_discovery_quiz(case, cast.get('side')),
            answers=petition.quiz_answers() if petition else {},
            results=petition.quiz_results() if petition else {},
        )
        unlocked_exhibits = unlocked_exhibits_for_score(case, quiz_score)
        unlocked_witnesses = unlocked_witnesses_for_score(case, quiz_score)
    locked_unlocks = locked_witness_unlocks(case, quiz_score) if (
        cast.get('kind') == 'counsel' and phase >= PHASE_QUIZ
    ) else []
    quiz_attempted = bool(petition and petition.quiz_attempted())
    quiz_allow_retake = bool(pack.get('allow_retake'))
    return {
        'cast': cast,
        'petition': petition,
        'teammates': teammates,
        'fir': case.fir() if cast.get('side') == SIDE_PROSECUTION else {},
        'accused': case.accused_statement() if cast.get('side') == SIDE_DEFENCE else {},
        'witness': cast.get('witness'),
        'witness_card': cast['witness'].card() if cast.get('witness') else {},
        'phase': phase,
        'quiz': quiz,
        'quiz_passed': quiz_passed,
        'quiz_score': quiz_score,
        'quiz_pass_score': pass_score,
        'quiz_allow_retake': quiz_allow_retake,
        'quiz_attempted': quiz_attempted,
        'quiz_locked': quiz_attempted and not quiz_allow_retake,
        'witness_unlock_score': witness_unlock_score,
        'unlocked_exhibits': unlocked_exhibits,
        'unlocked_witnesses': unlocked_witnesses,
        'locked_witness_count': len(locked_unlocks),
        'next_witness_unlock': min(locked_unlocks) if locked_unlocks else None,
        'teacher_note': petition.teacher_note() if petition else '',
        'paper_rows': paper_rows_for_witness(cast.get('witness')),
        'paper_template': None,
        'paper_fields': [],
        'paper_values': {},
        'paper_record': None,
    }


def _attach_paper_template(ctx):
    witness = (ctx.get('cast') or {}).get('witness')
    if not witness or not witness.is_official_prosecution():
        return ctx
    spec = get_template(witness.role, request.args.get('template') or request.form.get('template_key'))
    if not spec:
        return ctx
    paper = next((item for item in (witness.papers or []) if item.template_key == spec.get('key')), None)
    ctx['paper_template'] = spec
    ctx['paper_fields'] = template_fields(spec)
    ctx['paper_record'] = paper
    ctx['paper_values'] = paper.body() if paper else {}
    return ctx


@mock_trial_simulator_bp.route('/play/<int:case_id>', methods=['GET', 'POST'])
@login_required
def student_case(case_id):
    blocked = _guard()
    if blocked is not None:
        return blocked
    case = MockTrialCase.query.get_or_404(case_id)
    if _is_student():
        student_id = getattr(current_user, 'username', None)
        enrolled = _student_sessions(student_id)
        if (
            case.session_id not in enrolled
            or not case.is_published()
            or not session_is_mock_trial_enabled(case.session)
        ):
            flash('This mock trial is not available yet.', 'warning')
            return redirect(url_for('mock_trial_simulator.index'))
        if request.method == 'POST':
            cast = resolve_cast(case, student_id)
            action = (request.form.get('action') or '').strip()
            if cast.get('kind') == 'counsel' and action in ('save_petition', 'submit_petition'):
                petition = _team_petition(case, cast.get('team'), create=True)
                petition.petition_type = MockTrialPetition.TYPE_VAKALATNAMA
                petition.draft_text = (request.form.get('draft_text') or '').strip() or None
                if action == 'submit_petition':
                    if not petition.draft_text:
                        flash('Write the vakalatnama before submitting.', 'warning')
                        return redirect(_student_case_url(case.id))
                    petition.status = MockTrialPetition.STATUS_SUBMITTED
                    flash('Vakalatnama submitted. Your teacher can review it.', 'success')
                elif petition.status not in (
                    MockTrialPetition.STATUS_ACCEPTED,
                    MockTrialPetition.STATUS_SUBMITTED,
                ):
                    petition.status = MockTrialPetition.STATUS_DRAFT
                    flash('Draft saved.', 'success')
                else:
                    flash('Draft saved.', 'success')
                db.session.commit()
            elif cast.get('kind') == 'counsel' and action == 'submit_quiz':
                if int(case.current_phase or 1) < PHASE_QUIZ:
                    flash('Phase 3 is not open yet. Wait until the teacher accepts both vakalatnamas.', 'warning')
                else:
                    petition = _team_petition(case, cast.get('team'), create=True)
                    questions = build_discovery_quiz(case, cast.get('side'))
                    if not questions:
                        flash('Your teacher has not published the quiz yet.', 'warning')
                    elif petition.quiz_attempted() and not (case.quiz_pack() or {}).get('allow_retake'):
                        flash('Your teacher has not allowed another attempt.', 'warning')
                    else:
                        answers = {
                            item['id']: request.form.get(f'q_{item["id"]}')
                            for item in questions
                        }
                        pass_score = int((case.quiz_pack() or {}).get('pass_score') or 60)
                        score, passed, result_map, given_map = grade_discovery_quiz(
                            questions, answers, pass_score,
                        )
                        petition.set_meta({
                            'quiz_score': score,
                            'quiz_passed': passed,
                            'quiz_answers': given_map,
                            'quiz_results': result_map,
                        })
                        db.session.commit()
                        if passed:
                            flash(
                                f'Quiz passed ({score}%). Exhibits and witness names / player IDs unlock at the scores your teacher set.',
                                'success',
                            )
                        else:
                            flash(
                                f'Score {score}%. You need {pass_score}% to pass. Witness names unlock at the score your teacher set.',
                                'warning',
                            )
            elif cast.get('kind') == 'witness' and action == 'save_witness_notes':
                cast['witness'].student_notes = (request.form.get('student_notes') or '').strip() or None
                db.session.commit()
                flash('Your prep notes were saved. Keep this card private.', 'success')
            elif cast.get('kind') == 'witness' and action == 'save_witness_paper':
                witness = cast.get('witness')
                spec = get_template(witness.role, request.form.get('template_key')) if witness else None
                if not witness or not witness.is_official_prosecution() or spec is None:
                    flash('That paper template is not available for your role yet.', 'warning')
                else:
                    paper = get_or_create_witness_paper(witness, spec)
                    values = {}
                    for field in template_fields(spec):
                        values[field['key']] = (request.form.get('f_' + field['key']) or '').strip()
                    paper.title = (spec.get('title_bn') or spec.get('title') or spec.get('key'))[:200]
                    paper.set_body(values)
                    if (request.form.get('submit_paper') or '').strip():
                        paper.status = MockTrialWitnessPaper.STATUS_SUBMITTED
                        paper.submitted_at = datetime.utcnow()
                        flash('Paper saved.', 'success')
                    else:
                        if paper.status != MockTrialWitnessPaper.STATUS_SUBMITTED:
                            paper.status = MockTrialWitnessPaper.STATUS_DRAFT
                        flash('Draft saved.', 'success')
                    db.session.commit()
            else:
                flash('You can only work on the role your teacher assigned.', 'warning')
            return redirect(_student_case_url(case.id))

        ctx = _attach_paper_template(_student_play_context(case, student_id, True))
        return render_template(
            'mock_trial_simulator/student_case.html',
            case=case,
            course_label=_course_label(case.session),
            caption=case.public_caption(),
            dashboard_url=url_for('mock_trial_simulator.index'),
            phase_labels=PHASE_LABELS,
            is_student=True,
            panel=_requested_panel(STUDENT_PANELS),
            **ctx,
        )

    case_obj, session_obj, teacher = _case_for_teacher(case_id)
    if not case_obj:
        return redirect(url_for('mock_trial_simulator.index'))
    ctx = _attach_paper_template(_student_play_context(case_obj, None, False))
    return render_template(
        'mock_trial_simulator/student_case.html',
        case=case_obj,
        course_label=_course_label(session_obj),
        caption=case_obj.public_caption(),
        dashboard_url=url_for('mock_trial_simulator.teacher_case', case_id=case_id),
        phase_labels=PHASE_LABELS,
        is_student=False,
        panel=_requested_panel(STUDENT_PANELS),
        **ctx,
    )


def _paper_fallback(case, is_teacher):
    if is_teacher:
        return url_for('mock_trial_simulator.teacher_case', case_id=case.id)
    return url_for('mock_trial_simulator.student_case', case_id=case.id)


def _resolve_paper_viewer(case):
    blocked = _guard()
    if blocked is not None:
        return None, blocked
    if _is_student():
        student_id = getattr(current_user, 'username', None)
        enrolled = _student_sessions(student_id) if student_id else {}
        if (
            not student_id
            or case.session_id not in enrolled
            or not case.is_published()
            or not session_is_mock_trial_enabled(case.session)
        ):
            flash('This mock trial is not available yet.', 'warning')
            return None, redirect(url_for('mock_trial_simulator.index'))
        return {
            'is_teacher': False,
            'student_id': student_id,
            'cast': resolve_cast(case, student_id),
        }, None
    owned, _session_obj, _teacher = _case_for_teacher(case.id)
    if not owned:
        return None, redirect(url_for('mock_trial_simulator.index'))
    return {
        'is_teacher': True,
        'student_id': None,
        'cast': {'kind': None, 'team': None, 'witness': None, 'side': None, 'label': None},
    }, None


def _viewer_quiz_score(case, viewer):
    if viewer.get('is_teacher'):
        return 100
    cast = viewer.get('cast') or {}
    if cast.get('kind') != 'counsel' or not cast.get('team'):
        return 0
    petition = _team_petition(case, cast['team'])
    return petition.quiz_score() if petition else 0


def _viewer_exhibits(case, viewer):
    if viewer.get('is_teacher'):
        return list(case.exhibits or [])
    if (viewer.get('cast') or {}).get('kind') != 'counsel':
        return []
    if int(case.current_phase or 1) < PHASE_QUIZ:
        return []
    return unlocked_exhibits_for_score(case, _viewer_quiz_score(case, viewer))


def _viewer_witnesses(case, viewer):
    if viewer.get('is_teacher'):
        return [item.public_identity() for item in (case.witnesses or [])]
    if (viewer.get('cast') or {}).get('kind') != 'counsel':
        return []
    if int(case.current_phase or 1) < PHASE_QUIZ:
        return []
    return unlocked_witnesses_for_score(case, _viewer_quiz_score(case, viewer))


def _can_see_side_brief(viewer, side):
    if viewer.get('is_teacher'):
        return True
    return (viewer.get('cast') or {}).get('side') == side


def _can_see_vakalatnama(viewer, side):
    if viewer.get('is_teacher'):
        return True
    cast = viewer.get('cast') or {}
    return cast.get('kind') == 'counsel' and cast.get('side') == side


def _can_see_witness_card(viewer, witness):
    if viewer.get('is_teacher'):
        return True
    assigned = (viewer.get('cast') or {}).get('witness')
    return bool(assigned and witness and assigned.id == witness.id)


def _send_paper(case, viewer, title, stem, sections):
    fallback = _paper_fallback(case, viewer.get('is_teacher'))
    if not sections:
        return deny_paper('That paper is not ready to download yet.', fallback)
    return render_paper_response(
        case,
        _course_label(case.session),
        title,
        paper_filename(case, stem),
        sections,
        fallback,
    )


def _pack_sections(case, viewer):
    sections = []
    if viewer.get('is_teacher'):
        sections.append(factsheet_section(case))
    if _can_see_side_brief(viewer, SIDE_PROSECUTION):
        sections.append(fir_section(case))
    if _can_see_side_brief(viewer, SIDE_DEFENCE):
        sections.append(accused_section(case))
    for side in (SIDE_PROSECUTION, SIDE_DEFENCE):
        if not _can_see_vakalatnama(viewer, side):
            continue
        petition = _team_petition(case, team_for_side(case, side))
        if petition and (petition.draft_text or '').strip():
            sections.append(vakalatnama_section(petition, side))
    identities = _viewer_witnesses(case, viewer)
    if identities:
        sections.append(witness_list_section(identities))
    for index, exhibit in enumerate(_viewer_exhibits(case, viewer), start=1):
        sections.append(exhibit_section(exhibit, index=index))
    assigned = (viewer.get('cast') or {}).get('witness')
    if assigned and _can_see_witness_card(viewer, assigned):
        sections.append(witness_card_section(assigned))
    return sections


@mock_trial_simulator_bp.route('/case/<int:case_id>/pdf/<kind>')
@login_required
def paper_pdf(case_id, kind):
    case = MockTrialCase.query.get_or_404(case_id)
    viewer, blocked = _resolve_paper_viewer(case)
    if blocked is not None:
        return blocked
    fallback = _paper_fallback(case, viewer.get('is_teacher'))
    kind = (kind or '').strip().lower()
    if kind == 'factsheet':
        if not viewer.get('is_teacher'):
            return deny_paper('The master factsheet is only for the teacher.', fallback)
        return _send_paper(case, viewer, 'Master factsheet', 'factsheet', [factsheet_section(case)])
    if kind == 'fir':
        if not _can_see_side_brief(viewer, SIDE_PROSECUTION):
            return deny_paper('The FIR is only for the prosecution team.', fallback)
        return _send_paper(case, viewer, 'First Information Report (FIR)', 'fir', [fir_section(case)])
    if kind in ('accused', 'statement'):
        if not _can_see_side_brief(viewer, SIDE_DEFENCE):
            return deny_paper('The accused’s statement is only for the defence team.', fallback)
        return _send_paper(case, viewer, 'Accused’s first statement', 'accused-statement', [accused_section(case)])
    if kind == 'witnesses':
        identities = _viewer_witnesses(case, viewer)
        if not identities:
            return deny_paper('No witness identities are unlocked on your copy yet.', fallback)
        return _send_paper(
            case, viewer, 'Witness list', 'witness-list',
            [witness_list_section(identities)],
        )
    if kind == 'exhibits':
        exhibits = _viewer_exhibits(case, viewer)
        if not exhibits:
            return deny_paper('No exhibits are unlocked on your copy yet.', fallback)
        sections = [exhibit_section(item, index=index) for index, item in enumerate(exhibits, start=1)]
        return _send_paper(case, viewer, 'Exhibits', 'exhibits', sections)
    if kind in ('pack', 'papers'):
        sections = _pack_sections(case, viewer)
        if not sections:
            return deny_paper('No papers are ready to download yet.', fallback)
        return _send_paper(case, viewer, 'Case papers', 'papers', sections)
    return deny_paper('That paper was not found.', fallback)


@mock_trial_simulator_bp.route('/case/<int:case_id>/pdf/vakalatnama/<side>')
@login_required
def vakalatnama_pdf(case_id, side):
    case = MockTrialCase.query.get_or_404(case_id)
    viewer, blocked = _resolve_paper_viewer(case)
    if blocked is not None:
        return blocked
    fallback = _paper_fallback(case, viewer.get('is_teacher'))
    side = normalize_side(side)
    if not side:
        return deny_paper('Choose the prosecution or defence vakalatnama.', fallback)
    if not _can_see_vakalatnama(viewer, side):
        return deny_paper('You can download only your team’s ওকালতনামা.', fallback)
    petition = _team_petition(case, team_for_side(case, side))
    if not petition or not (petition.draft_text or '').strip():
        return deny_paper('The ওকালতনামা has not been written yet.', fallback)
    label = 'defence' if side == SIDE_DEFENCE else 'prosecution'
    return _send_paper(
        case, viewer, f'ওকালতনামা — {label.title()}',
        f'okalotnama-{label}',
        [vakalatnama_section(petition, side)],
    )


@mock_trial_simulator_bp.route('/case/<int:case_id>/pdf/exhibit/<int:exhibit_id>')
@login_required
def exhibit_pdf(case_id, exhibit_id):
    case = MockTrialCase.query.get_or_404(case_id)
    viewer, blocked = _resolve_paper_viewer(case)
    if blocked is not None:
        return blocked
    fallback = _paper_fallback(case, viewer.get('is_teacher'))
    exhibit = next((item for item in (case.exhibits or []) if item.id == exhibit_id), None)
    if not exhibit:
        return deny_paper('That exhibit was not found.', fallback)
    allowed = {item.id for item in _viewer_exhibits(case, viewer)}
    if exhibit.id not in allowed:
        return deny_paper('That exhibit is still locked on your copy.', fallback)
    return _send_paper(
        case, viewer, exhibit.title or 'Exhibit',
        f'exhibit-{exhibit.exhibit_key or exhibit.id}',
        [exhibit_section(exhibit)],
    )


@mock_trial_simulator_bp.route('/case/<int:case_id>/pdf/witness-card/<int:witness_id>')
@login_required
def witness_card_pdf(case_id, witness_id):
    case = MockTrialCase.query.get_or_404(case_id)
    viewer, blocked = _resolve_paper_viewer(case)
    if blocked is not None:
        return blocked
    fallback = _paper_fallback(case, viewer.get('is_teacher'))
    witness = next((item for item in (case.witnesses or []) if item.id == witness_id), None)
    if not witness:
        return deny_paper('That witness card was not found.', fallback)
    if not _can_see_witness_card(viewer, witness):
        return deny_paper('Instruction cards stay hidden from counsel.', fallback)
    return _send_paper(
        case, viewer, f'Instruction card — {witness.name}',
        f'witness-card-{witness.id}',
        [witness_card_section(witness)],
    )
