"""Phase 1 mock trial: teacher HITL pack, publish, student information asymmetry."""
from unittest.mock import patch

from blueprints.class_management.models import ClassStudent, Session, StudentNotification
from blueprints.course_management.models import Course
from blueprints.mock_trial_simulator.models import (
    MockTrialCase,
    MockTrialEnabledCourse,
    MockTrialPetition,
    MockTrialWitness,
    MockTrialWitnessPaper,
    PHASE_QUIZ,
    SIDE_PROSECUTION,
    WITNESS_IO,
    build_discovery_quiz,
    grade_discovery_quiz,
    normalize_course_code,
    normalize_quiz_pack,
    public_quiz,
    quiz_questions_for_side,
    replace_enabled_courses,
    resolve_cast,
    session_is_mock_trial_enabled,
    unlocked_witnesses_for_score,
)
from blueprints.student_management.models import Student as StudentMgmt
from extensions import db
from tests.conftest import TEST_PASSWORD, login_client
from user_models import User
from utils.ai.mock_trial import (
    default_exhibits,
    ensure_witness_roster,
    generate_case_pack,
    normalize_case_pack,
    parse_teacher_pack_request,
)


SAMPLE_PACK = {
    'title': 'State v. Karim — courtyard killing',
    'factsheet': {
        'incident_summary': 'The victim was found in a courtyard after a quarrel.',
        'date_time': '12 March 2026, 9.30 pm',
        'place': 'Ward 4, Khulna',
        'legal_provisions': ['Penal Code s.302', 'CrPC s.154'],
        'facts': ['A quarrel was heard', 'A dao was recovered'],
        'accused': [{'name': 'Karim', 'age': '28', 'role': 'accused'}],
        'victim': {'name': 'Rahim', 'age': '34'},
    },
    'fir': {
        'police_station': 'Khalishpur',
        'gd_entry': '112',
        'narrative': 'Complainant states the accused struck the victim after a land dispute.',
    },
    'accused_statement': {
        'narrative': 'I was at my sister’s house. I did not strike anyone.',
    },
    'witnesses': [
        {
            'role': 'lay',
            'called_by': 'prosecution',
            'name': 'Fatema Begum',
            'designation': 'Neighbour',
            'instruction_card': {
                'direct_evidence': 'Heard shouting from the courtyard.',
                'section_161': 'Said she saw nothing clearly.',
                'hidden_truth': 'She saw the accused drop a dao.',
                'hearsay': 'A shopkeeper told her Karim always carries a knife.',
                'behaviour': 'Nervous, looks at the floor.',
            },
        },
        {
            'role': 'io',
            'called_by': 'prosecution',
            'name': 'SI Hasan',
            'designation': 'IO, Khalishpur PS',
            'instruction_card': {
                'timeline': 'Arrived at 10.15 pm.',
                'seizure': 'Dao seized from drain.',
                's161_summaries': 'Neighbour heard shouts.',
                'procedural_flaws': 'Search witnesses were not local residents (CrPC 103).',
                'behaviour': 'Defensive about the seizure list.',
            },
        },
        {
            'role': 'expert',
            'called_by': 'defence',
            'name': 'Dr. Nila',
            'designation': 'Forensic medicine',
            'instruction_card': {
                'expertise': '12 years in forensic medicine.',
                'findings': 'Incised wound consistent with a dao.',
                'margin_of_error': 'Time of death window is ±3 hours.',
                'behaviour': 'Precise, will concede scientific limits.',
            },
        },
    ],
    'exhibits': [
        {
            'exhibit_key': 'seizure_list',
            'title': 'Seizure list',
            'summary': 'One dao recovered from a drain.',
            'unlock_min_score': 55,
        }
    ],
}


SAMPLE_QUIZ = {
    'brief': 'CrPC s.103 and Evidence Act s.27',
    'pass_score': 60,
    'witness_unlock_score': 60,
    'questions': [
        {
            'id': 'q1',
            'prompt': 'CrPC s.103 is mainly about?',
            'choices': [
                'Search and seizure, and the search witnesses',
                'Bail after conviction',
                'Charge-sheet numbering',
                'Sentencing discounts',
            ],
            'answer': 'Search and seizure, and the search witnesses',
            'side': 'both',
        },
        {
            'id': 'q2',
            'prompt': 'Evidence Act s.27 is mainly about?',
            'choices': [
                'Discovery of fact in consequence of information',
                'Dying declarations',
                'Expert opinions',
                'Public documents',
            ],
            'answer': 'Discovery of fact in consequence of information',
            'side': 'both',
        },
    ],
}


def _ensure_student_user(username='S001', name='Student One'):
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(
            username=username,
            email=f'{username.lower()}@test.example',
            full_name=name,
            role='student',
        )
        user.set_password(TEST_PASSWORD)
        db.session.add(user)
        db.session.commit()
    return user


def _enable_session_course(session_id):
    sess = db.session.get(Session, session_id)
    course = Course.query.filter_by(course_code=sess.course_code).first()
    if not course:
        course = Course(
            course_code=sess.course_code,
            course_name=sess.course_name or 'Criminal Procedure',
            credit=3,
            course_type='Theory',
            category='ug',
        )
        db.session.add(course)
        db.session.flush()
    if not MockTrialEnabledCourse.query.filter_by(course_id=course.id).first():
        db.session.add(MockTrialEnabledCourse(
            course_id=course.id,
            course_code=normalize_course_code(course.course_code),
            is_enabled=True,
        ))
    db.session.commit()
    return course.id


def _enroll(session_id, teacher_id, student_id, name):
    if not StudentMgmt.query.filter_by(student_id=student_id).first():
        db.session.add(StudentMgmt(student_id=student_id, name=name))
    if not ClassStudent.query.filter_by(session_id=session_id, student_id=student_id).first():
        db.session.add(ClassStudent(
            student_id=student_id,
            name=name,
            session_id=session_id,
            teacher_id=teacher_id,
        ))
    db.session.commit()


def _create_draft(app, client, session_id, **overrides):
    data = {
        'title': 'Courtyard homicide',
        'case_type': 'murder',
        'extra_brief': 'Land dispute in a Khulna courtyard.',
    }
    data.update(overrides)
    rv = client.post(f'/mock-trial-simulator/course/{session_id}', data=data, follow_redirects=True)
    assert rv.status_code == 200, rv.get_data(as_text=True)
    with app.app_context():
        case = MockTrialCase.query.filter_by(session_id=session_id, title=data['title']).first()
        assert case is not None
        return case.id


def test_quiz_grade_marks_right_wrong_without_answer_key():
    questions = normalize_quiz_pack(SAMPLE_QUIZ)['questions']
    score, passed, results, given = grade_discovery_quiz(
        questions,
        {
            'q1': 'Bail after conviction',
            'q2': 'Discovery of fact in consequence of information',
        },
        60,
    )
    assert score == 50
    assert passed is False
    assert results['q1'] is False
    assert results['q2'] is True
    pub = public_quiz(questions, answers=given, results=results)
    assert 'answer' not in pub[0]
    assert pub[0]['marked_correct'] is False
    assert pub[1]['marked_correct'] is True
    assert pub[0]['given'] == 'Bail after conviction'
    assert normalize_quiz_pack(SAMPLE_QUIZ)['allow_retake'] is False


def test_gemini_safety_block_is_ai_client_error_not_attribute_error():
    from utils.ai.client import AIClientError, extract_gemini_text

    text, _usage = extract_gemini_text({
        'candidates': [{'content': {'parts': [{'text': '{"ok": true}'}]}}],
    })
    assert '{"ok": true}' in text

    try:
        extract_gemini_text({
            'promptFeedback': {'blockReason': 'SAFETY'},
            'candidates': [{'finishReason': 'SAFETY', 'content': None}],
        })
    except AIClientError as exc:
        assert 'সেফটি' in str(exc)
    else:
        raise AssertionError('expected AIClientError')


def test_normalize_pack_keeps_hidden_fields_off_fir():
    pack = normalize_case_pack(SAMPLE_PACK, fallback_title='Untitled', case_type='murder')
    assert pack['fir']['narrative']
    assert 'CrPC 103' not in pack['fir']['narrative']
    io = next(item for item in pack['witnesses'] if item['role'] == 'io')
    assert '103' in io['instruction_card']['procedural_flaws']
    assert io['called_by'] == 'prosecution'
    lay = next(item for item in pack['witnesses'] if item['role'] == 'lay')
    assert lay['instruction_card']['hidden_truth']
    expert = next(item for item in pack['witnesses'] if item['role'] == 'expert')
    assert expert['called_by'] == 'prosecution'
    assert pack['exhibits']


def test_parse_brief_reads_bangla_counts_and_exhibits():
    req = parse_teacher_pack_request(
        '৫ জন প্রসিকিউশনের পক্ষে সাক্ষী এবং ৩ জন ডিফেন্স পক্ষে সাক্ষী। '
        'এক্সিবিট: সিজার লিস্ট, পোস্টমর্টেম, সিসিটিভি'
    )
    assert req['prosecution_witnesses'] == 5
    assert req['defence_witnesses'] == 3
    assert req['counts_specified']
    assert any('সিজার' in item or 'পোস্টমর্টেম' in item or 'সিসিটিভি' in item for item in req['required_exhibits'])


def test_normalize_keeps_eight_witnesses_and_fills_missing_exhibits():
    payload = {
        'title': 'Eight-witness case',
        'factsheet': {'incident_summary': 'A courtyard quarrel.'},
        'fir': {'narrative': 'FIR text'},
        'accused_statement': {'narrative': 'Denial'},
        'witnesses': [
            {'name': f'P{i}', 'role': 'lay', 'called_by': 'prosecution',
             'instruction_card': {'direct_evidence': f'saw {i}'}}
            for i in range(5)
        ] + [
            {'name': f'D{i}', 'role': 'lay', 'called_by': 'defence',
             'instruction_card': {'direct_evidence': f'heard {i}'}}
            for i in range(3)
        ],
    }
    pack = normalize_case_pack(
        payload,
        fallback_title='Eight',
        case_type='murder',
        requirements={'prosecution_witnesses': 5, 'defence_witnesses': 3, 'counts_specified': True},
    )
    assert len(pack['witnesses']) == 8
    assert sum(1 for w in pack['witnesses'] if w['called_by'] == 'prosecution') == 5
    assert sum(1 for w in pack['witnesses'] if w['called_by'] == 'defence') == 3
    filled = default_exhibits(required_titles=['CCTV clip'], incident_summary='A courtyard quarrel.')
    assert len(filled) >= 4
    assert any('CCTV' in item['title'] for item in filled)


def test_ensure_witness_roster_pads_each_side():
    roster = ensure_witness_roster(
        [{'name': 'Only one', 'called_by': 'prosecution', 'role': 'lay', 'instruction_card': {}}],
        5,
        3,
    )
    assert len(roster) == 8
    assert sum(1 for w in roster if w['called_by'] == 'prosecution') == 5
    assert sum(1 for w in roster if w['called_by'] == 'defence') == 3


def test_generate_case_pack_uses_short_passes_and_keeps_full_brief():
    briefs = []

    def fake_ai(system, user, max_tokens=2500, max_retries=0):
        briefs.append(user)
        if 'SHORT JSON skeleton' in system or 'skeleton' in system.lower() or 'exhibit titles' in system:
            payload = {
                'title': 'State v. Test',
                'factsheet': {'incident_summary': 'A courtyard quarrel after a land dispute.'},
                'fir': {'narrative': 'Complainant states the accused struck the victim.'},
                'accused_statement': {'narrative': 'I was at my sister’s house.'},
                'witnesses': [
                    {'name': f'P{i}', 'role': 'lay', 'called_by': 'prosecution'}
                    for i in range(5)
                ] + [
                    {'name': f'D{i}', 'role': 'lay', 'called_by': 'defence'}
                    for i in range(3)
                ],
                'exhibits': [{'title': 'Seizure list', 'exhibit_key': 'seizure_list'}],
            }
            return payload, {'provider': 'test', 'model_name': 'test'}
        if 'instruction cards' in system.lower() or 'instruction_card' in system:
            names = []
            if 'P0' in user:
                names = [f'P{i}' for i in range(3)]
            elif 'P3' in user:
                names = ['P3', 'P4']
            else:
                names = [f'D{i}' for i in range(3)]
            return {
                'witnesses': [
                    {'name': name, 'instruction_card': {'direct_evidence': f'{name} saw the courtyard.'}}
                    for name in names
                ]
            }, {'provider': 'test', 'model_name': 'test'}
        return {
            'exhibits': [
                {
                    'exhibit_key': 'seizure_list',
                    'title': 'Seizure list (CrPC s.103)',
                    'summary': 'Dao from drain',
                    'body': 'Full seizure list of one dao recovered from the drain with two search witnesses.',
                    'unlock_min_score': 55,
                },
                {
                    'exhibit_key': 'postmortem',
                    'title': 'Post-mortem report',
                    'summary': 'Incised wound',
                    'body': 'Post-mortem report describing an incised wound consistent with a dao and a three-hour window.',
                    'unlock_min_score': 60,
                },
            ]
        }, {'provider': 'test', 'model_name': 'test'}

    long_brief = '৫ জন প্রসিকিউশন ও ৩ জন ডিফেন্স। ' + ('বিস্তারিত ঘটনা। ' * 200)
    with patch('utils.ai.mock_trial._ai_json', side_effect=fake_ai):
        pack = generate_case_pack(
            case_type='murder',
            case_type_label='Homicide',
            title='Courtyard',
            extra_brief=long_brief,
            course_label='LAW 4103',
            prosec_count=5,
            defence_count=3,
        )
    assert len(pack['witnesses']) == 8
    assert sum(1 for w in pack['witnesses'] if w['called_by'] == 'defence') == 3
    assert pack['exhibits']
    assert any(len((item.get('body') or '')) > 40 for item in pack['exhibits'])
    assert all(long_brief[:80] in text for text in briefs)


def test_generate_surfaces_provider_error_not_opaque_ref(
    app, client, teacher_user, class_session_w1, windows,
):
    from utils.ai.client import AIClientError

    session_id = class_session_w1['session_id']
    with app.app_context():
        _enable_session_course(session_id)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _create_draft(app, client, session_id, title='Blocked pack')
    with patch(
        'utils.ai.mock_trial.generate_case_pack',
        side_effect=AIClientError('Gemini এই শিক্ষামূলক মামলার খসড়া সেফটি ফিল্টারে আটকেছে।'),
    ):
        failed = client.post(
            f'/mock-trial-simulator/case/{case_id}',
            data={'action': 'generate', 'title': 'Blocked pack', 'case_type': 'murder'},
            follow_redirects=True,
        )
    body = failed.get_data(as_text=True)
    assert failed.status_code == 200
    assert 'সেফটি' in body
    assert 'AI generation failed' not in body


def test_teacher_creates_generates_publishes_student_sees_caption_only(
    app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    with app.app_context():
        _ensure_student_user()
        _enroll(session_id, teacher_user['teacher_id'], 'S001', 'Student One')
        _enable_session_course(session_id)

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    home = client.get('/mock-trial-simulator/')
    assert home.status_code == 200
    assert b'Case workshop' in home.get_data() or b'Mock Trial Simulator' in home.get_data()
    assert b'LAW 4103' in home.get_data()

    course = client.get(f'/mock-trial-simulator/course/{session_id}')
    assert course.status_code == 200
    assert b'New case' in course.get_data()
    assert b'mtsNewCase' in course.get_data()
    assert b'Create draft' in course.get_data()

    case_id = _create_draft(app, client, session_id)
    with patch('utils.ai.mock_trial.generate_case_pack', return_value=SAMPLE_PACK):
        rv = client.post(
            f'/mock-trial-simulator/case/{case_id}',
            data={'action': 'generate', 'title': 'Courtyard homicide', 'case_type': 'murder'},
            follow_redirects=True,
        )
    assert rv.status_code == 200, rv.get_data(as_text=True)

    with app.app_context():
        case = db.session.get(MockTrialCase, case_id)
        assert case.fir()['narrative']
        hidden = ' '.join(
            (w.card().get('hidden_truth') or '') + (w.card().get('procedural_flaws') or '')
            for w in case.witnesses
        )
        assert 'dao' in hidden or '103' in hidden

    publish = client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'publish',
            'title': 'Courtyard homicide',
            'case_type': 'murder',
            'fir_narrative': SAMPLE_PACK['fir']['narrative'],
            'incident_summary': SAMPLE_PACK['factsheet']['incident_summary'],
        },
        follow_redirects=True,
    )
    assert publish.status_code == 200
    assert b'Published' in publish.get_data() or b'published' in publish.get_data()

    with app.app_context():
        notes = StudentNotification.query.filter_by(type='mock_trial').all()
        assert notes

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    listing = client.get('/mock-trial-simulator/')
    assert listing.status_code == 200
    listing_html = listing.get_data(as_text=True)
    assert 'Courtyard homicide' in listing_html or 'State v. Karim' in listing_html

    play = client.get(f'/mock-trial-simulator/play/{case_id}')
    assert play.status_code == 200
    play_html = play.get_data(as_text=True)
    assert 'Discovery' in play_html
    assert 'saw the accused drop a dao' not in play_html
    assert 's.103 paper' not in play_html
    assert 'Instruction cards' not in play_html
    assert f'/play/{case_id}?panel=wait' in play_html or 'not assigned' in play_html.lower()


def test_student_cannot_open_draft(app, client, teacher_user, class_session_w1, windows):
    session_id = class_session_w1['session_id']
    with app.app_context():
        _ensure_student_user()
        _enroll(session_id, teacher_user['teacher_id'], 'S001', 'Student One')
        _enable_session_course(session_id)

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _create_draft(app, client, session_id, title='Secret draft')

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    listing = client.get('/mock-trial-simulator/')
    assert b'Secret draft' not in listing.get_data()
    play = client.get(f'/mock-trial-simulator/play/{case_id}', follow_redirects=True)
    assert play.status_code == 200
    assert b'Secret draft' not in play.get_data() or b'not available' in play.get_data()


def test_class_management_has_mock_trial_button():
    from pathlib import Path
    index_html = Path('blueprints/class_management/templates/class_management/index.html').read_text()
    assert '/mock-trial-simulator/course/' in index_html
    assert index_html.count('mock_trial_enabled_ids and session.id in mock_trial_enabled_ids') == 2


def test_class_management_shows_mock_trial_only_for_enabled_course(
    app, client, teacher_user, class_session_w1, windows,
):
    from blueprints.class_management.models import Session

    with app.app_context():
        other = Session(
            year='Fourth',
            term='First',
            academic_session='2024-25',
            window_id=windows['w1_id'],
            course_code='LAW 5209',
            course_name='Intellectual Property Law',
            teacher_id=teacher_user['teacher_id'],
            course_type='theory',
            category='ug',
        )
        db.session.add(other)
        db.session.commit()
        enabled = db.session.get(Session, class_session_w1['session_id'])
        _enable_session_course(enabled.id)
        shown = [
            item.id
            for item in (enabled, other)
            if session_is_mock_trial_enabled(item)
        ]
        assert enabled.id in shown
        assert other.id not in shown


def test_disabled_course_hidden_from_teacher_and_student(
    app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    with app.app_context():
        _ensure_student_user()
        _enroll(session_id, teacher_user['teacher_id'], 'S001', 'Student One')
        course_id = _enable_session_course(session_id)
        assert session_is_mock_trial_enabled(db.session.get(Session, session_id))
        replace_enabled_courses([])
        assert not session_is_mock_trial_enabled(db.session.get(Session, session_id))
        assert course_id

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    home = client.get('/mock-trial-simulator/')
    assert home.status_code == 200
    assert b'LAW 4103' not in home.get_data()
    blocked = client.get(f'/mock-trial-simulator/course/{session_id}', follow_redirects=True)
    assert blocked.status_code == 200
    assert b'not enabled' in blocked.get_data() or b'Mock Trial' in blocked.get_data()

    with app.app_context():
        _enable_session_course(session_id)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _create_draft(app, client, session_id, title='Enabled then off')
    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'publish',
            'title': 'Enabled then off',
            'case_type': 'murder',
            'fir_narrative': 'FIR text',
            'incident_summary': 'Summary',
        },
        follow_redirects=True,
    )
    with app.app_context():
        replace_enabled_courses([])

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    listing = client.get('/mock-trial-simulator/')
    assert listing.status_code == 200
    assert f'/play/{case_id}'.encode() not in listing.get_data()
    play = client.get(f'/mock-trial-simulator/play/{case_id}', follow_redirects=True)
    assert play.status_code == 200
    assert play.request.path.rstrip('/') == '/mock-trial-simulator'


def _publish_generated(app, client, session_id, teacher_user):
    with app.app_context():
        for sid, name in (
            ('S001', 'Student One'),
            ('S002', 'Student Two'),
            ('S003', 'Student Three'),
            ('S004', 'Student Four'),
        ):
            _ensure_student_user(sid, name)
            _enroll(session_id, teacher_user['teacher_id'], sid, name)
        _enable_session_course(session_id)
    case_id = _create_draft(app, client, session_id)
    with patch('utils.ai.mock_trial.generate_case_pack', return_value=SAMPLE_PACK):
        client.post(
            f'/mock-trial-simulator/case/{case_id}',
            data={'action': 'generate', 'title': 'Courtyard homicide', 'case_type': 'murder'},
            follow_redirects=True,
        )
    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'publish',
            'title': 'Courtyard homicide',
            'case_type': 'murder',
            'fir_narrative': SAMPLE_PACK['fir']['narrative'],
            'incident_summary': SAMPLE_PACK['factsheet']['incident_summary'],
            'accused_narrative': SAMPLE_PACK['accused_statement']['narrative'],
        },
        follow_redirects=True,
    )
    return case_id


def test_teacher_assigns_roles_and_students_see_only_their_side(
    app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _publish_generated(app, client, session_id, teacher_user)

    with app.app_context():
        lay = next(w for w in db.session.get(MockTrialCase, case_id).witnesses if w.role == 'lay')
        witness_id = lay.id

    assign = client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'assign',
            'prosecution_ids': ['S001'],
            'defence_ids': ['S002'],
            f'witness_{witness_id}': 'S003',
        },
        follow_redirects=True,
    )
    assert assign.status_code == 200
    assert b'Cast' in assign.get_data() or b'assignments' in assign.get_data()

    with app.app_context():
        case = db.session.get(MockTrialCase, case_id)
        assert resolve_cast(case, 'S001')['side'] == 'prosecution'
        assert resolve_cast(case, 'S002')['side'] == 'defence'
        assert resolve_cast(case, 'S003')['kind'] == 'witness'
        assert resolve_cast(case, 'S004')['kind'] is None

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    prosec = client.get(f'/mock-trial-simulator/play/{case_id}?panel=brief').get_data(as_text=True)
    assert 'Complainant states the accused struck' in prosec
    assert 'I was at my sister' not in prosec
    assert 'saw the accused drop a dao' not in prosec
    save = client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data={'action': 'save_petition', 'draft_text': 'Search witnesses were not local (CrPC 103).'},
        follow_redirects=True,
    )
    assert save.status_code == 200
    assert 'Search witnesses were not local' in save.get_data(as_text=True)

    login_client(client, 'S002', role='student', window_id=windows['w1_id'])
    defence = client.get(f'/mock-trial-simulator/play/{case_id}?panel=brief').get_data(as_text=True)
    assert 'I was at my sister' in defence
    assert 'Complainant states the accused struck' not in defence
    assert 'saw the accused drop a dao' not in defence

    login_client(client, 'S003', role='student', window_id=windows['w1_id'])
    witness = client.get(f'/mock-trial-simulator/play/{case_id}?panel=character').get_data(as_text=True)
    assert 'saw the accused drop a dao' in witness
    assert 'Complainant states the accused struck' not in witness
    assert 'I was at my sister' not in witness
    notes = client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data={'action': 'save_witness_notes', 'student_notes': 'Admit the dao only on cross.'},
        follow_redirects=True,
    )
    assert notes.status_code == 200
    assert 'Admit the dao only on cross.' in notes.get_data(as_text=True)

    login_client(client, 'S004', role='student', window_id=windows['w1_id'])
    waiting = client.get(f'/mock-trial-simulator/play/{case_id}').get_data(as_text=True)
    assert 'not assigned' in waiting.lower()
    assert 'Complainant states the accused struck' not in waiting
    assert 'I was at my sister' not in waiting
    assert 'saw the accused drop a dao' not in waiting

    with app.app_context():
        petition = MockTrialPetition.query.filter_by(
            case_id=case_id, petition_type=MockTrialPetition.TYPE_VAKALATNAMA,
        ).first()
        assert petition and 'CrPC 103' in (petition.draft_text or '')
        assert MockTrialWitness.query.get(witness_id).student_notes.startswith('Admit')


def test_teacher_accepts_both_vakalatnamas_then_quiz_unlocks_exhibits(
    app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _publish_generated(app, client, session_id, teacher_user)
    with app.app_context():
        lay = next(w for w in db.session.get(MockTrialCase, case_id).witnesses if w.role == 'lay')
        witness_id = lay.id
    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'assign',
            'prosecution_ids': ['S001'],
            'defence_ids': ['S002'],
            f'witness_{witness_id}': 'S003',
        },
        follow_redirects=True,
    )

    with app.app_context():
        case = db.session.get(MockTrialCase, case_id)
        case.set_quiz_pack(dict(SAMPLE_QUIZ, allow_retake=True))
        for witness in case.witnesses:
            witness.unlock_min_score = 60 if witness.role == 'lay' else 90
        db.session.commit()
        names_0 = {item['name'] for item in unlocked_witnesses_for_score(case, 0)}
        names_60 = {item['name'] for item in unlocked_witnesses_for_score(case, 60)}
        names_89 = {item['name'] for item in unlocked_witnesses_for_score(case, 89)}
        assert 'SI Hasan' in names_0
        assert 'Dr. Nila' in names_0
        assert 'Fatema Begum' not in names_0
        assert 'Fatema Begum' in names_60
        assert 'SI Hasan' in names_60
        assert 'Dr. Nila' in names_60
        assert names_60 == names_89

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data={
            'action': 'submit_petition',
            'draft_text': 'Prosecution vakalatnama authorizing counsel to appear.',
        },
        follow_redirects=True,
    )
    waiting = client.get(f'/mock-trial-simulator/play/{case_id}?panel=vakalat').get_data(as_text=True)
    assert 'Waiting for the teacher' in waiting
    assert 'Seizure list' not in waiting
    assert '<h2 class="mts-step-title">Quiz</h2>' not in waiting

    login_client(client, 'S002', role='student', window_id=windows['w1_id'])
    client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data={
            'action': 'submit_petition',
            'draft_text': 'Defence vakalatnama authorizing counsel to appear.',
        },
        follow_redirects=True,
    )

    with app.app_context():
        papers = MockTrialPetition.query.filter_by(
            case_id=case_id, petition_type=MockTrialPetition.TYPE_VAKALATNAMA,
        ).all()
        assert len(papers) == 2
        prosec_id = next(p.id for p in papers if 'Prosecution' in (p.draft_text or ''))
        defence_id = next(p.id for p in papers if 'Defence' in (p.draft_text or ''))

    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    first = client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'accept_petition',
            'petition_id': str(prosec_id),
            'teacher_note': 'In order.',
        },
        follow_redirects=True,
    )
    assert first.status_code == 200
    assert b'both sides' in first.get_data()
    with app.app_context():
        assert db.session.get(MockTrialCase, case_id).current_phase != PHASE_QUIZ

    accept = client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'accept_petition',
            'petition_id': str(defence_id),
        },
        follow_redirects=True,
    )
    assert accept.status_code == 200
    assert b'Phase 3' in accept.get_data()
    with app.app_context():
        case = db.session.get(MockTrialCase, case_id)
        assert case.current_phase == PHASE_QUIZ
        assert MockTrialPetition.query.get(defence_id).status == MockTrialPetition.STATUS_ACCEPTED

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    quiz_page = client.get(f'/mock-trial-simulator/play/{case_id}?panel=quiz').get_data(as_text=True)
    assert '<h2 class="mts-step-title">Quiz</h2>' in quiz_page
    assert 'CrPC s.103 is mainly about' in quiz_page
    assert 'Seizure list' not in quiz_page
    assert 'Fatema Begum' not in quiz_page
    assert 'S003' not in quiz_page
    locked = client.get(f'/mock-trial-simulator/play/{case_id}?panel=witnesses').get_data(as_text=True)
    assert 'still locked' in locked
    assert 'Fatema Begum' not in locked
    with app.app_context():
        questions = build_discovery_quiz(db.session.get(MockTrialCase, case_id), SIDE_PROSECUTION)
        assert questions
        wrong = {
            'action': 'submit_quiz',
            **{
                f'q_{item["id"]}': next(
                    choice for choice in item['choices']
                    if ' '.join(choice.lower().split()) != item['answer']
                )
                for item in questions
            },
        }
        form = {
            'action': 'submit_quiz',
            **{
                f'q_{item["id"]}': next(
                    choice for choice in item['choices']
                    if ' '.join(choice.lower().split()) == item['answer']
                )
                for item in questions
            },
        }
    missed = client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data=wrong,
        follow_redirects=True,
    )
    missed_html = missed.get_data(as_text=True)
    assert 'mts-choice-mark bad' in missed_html
    assert 'mts-choice-mark ok' not in missed_html
    assert 'mts-choice is-ok' not in missed_html
    assert 'সঠিক উত্তর' not in missed_html
    locked_after_miss = client.get(
        f'/mock-trial-simulator/play/{case_id}?panel=witnesses'
    ).get_data(as_text=True)
    assert 'Fatema Begum' not in locked_after_miss
    passed = client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data=form,
        follow_redirects=True,
    )
    assert passed.status_code == 200
    passed_html = passed.get_data(as_text=True)
    assert 'mts-choice-mark ok' in passed_html
    assert 'mts-choice-mark bad' not in passed_html
    exhibits = client.get(f'/mock-trial-simulator/play/{case_id}?panel=exhibits').get_data(as_text=True)
    names = client.get(f'/mock-trial-simulator/play/{case_id}?panel=witnesses').get_data(as_text=True)
    assert 'Seizure list' in exhibits
    assert 'One dao recovered from a drain.' in exhibits
    assert 'Fatema Begum' in names
    assert 'S003' in names
    assert 'saw the accused drop a dao' not in exhibits
    assert 'saw the accused drop a dao' not in names


def test_quiz_retake_blocked_unless_teacher_allows(
    app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _publish_generated(app, client, session_id, teacher_user)
    with app.app_context():
        lay = next(w for w in db.session.get(MockTrialCase, case_id).witnesses if w.role == 'lay')
        witness_id = lay.id
    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'assign',
            'prosecution_ids': ['S001'],
            'defence_ids': ['S002'],
            f'witness_{witness_id}': 'S003',
        },
        follow_redirects=True,
    )
    with app.app_context():
        case = db.session.get(MockTrialCase, case_id)
        case.set_quiz_pack(SAMPLE_QUIZ)
        db.session.commit()
    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data={'action': 'submit_petition', 'draft_text': 'Prosecution vakalatnama.'},
        follow_redirects=True,
    )
    login_client(client, 'S002', role='student', window_id=windows['w1_id'])
    client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data={'action': 'submit_petition', 'draft_text': 'Defence vakalatnama.'},
        follow_redirects=True,
    )
    with app.app_context():
        papers = MockTrialPetition.query.filter_by(
            case_id=case_id, petition_type=MockTrialPetition.TYPE_VAKALATNAMA,
        ).all()
        prosec_id = next(p.id for p in papers if 'Prosecution' in (p.draft_text or ''))
        defence_id = next(p.id for p in papers if 'Defence' in (p.draft_text or ''))
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    teacher_quiz = client.get(f'/mock-trial-simulator/case/{case_id}?panel=quiz').get_data(as_text=True)
    assert 'স্টুডেন্ট আবার চেষ্টা করতে পারবে' in teacher_quiz
    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={'action': 'accept_petition', 'petition_id': str(prosec_id)},
        follow_redirects=True,
    )
    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={'action': 'accept_petition', 'petition_id': str(defence_id)},
        follow_redirects=True,
    )
    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    with app.app_context():
        questions = build_discovery_quiz(db.session.get(MockTrialCase, case_id), SIDE_PROSECUTION)
        wrong = {
            'action': 'submit_quiz',
            **{
                f'q_{item["id"]}': next(
                    choice for choice in item['choices']
                    if ' '.join(choice.lower().split()) != item['answer']
                )
                for item in questions
            },
        }
        right = {
            'action': 'submit_quiz',
            **{
                f'q_{item["id"]}': next(
                    choice for choice in item['choices']
                    if ' '.join(choice.lower().split()) == item['answer']
                )
                for item in questions
            },
        }
    first = client.post(f'/mock-trial-simulator/play/{case_id}', data=wrong, follow_redirects=True)
    first_html = first.get_data(as_text=True)
    assert 'mts-choice-mark bad' in first_html
    assert 'Retake quiz' not in first_html
    assert 'শিক্ষক আর চেষ্টা করার অনুমতি দেননি' in first_html
    second = client.post(f'/mock-trial-simulator/play/{case_id}', data=right, follow_redirects=True)
    assert b'not allowed another attempt' in second.get_data()
    with app.app_context():
        petition = MockTrialPetition.query.filter_by(
            case_id=case_id, petition_type=MockTrialPetition.TYPE_VAKALATNAMA,
        ).all()
        prosec = next(p for p in petition if 'Prosecution' in (p.draft_text or ''))
        assert prosec.quiz_score() == 0
        assert prosec.quiz_passed() is False


def test_cannot_place_same_student_on_both_sides(
    app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _publish_generated(app, client, session_id, teacher_user)
    blocked = client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'assign',
            'prosecution_ids': ['S001'],
            'defence_ids': ['S001'],
        },
        follow_redirects=True,
    )
    body = blocked.get_data(as_text=True)
    assert blocked.status_code == 200
    assert 'প্রসিকিউশন' in body or 'দুই দলে' in body
    with app.app_context():
        assert resolve_cast(db.session.get(MockTrialCase, case_id), 'S001')['kind'] is None


def test_teacher_can_add_and_generate_quiz(
    app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _publish_generated(app, client, session_id, teacher_user)

    page = client.get(f'/mock-trial-simulator/case/{case_id}')
    assert page.status_code == 200
    assert b'<span class="mts-step-title">Quiz</span>' in page.get_data()

    added = client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={'action': 'add_quiz_question', 'quiz_brief': 'CrPC s.103', 'quiz_gen_side': 'prosecution'},
        follow_redirects=True,
    )
    assert added.status_code == 200
    with app.app_context():
        qid = db.session.get(MockTrialCase, case_id).quiz_pack()['questions'][0]['id']
    saved = client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'save_quiz',
            'quiz_brief': 'CrPC s.103 search witnesses',
            'quiz_pass_score': '70',
            'quiz_witness_unlock_score': '50',
            'quiz_allow_retake_present': '1',
            'quiz_allow_retake': '1',
            'quiz_id': qid,
            f'quiz_{qid}_prompt': 'Who must witness a search under CrPC s.103?',
            f'quiz_{qid}_c1': 'Two or more respectable inhabitants of the locality',
            f'quiz_{qid}_c2': 'Only the investigating officer',
            f'quiz_{qid}_c3': 'The Sessions Judge',
            f'quiz_{qid}_c4': 'The accused’s surety',
            f'quiz_{qid}_answer_index': '1',
            f'quiz_{qid}_side': 'prosecution',
        },
        follow_redirects=True,
    )
    assert saved.status_code == 200
    with app.app_context():
        case = db.session.get(MockTrialCase, case_id)
        pack = case.quiz_pack()
        assert pack['pass_score'] == 70
        assert pack['witness_unlock_score'] == 50
        assert pack['allow_retake'] is True
        assert pack['brief'].startswith('CrPC s.103')
        prosec = quiz_questions_for_side(case, 'prosecution')
        defence = quiz_questions_for_side(case, 'defence')
        assert len(prosec) == 1
        assert prosec[0]['prompt'].startswith('Who must witness')
        assert defence == []

    with patch(
        'utils.ai.mock_trial.generate_quiz_questions',
        return_value=[{
            'prompt': 'Evidence Act s.27 covers?',
            'choices': [
                'Discovery of fact in consequence of information',
                'Hearsay exceptions only',
                'Character evidence',
                'Refreshing memory',
            ],
            'answer': 'Discovery of fact in consequence of information',
            'side': 'both',
        }],
    ):
        generated = client.post(
            f'/mock-trial-simulator/case/{case_id}',
            data={
                'action': 'generate_quiz',
                'quiz_brief': 'Evidence Act s.27',
                'quiz_count': '1',
                'quiz_gen_side': 'both',
                'quiz_pass_score': '70',
                'quiz_id': qid,
                f'quiz_{qid}_prompt': 'Who must witness a search under CrPC s.103?',
                f'quiz_{qid}_c1': 'Two or more respectable inhabitants of the locality',
                f'quiz_{qid}_c2': 'Only the investigating officer',
                f'quiz_{qid}_c3': 'The Sessions Judge',
                f'quiz_{qid}_c4': 'The accused’s surety',
                f'quiz_{qid}_answer_index': '1',
                f'quiz_{qid}_side': 'prosecution',
            },
            follow_redirects=True,
        )
    assert generated.status_code == 200
    generated_html = generated.get_data(as_text=True)
    assert 'Evidence Act s.27 covers' in generated_html
    assert 'name="quiz_q1_answer_index"' in generated_html
    assert '>সঠিক<' in generated_html
    with app.app_context():
        case = db.session.get(MockTrialCase, case_id)
        assert len(case.quiz_pack()['questions']) == 2
        assert len(quiz_questions_for_side(case, 'defence')) == 1
        assert len(quiz_questions_for_side(case, 'prosecution')) == 2


def test_pdf_font_css_splits_latin_and_bangla(app):
    with app.app_context():
        from utils.pdf_fonts import weasyprint_font_css
        css = weasyprint_font_css()
    assert 'PDFSerif' in css
    assert 'Kalpurush' in css or 'NotoBengali' in css
    assert 'U+0980-09FF' in css
    assert 'U+0000-024F' in css


def test_pdf_rich_text_wraps_bangla_runs():
    from blueprints.mock_trial_simulator.pdf import pdf_rich_text
    html = str(pdf_rich_text('Homicide / Murder (খুন)'))
    assert 'Homicide / Murder (' in html
    assert '<span class="bn">খুন</span>' in html
    assert '&lt;' in str(pdf_rich_text('a < b'))


def test_mock_trial_pdf_keeps_latin_readable(app, tmp_path):
    from flask import render_template

    from blueprints.mock_trial_simulator.pdf import section, write_html_pdf

    class _Case:
        id = 1
        title = 'State v. Karim — courtyard killing'

        def case_type_label(self):
            return 'Homicide / Murder (খুন)'

    with app.test_request_context('/'):
        html = render_template(
            'mock_trial_simulator/paper_pdf.html',
            case=_Case(),
            course_label='Law 4208 — Criminal Trial Advocacy',
            title='First Information Report (FIR)',
            sections=[section(
                'First Information Report (FIR)',
                'Complainant states the accused struck the victim after a land dispute in খুলনা.',
                meta=[('Police station', 'Khalishpur'), ('GD / FIR no.', '112')],
            )],
        )
        assert 'class="bn"' in html
        pdf = write_html_pdf(html)
    assert pdf.startswith(b'%PDF')
    out = tmp_path / 'fir.pdf'
    out.write_bytes(pdf)
    text = ''
    try:
        from pypdf import PdfReader
        text = ''.join(page.extract_text() or '' for page in PdfReader(str(out)).pages)
    except Exception:
        text = ''
    if text:
        assert 'Police station' in text
        assert 'ppolice' not in text.lower()
        assert 'Firstt' not in text
        assert 'Khalishpur' in text


def _fake_pdf(html):
    return f'%PDF-1.4\n{html}'.encode('utf-8')


def _denied_pdf(client, url):
    rv = client.get(url)
    assert rv.status_code in (302, 303)
    assert rv.mimetype != 'application/pdf'
    return rv


@patch('blueprints.mock_trial_simulator.pdf.write_html_pdf', side_effect=_fake_pdf)
def test_pdf_downloads_respect_roles_and_unlocks(
    _mock_pdf, app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _publish_generated(app, client, session_id, teacher_user)
    with app.app_context():
        case = db.session.get(MockTrialCase, case_id)
        lay = next(w for w in case.witnesses if w.role == 'lay')
        witness_id = lay.id
        exhibit_id = case.exhibits[0].id
        case.set_quiz_pack(SAMPLE_QUIZ)
        db.session.commit()

    page = client.get(f'/mock-trial-simulator/case/{case_id}?panel=papers').get_data(as_text=True)
    assert f'/case/{case_id}/pdf/fir' in page
    assert f'/case/{case_id}/pdf/witnesses' in page
    exhibits_page = client.get(f'/mock-trial-simulator/case/{case_id}?panel=exhibits').get_data(as_text=True)
    assert f'/case/{case_id}/pdf/exhibit/{exhibit_id}' in exhibits_page

    fir = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/fir')
    assert fir.status_code == 200
    assert fir.mimetype == 'application/pdf'
    fir_html = fir.get_data(as_text=True)
    assert 'Complainant states the accused struck' in fir_html
    assert 'I was at my sister' not in fir_html

    accused = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/accused')
    assert accused.status_code == 200
    assert 'I was at my sister' in accused.get_data(as_text=True)

    card = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/witness-card/{witness_id}')
    assert card.status_code == 200
    assert 'saw the accused drop a dao' in card.get_data(as_text=True)

    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'assign',
            'prosecution_ids': ['S001'],
            'defence_ids': ['S002'],
            f'witness_{witness_id}': 'S003',
        },
        follow_redirects=True,
    )

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    play = client.get(f'/mock-trial-simulator/play/{case_id}?panel=brief').get_data(as_text=True)
    assert f'/case/{case_id}/pdf/fir' in play
    assert f'/case/{case_id}/pdf/accused' not in play
    student_fir = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/fir')
    assert student_fir.status_code == 200
    assert 'Complainant states the accused struck' in student_fir.get_data(as_text=True)
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/accused')
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/factsheet')
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/exhibit/{exhibit_id}')
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/witnesses')
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/witness-card/{witness_id}')
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/vakalatnama/defence')

    client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data={
            'action': 'submit_petition',
            'draft_text': 'Prosecution vakalatnama authorizing counsel to appear.',
        },
        follow_redirects=True,
    )
    vakalat = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/vakalatnama/prosecution')
    assert vakalat.status_code == 200
    assert 'Prosecution vakalatnama authorizing counsel' in vakalat.get_data(as_text=True)

    login_client(client, 'S002', role='student', window_id=windows['w1_id'])
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/fir')
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/vakalatnama/prosecution')
    defence_statement = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/accused')
    assert defence_statement.status_code == 200
    assert 'I was at my sister' in defence_statement.get_data(as_text=True)
    client.post(
        f'/mock-trial-simulator/play/{case_id}',
        data={
            'action': 'submit_petition',
            'draft_text': 'Defence vakalatnama authorizing counsel to appear.',
        },
        follow_redirects=True,
    )

    login_client(client, 'S003', role='student', window_id=windows['w1_id'])
    witness_pdf = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/witness-card/{witness_id}')
    assert witness_pdf.status_code == 200
    witness_html = witness_pdf.get_data(as_text=True)
    assert 'saw the accused drop a dao' in witness_html
    assert 'Complainant states the accused struck' not in witness_html
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/fir')
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/exhibits')

    login_client(client, 'S004', role='student', window_id=windows['w1_id'])
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/fir')
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/pack')

    with app.app_context():
        papers = MockTrialPetition.query.filter_by(
            case_id=case_id, petition_type=MockTrialPetition.TYPE_VAKALATNAMA,
        ).all()
        prosec_id = next(p.id for p in papers if 'Prosecution' in (p.draft_text or ''))
        defence_id = next(p.id for p in papers if 'Defence' in (p.draft_text or ''))
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={'action': 'accept_petition', 'petition_id': str(prosec_id)},
        follow_redirects=True,
    )
    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={'action': 'accept_petition', 'petition_id': str(defence_id)},
        follow_redirects=True,
    )

    login_client(client, 'S001', role='student', window_id=windows['w1_id'])
    _denied_pdf(client, f'/mock-trial-simulator/case/{case_id}/pdf/exhibit/{exhibit_id}')
    with app.app_context():
        questions = build_discovery_quiz(db.session.get(MockTrialCase, case_id), SIDE_PROSECUTION)
        form = {
            'action': 'submit_quiz',
            **{
                f'q_{item["id"]}': next(
                    choice for choice in item['choices']
                    if ' '.join(choice.lower().split()) == item['answer']
                )
                for item in questions
            },
        }
    client.post(f'/mock-trial-simulator/play/{case_id}', data=form, follow_redirects=True)
    exhibit_pdf = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/exhibit/{exhibit_id}')
    assert exhibit_pdf.status_code == 200
    exhibit_html = exhibit_pdf.get_data(as_text=True)
    assert 'One dao recovered from a drain' in exhibit_html
    assert 'saw the accused drop a dao' not in exhibit_html
    names = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/witnesses')
    assert names.status_code == 200
    names_html = names.get_data(as_text=True)
    assert 'Fatema Begum' in names_html
    assert 'S003' in names_html
    assert 'saw the accused drop a dao' not in names_html
    pack = client.get(f'/mock-trial-simulator/case/{case_id}/pdf/pack')
    assert pack.status_code == 200
    pack_html = pack.get_data(as_text=True)
    assert 'Complainant states the accused struck' in pack_html
    assert 'I was at my sister' not in pack_html
    assert 'Prosecution vakalatnama authorizing counsel' in pack_html


def test_io_dashboard_has_paper_template_scaffold(
    app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _publish_generated(app, client, session_id, teacher_user)
    with app.app_context():
        io = next(w for w in db.session.get(MockTrialCase, case_id).witnesses if w.role == 'io')
        io_id = io.id
    client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={'action': 'assign', 'prosecution_ids': ['S001'], f'witness_{io_id}': 'S003'},
        follow_redirects=True,
    )
    login_client(client, 'S003', role='student', window_id=windows['w1_id'])
    home = client.get(f'/mock-trial-simulator/play/{case_id}').get_data(as_text=True)
    assert 'Case documents' in home
    papers = client.get(f'/mock-trial-simulator/play/{case_id}?panel=papers').get_data(as_text=True)
    assert 'টেমপ্লেট এখনো যোগ হয়নি' in papers


def test_io_can_save_registered_paper_template(
    app, client, teacher_user, class_session_w1, windows,
):
    from blueprints.mock_trial_simulator import paper_templates as pt

    previous = list(pt.WITNESS_PAPER_TEMPLATES[WITNESS_IO])
    pt.WITNESS_PAPER_TEMPLATES[WITNESS_IO] = [{
        'key': 'seizure_list',
        'title': 'Seizure list',
        'title_bn': 'জব্দনামা',
        'description': 'List seized items.',
        'fields': [{'key': 'items', 'label': 'Items seized', 'type': 'textarea'}],
    }]
    try:
        session_id = class_session_w1['session_id']
        login_client(client, teacher_user['username'], window_id=windows['w1_id'])
        case_id = _publish_generated(app, client, session_id, teacher_user)
        with app.app_context():
            io = next(w for w in db.session.get(MockTrialCase, case_id).witnesses if w.role == 'io')
            io_id = io.id
        client.post(
            f'/mock-trial-simulator/case/{case_id}',
            data={'action': 'assign', 'prosecution_ids': ['S001'], f'witness_{io_id}': 'S003'},
            follow_redirects=True,
        )
        login_client(client, 'S003', role='student', window_id=windows['w1_id'])
        listed = client.get(f'/mock-trial-simulator/play/{case_id}?panel=papers').get_data(as_text=True)
        assert 'জব্দনামা' in listed
        saved = client.post(
            f'/mock-trial-simulator/play/{case_id}',
            data={
                'action': 'save_witness_paper',
                'template_key': 'seizure_list',
                'f_items': 'One dao from the drain.',
            },
            follow_redirects=True,
        )
        assert saved.status_code == 200
        assert 'One dao from the drain.' in saved.get_data(as_text=True)
        with app.app_context():
            paper = MockTrialWitnessPaper.query.filter_by(
                witness_id=io_id, template_key='seizure_list',
            ).first()
            assert paper is not None
            assert paper.body().get('items') == 'One dao from the drain.'
            assert paper.status == MockTrialWitnessPaper.STATUS_DRAFT
    finally:
        pt.WITNESS_PAPER_TEMPLATES[WITNESS_IO] = previous


def test_teacher_can_add_and_delete_witnesses(
    app, client, teacher_user, class_session_w1, windows,
):
    session_id = class_session_w1['session_id']
    with app.app_context():
        _enable_session_course(session_id)
    login_client(client, teacher_user['username'], window_id=windows['w1_id'])
    case_id = _create_draft(app, client, session_id)
    page = client.get(f'/mock-trial-simulator/case/{case_id}?panel=witnesses')
    assert page.status_code == 200
    assert b'Add witness' in page.get_data()

    added = client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={
            'action': 'add_witness',
            'panel': 'witnesses',
            'new_witness_name': 'Abdul Karim',
            'new_witness_role': 'lay',
            'new_witness_called_by': 'defence',
            'new_witness_designation': 'Shopkeeper',
        },
        follow_redirects=True,
    )
    assert added.status_code == 200
    assert b'Abdul Karim' in added.get_data()
    with app.app_context():
        case = db.session.get(MockTrialCase, case_id)
        assert len(case.witnesses) == 1
        witness = case.witnesses[0]
        assert witness.name == 'Abdul Karim'
        assert witness.called_by == 'defence'
        assert witness.designation == 'Shopkeeper'
        witness_id = witness.id

    deleted = client.post(
        f'/mock-trial-simulator/case/{case_id}',
        data={'delete_witness_id': str(witness_id), 'panel': 'witnesses'},
        follow_redirects=True,
    )
    assert deleted.status_code == 200
    with app.app_context():
        assert len(db.session.get(MockTrialCase, case_id).witnesses) == 0
