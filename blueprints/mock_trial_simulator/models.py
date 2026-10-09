"""Hybrid AI Mock Trial Simulator — Bangladesh CrPC / Evidence Act cases."""
import json
from datetime import datetime

from extensions import db


CASE_TYPES = (
    ('murder', 'Homicide / Murder (খুন)'),
    ('robbery', 'Robbery / Dacoity (ডাকাতি)'),
    ('theft', 'Theft (চুরি)'),
    ('hurt', 'Hurt / Grievous Hurt (আঘাত)'),
    ('kidnapping', 'Kidnapping (অপহরণ)'),
    ('narcotics', 'Narcotics'),
    ('cheating', 'Cheating / Fraud (প্রতারণা)'),
    ('custom', 'Custom brief'),
)

CASE_TYPE_LABELS = dict(CASE_TYPES)

WITNESS_LAY = 'lay'
WITNESS_IO = 'io'
WITNESS_EXPERT = 'expert'
WITNESS_ROLES = (
    (WITNESS_LAY, 'Lay witness (সাধারণ সাক্ষী)'),
    (WITNESS_IO, 'Investigating Officer'),
    (WITNESS_EXPERT, 'Expert (Medical / Forensic)'),
)
WITNESS_ROLE_LABELS = dict(WITNESS_ROLES)
OFFICIAL_PROSECUTION_ROLES = (WITNESS_IO, WITNESS_EXPERT)


def is_official_prosecution_witness(witness):
    """IO and expert are always prosecution witnesses and are never quiz-locked."""
    role = getattr(witness, 'role', None)
    if role is None and isinstance(witness, dict):
        role = witness.get('role')
    return role in OFFICIAL_PROSECUTION_ROLES

STATUS_DRAFT = 'draft'
STATUS_PUBLISHED = 'published'
STATUS_ARCHIVED = 'archived'

SIDE_PROSECUTION = 'prosecution'
SIDE_DEFENCE = 'defence'

PHASE_PREP = 1
PHASE_DISCOVERY = 2
PHASE_QUIZ = 3
PHASE_INTERVIEW = 4
PHASE_TRIAL = 5
PHASE_LABELS = {
    PHASE_PREP: 'Case Preparation',
    PHASE_DISCOVERY: 'Discovery & drafting',
    PHASE_QUIZ: 'Quiz',
    PHASE_INTERVIEW: 'Pre-trial interview',
    PHASE_TRIAL: 'Case dossier & physical trial',
}


def _parse_json(raw, fallback):
    if not raw:
        return fallback
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return data if isinstance(data, type(fallback)) else fallback


def dump_json(value):
    return json.dumps(value or {}, ensure_ascii=False)


def normalize_course_code(code):
    return ' '.join((code or '').split()).upper()


class MockTrialEnabledCourse(db.Model):
    """Admin allow-list: only these catalog courses may use Mock Trial."""
    __tablename__ = 'mock_trial_enabled_course'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, unique=True, index=True)
    course_code = db.Column(db.String(50), nullable=False, index=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    course = db.relationship('Course', backref=db.backref('mock_trial_access', uselist=False))


def _enabled_lookup():
    """Return (course_ids, course_codes) that admin has turned on."""
    try:
        rows = MockTrialEnabledCourse.query.filter_by(is_enabled=True).all()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return set(), set()
    ids = {row.course_id for row in rows if row.course_id}
    codes = {normalize_course_code(row.course_code) for row in rows if row.course_code}
    return ids, codes


def session_is_mock_trial_enabled(session_obj):
    """True when admin enabled this class session's catalog course."""
    if not session_obj:
        return False
    ids, codes = _enabled_lookup()
    if not ids and not codes:
        return False
    try:
        from blueprints.course_management.models import CourseSessionAssignment
        assignment = CourseSessionAssignment.query.filter_by(session_id=session_obj.id).first()
    except Exception:
        assignment = None
    if assignment is not None and assignment.course_id in ids:
        return True
    code = normalize_course_code(getattr(session_obj, 'course_code', None))
    return bool(code and code in codes)


def filter_mock_trial_sessions(sessions):
    return [item for item in (sessions or []) if session_is_mock_trial_enabled(item)]


def replace_enabled_courses(course_ids):
    """Replace the allow-list with the given Course ids. Returns saved count."""
    from blueprints.course_management.models import Course

    wanted = set()
    for raw in course_ids or []:
        try:
            wanted.add(int(raw))
        except (TypeError, ValueError):
            continue
    MockTrialEnabledCourse.query.delete()
    saved = 0
    if wanted:
        courses = Course.query.filter(Course.id.in_(wanted)).all()
        for course in courses:
            db.session.add(MockTrialEnabledCourse(
                course_id=course.id,
                course_code=normalize_course_code(course.course_code) or course.course_code,
                is_enabled=True,
            ))
            saved += 1
    db.session.commit()
    return saved


class MockTrialCase(db.Model):
    """One mock-trial game attached to a class session."""
    __tablename__ = 'mock_trial_case'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('class_session.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    case_type = db.Column(db.String(40), nullable=False, default='murder')
    extra_brief = db.Column(db.Text, nullable=True)
    prosecution_witness_count = db.Column(db.Integer, nullable=True)
    defence_witness_count = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT, index=True)
    current_phase = db.Column(db.Integer, nullable=False, default=PHASE_PREP)
    master_factsheet_json = db.Column(db.Text, nullable=True)
    fir_json = db.Column(db.Text, nullable=True)
    accused_statement_json = db.Column(db.Text, nullable=True)
    quiz_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime, nullable=True)

    session = db.relationship(
        'Session',
        backref=db.backref('mock_trial_cases', lazy='dynamic'),
    )
    teacher = db.relationship('Teacher', backref=db.backref('mock_trial_cases', lazy='dynamic'))
    witnesses = db.relationship(
        'MockTrialWitness',
        backref='case',
        lazy='selectin',
        cascade='all, delete-orphan',
        order_by='MockTrialWitness.sort_order, MockTrialWitness.id',
    )
    exhibits = db.relationship(
        'MockTrialExhibit',
        backref='case',
        lazy='selectin',
        cascade='all, delete-orphan',
        order_by='MockTrialExhibit.sort_order, MockTrialExhibit.id',
    )
    teams = db.relationship(
        'MockTrialTeam',
        backref='case',
        lazy='selectin',
        cascade='all, delete-orphan',
        order_by='MockTrialTeam.id',
    )

    def case_type_label(self):
        return CASE_TYPE_LABELS.get(self.case_type, self.case_type or 'Case')

    def phase_label(self):
        return PHASE_LABELS.get(int(self.current_phase or PHASE_PREP), 'Preparation')

    def is_published(self):
        return self.status == STATUS_PUBLISHED

    def is_draft(self):
        return self.status == STATUS_DRAFT

    def factsheet(self):
        return _parse_json(self.master_factsheet_json, {})

    def fir(self):
        return _parse_json(self.fir_json, {})

    def accused_statement(self):
        return _parse_json(self.accused_statement_json, {})

    def set_factsheet(self, data):
        self.master_factsheet_json = dump_json(data if isinstance(data, dict) else {})

    def set_fir(self, data):
        self.fir_json = dump_json(data if isinstance(data, dict) else {})

    def set_accused_statement(self, data):
        self.accused_statement_json = dump_json(data if isinstance(data, dict) else {})

    def quiz_pack(self):
        return normalize_quiz_pack(_parse_json(self.quiz_json, {}))

    def set_quiz_pack(self, data):
        self.quiz_json = dump_json(normalize_quiz_pack(data))

    def public_caption(self):
        sheet = self.factsheet()
        return {
            'title': self.title,
            'case_type': self.case_type_label(),
            'date_time': (sheet.get('date_time') or '').strip(),
            'place': (sheet.get('place') or '').strip(),
            'legal_provisions': [
                str(item).strip()
                for item in (sheet.get('legal_provisions') or [])
                if str(item).strip()
            ],
        }


class MockTrialWitness(db.Model):
    """AI-generated (teacher-edited) witness with a hidden instruction card."""
    __tablename__ = 'mock_trial_witness'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('mock_trial_case.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default=WITNESS_LAY)
    called_by = db.Column(db.String(20), nullable=False, default=SIDE_PROSECUTION)
    name = db.Column(db.String(120), nullable=False)
    designation = db.Column(db.String(200), nullable=True)
    instruction_card_json = db.Column(db.Text, nullable=True)
    assigned_student_id = db.Column(db.String(50), nullable=True, index=True)
    assigned_student_name = db.Column(db.String(100), nullable=True)
    student_notes = db.Column(db.Text, nullable=True)
    is_unlocked = db.Column(db.Boolean, nullable=False, default=False)
    unlock_min_score = db.Column(db.Integer, nullable=False, default=60)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    papers = db.relationship(
        'MockTrialWitnessPaper',
        backref='witness',
        lazy='selectin',
        cascade='all, delete-orphan',
        order_by='MockTrialWitnessPaper.id',
    )

    def role_label(self):
        return WITNESS_ROLE_LABELS.get(self.role, self.role)

    def is_official_prosecution(self):
        return is_official_prosecution_witness(self)

    def side_label(self):
        if self.is_official_prosecution():
            return 'Prosecution'
        return 'Defence' if (self.called_by or SIDE_PROSECUTION) == SIDE_DEFENCE else 'Prosecution'

    def card(self):
        return _parse_json(self.instruction_card_json, {})

    def set_card(self, data):
        self.instruction_card_json = dump_json(data if isinstance(data, dict) else {})

    def public_identity(self):
        """Name and real player id after the quiz unlock — never hidden facts."""
        return {
            'name': self.name,
            'role': self.role,
            'role_label': self.role_label(),
            'called_by': SIDE_PROSECUTION if self.is_official_prosecution() else (self.called_by or SIDE_PROSECUTION),
            'side_label': self.side_label(),
            'designation': self.designation or '',
            'player_id': (self.assigned_student_id or '').strip(),
            'player_name': (self.assigned_student_name or '').strip(),
        }


class MockTrialWitnessPaper(db.Model):
    """IO / expert draft of a case paper, keyed to a catalog template."""
    __tablename__ = 'mock_trial_witness_paper'
    __table_args__ = (
        db.UniqueConstraint('witness_id', 'template_key', name='uq_mock_trial_witness_paper'),
    )

    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('mock_trial_case.id'), nullable=False, index=True)
    witness_id = db.Column(db.Integer, db.ForeignKey('mock_trial_witness.id'), nullable=False, index=True)
    template_key = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(200), nullable=True)
    body_json = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)

    def body(self):
        return _parse_json(self.body_json, {})

    def set_body(self, data):
        self.body_json = dump_json(data if isinstance(data, dict) else {})


def get_or_create_witness_paper(witness, spec):
    key = (spec or {}).get('key') or ''
    paper = next((item for item in (witness.papers or []) if item.template_key == key), None)
    if paper is None:
        paper = MockTrialWitnessPaper(
            case_id=witness.case_id,
            witness_id=witness.id,
            template_key=key[:80],
            title=((spec or {}).get('title_bn') or (spec or {}).get('title') or key)[:200] or None,
            status=MockTrialWitnessPaper.STATUS_DRAFT,
        )
        paper.set_body({})
        witness.papers.append(paper)
    return paper


class MockTrialExhibit(db.Model):
    """Seizure list, PM report, CCTV note, case diary, etc."""
    __tablename__ = 'mock_trial_exhibit'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('mock_trial_case.id'), nullable=False, index=True)
    exhibit_key = db.Column(db.String(50), nullable=False, default='other')
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    body_json = db.Column(db.Text, nullable=True)
    is_unlocked = db.Column(db.Boolean, nullable=False, default=False)
    unlock_min_score = db.Column(db.Integer, nullable=False, default=60)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def body(self):
        return _parse_json(self.body_json, {})

    def set_body(self, data):
        self.body_json = dump_json(data if isinstance(data, dict) else {})


class MockTrialTeam(db.Model):
    """Prosecution or defence side (Phase 2+)."""
    __tablename__ = 'mock_trial_team'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('mock_trial_case.id'), nullable=False, index=True)
    side = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship(
        'MockTrialTeamMember',
        backref='team',
        lazy='selectin',
        cascade='all, delete-orphan',
        order_by='MockTrialTeamMember.id',
    )


class MockTrialTeamMember(db.Model):
    __tablename__ = 'mock_trial_team_member'
    __table_args__ = (
        db.UniqueConstraint('team_id', 'student_id', name='uq_mock_trial_team_student'),
    )

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('mock_trial_team.id'), nullable=False, index=True)
    student_id = db.Column(db.String(50), nullable=False, index=True)
    student_name = db.Column(db.String(100), nullable=True)


class MockTrialPetition(db.Model):
    """Vakalatnama (ওকালতনামা) gateway (Phase 2). Legacy 103/207 rows still load."""
    __tablename__ = 'mock_trial_petition'

    TYPE_VAKALATNAMA = 'vakalatnama'
    TYPE_103 = 'crpc_103'
    TYPE_207 = 'crpc_207'

    @classmethod
    def types_for_side(cls, side):
        if side == SIDE_DEFENCE:
            return (cls.TYPE_VAKALATNAMA, cls.TYPE_207)
        return (cls.TYPE_VAKALATNAMA, cls.TYPE_103)
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('mock_trial_case.id'), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('mock_trial_team.id'), nullable=True, index=True)
    petition_type = db.Column(db.String(20), nullable=False)
    draft_text = db.Column(db.Text, nullable=True)
    ai_eval_json = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = db.relationship('MockTrialCase', backref=db.backref('petitions', lazy='dynamic'))
    team = db.relationship('MockTrialTeam', backref=db.backref('petitions', lazy='dynamic'))

    def meta(self):
        return _parse_json(self.ai_eval_json, {})

    def set_meta(self, data):
        merged = self.meta()
        if isinstance(data, dict):
            merged.update(data)
        self.ai_eval_json = dump_json(merged)

    def teacher_note(self):
        return (self.meta().get('teacher_note') or '').strip()

    def quiz_passed(self):
        return bool(self.meta().get('quiz_passed'))

    def quiz_score(self):
        try:
            return int(self.meta().get('quiz_score') or 0)
        except (TypeError, ValueError):
            return 0

    def quiz_answers(self):
        raw = self.meta().get('quiz_answers') or {}
        if not isinstance(raw, dict):
            return {}
        return {str(key): str(value or '') for key, value in raw.items()}

    def quiz_results(self):
        raw = self.meta().get('quiz_results') or {}
        if not isinstance(raw, dict):
            return {}
        return {str(key): bool(value) for key, value in raw.items()}

    def quiz_attempted(self):
        return bool(self.quiz_results() or self.quiz_answers())


def _norm_answer(text):
    return ' '.join((text or '').lower().split())


QUIZ_SIDES = (SIDE_PROSECUTION, SIDE_DEFENCE, 'both')


def _pass_score(value, default=60):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(100, number))


def _as_bool(value, default=False):
    if value in (None, ''):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def next_quiz_id(questions):
    highest = 0
    for item in questions or []:
        raw = str((item or {}).get('id') or '').strip()
        if raw.startswith('q') and raw[1:].isdigit():
            highest = max(highest, int(raw[1:]))
    return f'q{highest + 1}'


def normalize_quiz_question(raw, fallback_id):
    item = raw if isinstance(raw, dict) else {}
    qid = str(item.get('id') or fallback_id or 'q1').strip()[:40] or 'q1'
    if not qid[0].isalpha():
        qid = f'q{qid}'
    prompt = str(item.get('prompt') or item.get('question') or '').strip()[:800]
    raw_choices = item.get('choices') or item.get('options') or []
    if isinstance(raw_choices, str):
        raw_choices = [part.strip() for part in raw_choices.splitlines()]
    choices = []
    seen = set()
    for choice in raw_choices:
        text = str(choice or '').strip()[:400]
        key = _norm_answer(text)
        if text and key not in seen:
            seen.add(key)
            choices.append(text)
    while len(choices) < 4:
        choices.append('')
    choices = choices[:4]
    answer_text = str(item.get('answer') or item.get('correct') or item.get('answer_label') or '').strip()
    if not answer_text:
        try:
            answer_text = choices[int(item.get('answer_index')) - 1]
        except (TypeError, ValueError, IndexError):
            answer_text = ''
    matched = ''
    for choice in choices:
        if choice and _norm_answer(choice) == _norm_answer(answer_text):
            matched = choice
            break
    if not matched:
        matched = answer_text
    side = str(item.get('side') or 'both').strip().lower()
    if side in ('defense', 'd', 'accused'):
        side = SIDE_DEFENCE
    if side in ('p', 'state'):
        side = SIDE_PROSECUTION
    if side not in QUIZ_SIDES:
        side = 'both'
    return {
        'id': qid,
        'prompt': prompt,
        'choices': choices,
        'answer': _norm_answer(matched) if matched else '',
        'answer_label': matched,
        'side': side,
    }


def normalize_quiz_pack(raw):
    data = raw if isinstance(raw, dict) else {}
    questions = []
    seen_ids = set()
    for index, item in enumerate(data.get('questions') or [], start=1):
        row = normalize_quiz_question(item, f'q{index}')
        qid = row['id']
        suffix = 2
        while qid in seen_ids:
            qid = f'{row["id"]}_{suffix}'
            suffix += 1
        row['id'] = qid
        seen_ids.add(qid)
        questions.append(row)
    pass_score = _pass_score(data.get('pass_score'))
    witness_raw = data.get('witness_unlock_score')
    witness_unlock = pass_score if witness_raw in (None, '') else _pass_score(witness_raw)
    return {
        'brief': str(data.get('brief') or '').strip()[:12000],
        'pass_score': pass_score,
        'witness_unlock_score': witness_unlock,
        'allow_retake': _as_bool(data.get('allow_retake'), False),
        'questions': questions,
    }


def unlocked_exhibits_for_score(case, score):
    score = int(score or 0)
    return [
        exhibit
        for exhibit in (case.exhibits or [])
        if score >= int(getattr(exhibit, 'unlock_min_score', 0) or 0)
    ]


def witness_unlock_need(witness, case=None):
    if is_official_prosecution_witness(witness):
        return 0
    raw = getattr(witness, 'unlock_min_score', None)
    if raw not in (None, ''):
        try:
            return max(0, min(100, int(raw)))
        except (TypeError, ValueError):
            pass
    pack = case.quiz_pack() if case else {}
    return int((pack or {}).get('witness_unlock_score') or (pack or {}).get('pass_score') or 60)


def unlocked_witnesses_for_score(case, score):
    score = int(score or 0)
    return [
        witness.public_identity()
        for witness in (case.witnesses or [])
        if score >= witness_unlock_need(witness, case)
    ]


def locked_witness_unlocks(case, score):
    score = int(score or 0)
    return [
        witness_unlock_need(witness, case)
        for witness in (case.witnesses or [])
        if score < witness_unlock_need(witness, case)
    ]


def quiz_questions_for_side(case, side):
    """Teacher-authored MCQs for this side. Incomplete rows stay off the student paper."""
    pack = case.quiz_pack() if case else normalize_quiz_pack({})
    out = []
    for item in pack.get('questions') or []:
        if not (item.get('prompt') or '').strip() or not item.get('answer'):
            continue
        filled = [choice for choice in (item.get('choices') or []) if (choice or '').strip()]
        if len(filled) < 2:
            continue
        qside = item.get('side') or 'both'
        if qside not in ('both', side):
            continue
        out.append({
            'id': item['id'],
            'prompt': item['prompt'],
            'choices': filled,
            'answer': item['answer'],
        })
    return out


def build_discovery_quiz(case, side):
    return quiz_questions_for_side(case, side)


def public_quiz(questions, answers=None, results=None):
    answers = answers or {}
    results = results or {}
    out = []
    for item in questions or []:
        if not item:
            continue
        qid = item['id']
        row = {
            'id': qid,
            'prompt': item['prompt'],
            'choices': item['choices'],
            'given': answers.get(qid) or '',
            'marked_correct': None,
        }
        if qid in results:
            row['marked_correct'] = bool(results[qid])
        out.append(row)
    return out


def grade_discovery_quiz(questions, answers, pass_score=60):
    """Score an attempt. Results say only whether each given answer was right."""
    answers = answers or {}
    total = len(questions or [])
    if not total:
        return 0, False, {}, {}
    correct = 0
    result_map = {}
    given_map = {}
    for item in questions:
        qid = item['id']
        given = answers.get(qid)
        given_map[qid] = given or ''
        ok = bool(_norm_answer(given) and _norm_answer(given) == item.get('answer'))
        result_map[qid] = ok
        if ok:
            correct += 1
    score = int(round(100 * correct / total))
    return score, score >= _pass_score(pass_score), result_map, given_map


def score_discovery_quiz(questions, answers, pass_score=60):
    score, passed, _, _ = grade_discovery_quiz(questions, answers, pass_score)
    return score, passed


def team_for_side(case, side):
    for team in case.teams or []:
        if team.side == side:
            return team
    return None


def ensure_side_teams(case):
    if team_for_side(case, SIDE_PROSECUTION) is None:
        case.teams.append(MockTrialTeam(side=SIDE_PROSECUTION, name='Prosecution'))
    if team_for_side(case, SIDE_DEFENCE) is None:
        case.teams.append(MockTrialTeam(side=SIDE_DEFENCE, name='Defence'))
    return case


def resolve_cast(case, student_id):
    """Which role a course student holds on this case (exclusive)."""
    empty = {'kind': None, 'team': None, 'witness': None, 'side': None, 'label': None}
    if not case or not student_id:
        return empty
    sid = str(student_id).strip()
    for witness in case.witnesses or []:
        if (witness.assigned_student_id or '').strip() == sid:
            return {
                'kind': 'witness',
                'team': None,
                'witness': witness,
                'side': None,
                'label': f'Witness — {witness.name}',
            }
    for team in case.teams or []:
        for member in team.members or []:
            if (member.student_id or '').strip() == sid:
                label = 'Prosecution' if team.side == SIDE_PROSECUTION else 'Defence'
                return {
                    'kind': 'counsel',
                    'team': team,
                    'witness': None,
                    'side': team.side,
                    'label': label,
                }
    return empty


def add_manual_witness(case, name, role=WITNESS_LAY, called_by=SIDE_PROSECUTION, designation=None):
    """Teacher-created witness with an empty instruction card."""
    name = (name or '').strip()[:120]
    if not name:
        raise ValueError('Give the witness a name.')
    role = role if role in WITNESS_ROLE_LABELS else WITNESS_LAY
    if role in OFFICIAL_PROSECUTION_ROLES:
        if any(item.role == role for item in (case.witnesses or [])):
            raise ValueError(
                'This case already has an Investigating Officer.'
                if role == WITNESS_IO
                else 'This case already has an expert witness.'
            )
        called_by = SIDE_PROSECUTION
        unlock = 0
    else:
        called_by = called_by if called_by in (SIDE_PROSECUTION, SIDE_DEFENCE) else SIDE_PROSECUTION
        unlock = int((case.quiz_pack() or {}).get('witness_unlock_score') or 60)
    sort_order = max((item.sort_order for item in (case.witnesses or [])), default=-1) + 1
    witness = MockTrialWitness(
        role=role,
        called_by=called_by,
        name=name,
        designation=(designation or '').strip()[:200] or None,
        is_unlocked=False,
        unlock_min_score=max(0, min(100, unlock)),
        sort_order=sort_order,
    )
    witness.set_card({})
    case.witnesses.append(witness)
    return witness


def delete_case_witness(case, witness_id):
    try:
        witness_id = int(witness_id)
    except (TypeError, ValueError):
        return False
    witness = next((item for item in (case.witnesses or []) if item.id == witness_id), None)
    if witness is None:
        return False
    case.witnesses.remove(witness)
    return True


def apply_cast(case, roster, prosecution_ids, defence_ids, witness_map):
    """Replace counsel teams and witness-player links. One student, one role."""
    roster_map = {}
    for row in roster or []:
        sid = str(getattr(row, 'student_id', '') or '').strip()
        if sid:
            roster_map[sid] = (getattr(row, 'name', None) or sid)[:100]

    def _clean(ids):
        seen = []
        for raw in ids or []:
            sid = str(raw or '').strip()
            if sid and sid in roster_map and sid not in seen:
                seen.append(sid)
        return seen

    prosec = _clean(prosecution_ids)
    defe = _clean(defence_ids)
    overlap = set(prosec) & set(defe)
    if overlap:
        raise ValueError('একই স্টুডেন্টকে প্রসিকিউশন ও ডিফেন্স দুই দলে রাখা যাবে না।')

    assigned_witness = {}
    used = set()
    for witness in case.witnesses or []:
        sid = str((witness_map or {}).get(witness.id) or '').strip()
        if not sid:
            assigned_witness[witness.id] = (None, None)
            continue
        if sid not in roster_map:
            continue
        if sid in used:
            raise ValueError('একজন স্টুডেন্টকে একাধিক সাক্ষী হিসেবে রাখা যাবে না।')
        used.add(sid)
        assigned_witness[witness.id] = (sid, roster_map[sid])

    prosec = [sid for sid in prosec if sid not in used]
    defe = [sid for sid in defe if sid not in used]

    ensure_side_teams(case)
    for team in case.teams:
        chosen = prosec if team.side == SIDE_PROSECUTION else defe if team.side == SIDE_DEFENCE else []
        team.members.clear()
        for sid in chosen:
            team.members.append(MockTrialTeamMember(
                student_id=sid[:50],
                student_name=roster_map.get(sid) or sid,
            ))

    for witness in case.witnesses or []:
        sid, name = assigned_witness.get(witness.id, (None, None))
        witness.assigned_student_id = sid
        witness.assigned_student_name = name
    return case


def apply_generated_pack(case, pack):
    """Replace factsheet, FIR, accused statement, witnesses, and exhibits from AI output."""
    pack = pack if isinstance(pack, dict) else {}
    title = (pack.get('title') or '').strip()
    if title:
        case.title = title[:300]
    if pack.get('factsheet'):
        case.set_factsheet(pack['factsheet'])
    if pack.get('fir'):
        case.set_fir(pack['fir'])
    if pack.get('accused_statement'):
        case.set_accused_statement(pack['accused_statement'])

    prior_cast = [
        {
            'role': item.role,
            'called_by': getattr(item, 'called_by', None) or SIDE_PROSECUTION,
            'sort_order': item.sort_order,
            'assigned_student_id': item.assigned_student_id,
            'assigned_student_name': item.assigned_student_name,
            'student_notes': item.student_notes,
            'unlock_min_score': getattr(item, 'unlock_min_score', None),
        }
        for item in (case.witnesses or [])
    ]
    case.witnesses.clear()
    for index, raw in enumerate(pack.get('witnesses') or []):
        if not isinstance(raw, dict):
            continue
        name = (raw.get('name') or '').strip()
        if not name:
            continue
        role = raw.get('role') if raw.get('role') in WITNESS_ROLE_LABELS else WITNESS_LAY
        official = role in OFFICIAL_PROSECUTION_ROLES
        default_need = 0 if official else int((case.quiz_pack() or {}).get('witness_unlock_score') or 60)
        try:
            min_score = 0 if official else int(raw.get('unlock_min_score') or default_need)
        except (TypeError, ValueError):
            min_score = default_need
        called_by = SIDE_PROSECUTION if official else (
            raw.get('called_by') if raw.get('called_by') in (SIDE_PROSECUTION, SIDE_DEFENCE) else SIDE_PROSECUTION
        )
        witness = MockTrialWitness(
            role=role,
            called_by=called_by,
            name=name[:120],
            designation=(raw.get('designation') or '')[:200] or None,
            is_unlocked=False,
            unlock_min_score=max(0, min(100, min_score)),
            sort_order=index,
        )
        witness.set_card(raw.get('instruction_card') or {})
        leftover = next(
            (
                item for item in prior_cast
                if item['role'] == role
                and item.get('called_by') == called_by
                and item.get('assigned_student_id')
            ),
            None,
        )
        if leftover is None:
            leftover = next(
                (item for item in prior_cast if item['sort_order'] == index and item.get('assigned_student_id')),
                None,
            )
        if leftover:
            witness.assigned_student_id = leftover['assigned_student_id']
            witness.assigned_student_name = leftover['assigned_student_name']
            witness.student_notes = leftover['student_notes']
            if not official and leftover.get('unlock_min_score') not in (None, ''):
                try:
                    witness.unlock_min_score = max(0, min(100, int(leftover['unlock_min_score'])))
                except (TypeError, ValueError):
                    pass
            prior_cast.remove(leftover)
        case.witnesses.append(witness)

    case.exhibits.clear()
    for index, raw in enumerate(pack.get('exhibits') or []):
        if not isinstance(raw, dict):
            continue
        title = (raw.get('title') or '').strip()
        if not title:
            continue
        try:
            min_score = int(raw.get('unlock_min_score') or 60)
        except (TypeError, ValueError):
            min_score = 60
        exhibit = MockTrialExhibit(
            exhibit_key=(raw.get('exhibit_key') or 'other')[:50],
            title=title[:200],
            summary=(raw.get('summary') or '').strip() or None,
            is_unlocked=False,
            unlock_min_score=max(0, min(100, min_score)),
            sort_order=index,
        )
        exhibit.set_body({'body': raw.get('body') or raw.get('summary') or ''})
        case.exhibits.append(exhibit)
    return case
