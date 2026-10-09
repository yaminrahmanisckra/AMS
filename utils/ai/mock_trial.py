"""Generate a Bangladesh criminal mock-trial case pack (factsheet + instruction cards)."""
import json
import re

from utils.ai.socrates import clip

INCOMPLETE_PACK_MESSAGE = 'এআই মামলার খসড়া অসম্পূর্ণ ছিল। আবার Generate চাপুন।'

_BN_DIGITS = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')

SKELETON_SYSTEM_PROMPT = (
    'You design a FICTIONAL Bangladesh classroom mock trial (Penal Code, CrPC 1898, Evidence Act 1872). '
    'This is teaching material, not a real crime. Follow the teacher brief exactly. '
    'Return a SHORT JSON skeleton only — no instruction-card text and no exhibit body. '
    'Create EXACTLY the requested number of prosecution witnesses and defence witnesses. '
    'The IO and expert are always prosecution witnesses. '
    'Mark each with called_by. List exhibit titles the teacher asked for plus seizure list, '
    'inquest/post-mortem, and case diary. Write Bangla if the brief is Bangla. JSON only.'
)

CARD_SYSTEM_PROMPT = (
    'You write hidden instruction cards for a fictional Bangladesh classroom mock trial. '
    'Fill ONLY the listed witnesses. Do not drop any name. '
    'Lay: direct_evidence, section_161, hidden_truth, hearsay, behaviour. '
    'IO: timeline, seizure, s161_summaries, procedural_flaws, behaviour. '
    'Expert: expertise, findings, margin_of_error, behaviour. '
    'Hidden facts stay off the FIR. JSON only: {"witnesses":[{name,instruction_card}]}.'
)

QUIZ_SYSTEM_PROMPT = (
    'You write multiple-choice questions for a fictional Bangladesh classroom mock trial '
    '(Penal Code, CrPC 1898, Evidence Act 1872). This is teaching material. '
    'Honor the teacher topic/law prompt exactly — if they name a section or subject, '
    'every question must be about those topics. '
    'Use only the public case papers plus the teacher prompt. '
    'Never use hidden witness instruction cards or locked exhibit bodies. '
    'Each item has exactly 4 distinct choices and one correct answer that matches a choice verbatim. '
    'Write Bangla if the teacher prompt is Bangla. JSON only.'
)

EXHIBIT_ONLY_SYSTEM_PROMPT = (
    'You write locked exhibits for a fictional Bangladesh classroom mock trial. '
    'Return JSON only: {"exhibits":[{exhibit_key,title,summary,body,unlock_min_score}]}. '
    'Create every named exhibit. Each body is a full classroom document (not a one-line stub). '
    'Match the case facts. Write Bangla if the brief is Bangla.'
)

BRIEF_CHAR_LIMIT = 12000
CARD_BATCH = 3

STANDARD_EXHIBITS = (
    {
        'exhibit_key': 'seizure_list',
        'title': 'Seizure list (CrPC s.103)',
        'summary': 'List of articles seized from the scene or from the accused.',
        'body': 'Seizure list prepared under CrPC s.103. Record the place, time, articles, and search witnesses.',
        'unlock_min_score': 55,
    },
    {
        'exhibit_key': 'postmortem',
        'title': 'Inquest / post-mortem report',
        'summary': 'Medical or inquest note on cause and time of injury or death.',
        'body': 'Inquest and medical findings for classroom use. Include injuries, probable weapon, and a time window.',
        'unlock_min_score': 60,
    },
    {
        'exhibit_key': 'case_diary',
        'title': 'Case diary extract',
        'summary': 'Short extract from the investigating officer’s case diary.',
        'body': 'Case diary extract: steps taken, persons examined, and exhibits sent to the lab.',
        'unlock_min_score': 65,
    },
    {
        'exhibit_key': 'forensic',
        'title': 'Forensic / lab note',
        'summary': 'Laboratory or forensic observation with a stated limitation.',
        'body': 'Forensic note for classroom use. State the finding and the margin of error or lab limitation.',
        'unlock_min_score': 70,
    },
)


def _string(value, limit=4000):
    return clip(str(value or '').strip(), limit)


def _string_list(value, limit=12):
    if isinstance(value, str):
        items = [part.strip() for part in value.replace('\n', ',').split(',')]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = []
    return [item for item in items if item][:limit]


def _dict(value):
    return value if isinstance(value, dict) else {}


def _int_or_none(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 1:
        return None
    return min(12, number)


def parse_teacher_pack_request(extra_brief, prosec_count=None, defence_count=None):
    """Read witness counts and named exhibits from the teacher brief / form."""
    prosec = _int_or_none(prosec_count)
    defence = _int_or_none(defence_count)
    raw = extra_brief or ''
    text = raw.translate(_BN_DIGITS)
    lowered = text.lower()

    def _search(patterns):
        for pattern in patterns:
            match = re.search(pattern, lowered, re.I | re.S)
            if match:
                return _int_or_none(match.group(1))
        return None

    if prosec is None:
        prosec = _search((
            r'(\d+)\s*(?:জন)?\s*(?:প্রসিকিউশন|prosecution)',
            r'(?:প্রসিকিউশন|prosecution)[^\d]{0,40}(\d+)',
        ))
    if defence is None:
        defence = _search((
            r'(\d+)\s*(?:জন)?\s*(?:ডিফেন্স|ডিফেন্সের|defence|defense)',
            r'(?:ডিফেন্স|defence|defense)[^\d]{0,40}(\d+)',
        ))

    named = []
    for match in re.finditer(
        r'(?:exhibit|exhibits|এক্সিবিট|প্রদর্শনী)\s*[:\-–]\s*([^\n]+)',
        raw,
        re.I,
    ):
        named.extend(_string_list(match.group(1), limit=16))

    specified = prosec is not None or defence is not None
    return {
        'prosecution_witnesses': prosec or 3,
        'defence_witnesses': defence or 2,
        'counts_specified': specified,
        'required_exhibits': named,
    }


def _normalize_called_by(value, fallback='prosecution'):
    text = str(value or '').strip().lower()
    if text in ('defence', 'defense', 'd', 'accused', 'ডিফেন্স', 'আসামি'):
        return 'defence'
    if text in ('prosecution', 'p', 'state', 'প্রসিকিউশন', 'রাষ্ট্র'):
        return 'prosecution'
    return fallback if fallback in ('prosecution', 'defence') else 'prosecution'


def _normalize_card(role, raw):
    card = _dict(raw)
    if role == 'io':
        keys = ('timeline', 'seizure', 's161_summaries', 'procedural_flaws', 'behaviour')
    elif role == 'expert':
        keys = ('expertise', 'findings', 'margin_of_error', 'behaviour')
    else:
        keys = ('direct_evidence', 'section_161', 'hidden_truth', 'hearsay', 'behaviour')
    return {key: _string(card.get(key), 2500) for key in keys}


def _collect_exhibit_rows(data):
    rows = data.get('exhibits') or data.get('locked_exhibits') or data.get('documents') or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    return rows if isinstance(rows, list) else []


def _normalize_exhibits(rows, required_titles=None):
    exhibits = []
    seen = set()
    for raw in rows or []:
        item = _dict(raw)
        exhibit_title = _string(
            item.get('title') or item.get('name') or item.get('exhibit_title'),
            200,
        )
        if not exhibit_title:
            continue
        key = exhibit_title.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            min_score = int(item.get('unlock_min_score') or 60)
        except (TypeError, ValueError):
            min_score = 60
        exhibits.append({
            'exhibit_key': _string(item.get('exhibit_key') or item.get('key') or 'other', 50),
            'title': exhibit_title,
            'summary': _string(item.get('summary') or item.get('description'), 2000),
            'body': _string(item.get('body') or item.get('text') or item.get('summary'), 4000),
            'unlock_min_score': max(0, min(100, min_score)),
        })
    for title in required_titles or []:
        if title.lower() not in seen:
            exhibits.append({
                'exhibit_key': 'other',
                'title': title[:200],
                'summary': title,
                'body': title,
                'unlock_min_score': 60,
            })
            seen.add(title.lower())
    return exhibits


def default_exhibits(required_titles=None, incident_summary=''):
    """Classroom fallback so a pack never ships without exhibits."""
    extras = _normalize_exhibits([], required_titles=required_titles)
    summary = (incident_summary or '').strip()
    built = []
    for spec in STANDARD_EXHIBITS:
        item = dict(spec)
        if summary:
            item['body'] = f"{item['body']}\n\nCase context: {clip(summary, 800)}"
        built.append(item)
    titles = {item['title'].lower() for item in built}
    for extra in extras:
        if extra['title'].lower() not in titles:
            built.append(extra)
    return built


def normalize_case_pack(payload, *, fallback_title, case_type, requirements=None):
    """Normalize AI JSON into a pack that apply_generated_pack() can store."""
    data = payload if isinstance(payload, dict) else {}
    factsheet = _dict(data.get('factsheet'))
    fir = _dict(data.get('fir'))
    accused = _dict(data.get('accused_statement'))
    title = _string(data.get('title') or factsheet.get('title') or fallback_title, 300)
    if not title:
        title = fallback_title

    legal = _string_list(factsheet.get('legal_provisions'))
    facts = _string_list(factsheet.get('facts'), limit=16)
    requirements = requirements or {}
    want_prosec = _int_or_none(requirements.get('prosecution_witnesses'))
    want_defence = _int_or_none(requirements.get('defence_witnesses'))

    witnesses = []
    role_counts = {'lay': 0, 'io': 0, 'expert': 0}
    side_counts = {'prosecution': 0, 'defence': 0}
    for raw in data.get('witnesses') or []:
        item = _dict(raw)
        name = _string(item.get('name'), 120)
        if not name:
            continue
        role = item.get('role') if item.get('role') in ('lay', 'io', 'expert') else 'lay'
        if role != 'lay' and role_counts[role] >= 1:
            role = 'lay'
        called_by = 'prosecution' if role in ('io', 'expert') else _normalize_called_by(
            item.get('called_by') or item.get('side') or item.get('called_for'),
            fallback='prosecution',
        )
        role_counts[role] = role_counts.get(role, 0) + 1
        side_counts[called_by] = side_counts.get(called_by, 0) + 1
        witnesses.append({
            'role': role,
            'called_by': called_by,
            'name': name,
            'designation': _string(item.get('designation'), 200),
            'instruction_card': _normalize_card(role, item.get('instruction_card')),
        })

    honor_counts = bool(requirements.get('counts_specified') or want_prosec or want_defence)
    if not honor_counts:
        if role_counts.get('io', 0) == 0:
            witnesses.append({
                'role': 'io',
                'called_by': 'prosecution',
                'name': 'Investigating Officer',
                'designation': 'Officer-in-Charge / IO',
                'instruction_card': _normalize_card('io', {}),
            })
        if role_counts.get('expert', 0) == 0:
            witnesses.append({
                'role': 'expert',
                'called_by': 'prosecution',
                'name': 'Expert Witness',
                'designation': 'Medical / Forensic expert',
                'instruction_card': _normalize_card('expert', {}),
            })

    exhibits = _normalize_exhibits(
        _collect_exhibit_rows(data),
        required_titles=requirements.get('required_exhibits'),
    )

    has_substance = bool(
        _string(factsheet.get('incident_summary'))
        or _string(fir.get('narrative'))
        or any(_normalize_card(w['role'], w['instruction_card']).values() for w in witnesses)
    )
    if not has_substance:
        raise ValueError(INCOMPLETE_PACK_MESSAGE)

    return {
        'title': title,
        'factsheet': {
            'title': title,
            'case_type': case_type,
            'incident_summary': _string(factsheet.get('incident_summary'), 4000),
            'date_time': _string(factsheet.get('date_time'), 200),
            'place': _string(factsheet.get('place'), 300),
            'legal_provisions': legal,
            'facts': facts,
            'accused': factsheet.get('accused') if isinstance(factsheet.get('accused'), list) else [],
            'victim': _dict(factsheet.get('victim')),
        },
        'fir': {
            'police_station': _string(fir.get('police_station'), 120),
            'gd_entry': _string(fir.get('gd_entry'), 80),
            'narrative': _string(fir.get('narrative'), 4000),
        },
        'accused_statement': {
            'narrative': _string(accused.get('narrative'), 4000),
        },
        'witnesses': witnesses,
        'exhibits': exhibits,
    }


def _teacher_brief(extra_brief):
    """Keep the teacher's prompt intact; only cap extreme paste size."""
    return (extra_brief or '').strip()[:BRIEF_CHAR_LIMIT]


def _ai_json(system_prompt, user_prompt, max_tokens=2500, max_retries=0):
    from utils.ai.client import generate_outline_json_with_meta
    from utils.ai.outline_parser import extract_json_from_response
    from utils.ai.session_utils import reset_db_session

    meta = generate_outline_json_with_meta(
        system_prompt,
        user_prompt,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )
    reset_db_session()
    return extract_json_from_response(meta.get('text') or ''), meta


def ensure_witness_roster(witnesses, prosec_n, defence_n):
    """Pad / trim so each side has the requested number of witnesses."""
    prosec_n = _int_or_none(prosec_n) or 3
    defence_n = _int_or_none(defence_n) or 2
    prosec = [w for w in (witnesses or []) if w.get('called_by') == 'prosecution']
    defence = [w for w in (witnesses or []) if w.get('called_by') == 'defence']

    def _pad(rows, side, wanted, label):
        out = list(rows[:wanted])
        while len(out) < wanted:
            index = len(out) + 1
            role = 'io' if side == 'prosecution' and index == wanted and not any(r.get('role') == 'io' for r in out) else 'lay'
            out.append({
                'role': role,
                'called_by': side,
                'name': f'{label} {index}',
                'designation': 'Investigating Officer' if role == 'io' else '',
                'instruction_card': _normalize_card(role, {}),
            })
        return out

    return _pad(prosec, 'prosecution', prosec_n, 'Prosecution witness') + _pad(
        defence, 'defence', defence_n, 'Defence witness',
    )


def _card_is_thin(witness):
    card = _normalize_card(witness.get('role') or 'lay', witness.get('instruction_card'))
    return not any((value or '').strip() for value in card.values())


def _merge_cards(roster, generated_rows):
    by_name = {}
    for raw in generated_rows or []:
        item = _dict(raw)
        name = _string(item.get('name'), 120)
        if name:
            by_name[name.lower()] = item.get('instruction_card')
    leftover = [item for item in (generated_rows or []) if _dict(item).get('instruction_card')]
    for witness in roster:
        card = by_name.get((witness.get('name') or '').lower())
        if card is None and leftover:
            card = leftover.pop(0).get('instruction_card')
        if card:
            witness['instruction_card'] = _normalize_card(witness.get('role') or 'lay', card)
    return roster


def _exhibit_is_thin(item):
    body = (item.get('body') or '').strip()
    title = (item.get('title') or '').strip()
    return len(body) < 60 or body == title


def generate_case_pack(
    *,
    case_type,
    case_type_label,
    title,
    extra_brief,
    course_label,
    prosec_count=None,
    defence_count=None,
):
    """Build the pack in short passes so the teacher brief and cards are not truncated."""
    from utils.ai.session_utils import reset_db_session

    brief = _teacher_brief(extra_brief)
    requirements = parse_teacher_pack_request(brief, prosec_count, defence_count)
    required_exhibits = list(requirements['required_exhibits'])
    for spec in STANDARD_EXHIBITS[:3]:
        if spec['title'] not in required_exhibits:
            required_exhibits.append(spec['title'])
    requirements = dict(requirements)
    requirements['required_exhibits'] = required_exhibits
    prosec_n = requirements['prosecution_witnesses']
    defence_n = requirements['defence_witnesses']

    skeleton_user = (
        'TEACHER BRIEF (authoritative — do not omit anything):\n'
        f'{brief or "(none)"}\n\n'
        f'Course: {course_label or ""}\n'
        f'Case type: {case_type_label or case_type}\n'
        f'Working title: {title or ""}\n'
        f'Create EXACTLY {prosec_n} prosecution witnesses and EXACTLY {defence_n} defence witnesses.\n'
        f'Required exhibit titles: {json.dumps(required_exhibits, ensure_ascii=False)}\n\n'
        'Return JSON: {"title":"","factsheet":{"incident_summary":"","date_time":"","place":"",'
        '"legal_provisions":[],"facts":[],"accused":[{"name":"","age":"","role":""}],'
        '"victim":{"name":"","age":""}},"fir":{"police_station":"","gd_entry":"","narrative":""},'
        '"accused_statement":{"narrative":""},'
        '"witnesses":[{"name":"","role":"lay|io|expert","called_by":"prosecution|defence","designation":""}],'
        '"exhibits":[{"exhibit_key":"","title":""}]}\n'
        'The IO and expert are always prosecution witnesses (called_by=prosecution).'
    )
    last_exc = None
    pack = None
    meta = None
    for attempt in range(2):
        try:
            payload, meta = _ai_json(
                SKELETON_SYSTEM_PROMPT, skeleton_user, max_tokens=3500, max_retries=1,
            )
            pack = normalize_case_pack(
                payload,
                fallback_title=title or case_type_label,
                case_type=case_type,
                requirements=requirements,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            last_exc = ValueError(INCOMPLETE_PACK_MESSAGE)
            last_exc.__cause__ = exc
            reset_db_session()
            if attempt == 0:
                continue
            raise last_exc from exc
        break
    if pack is None:
        raise last_exc or ValueError(INCOMPLETE_PACK_MESSAGE)

    pack['witnesses'] = ensure_witness_roster(pack.get('witnesses') or [], prosec_n, defence_n)
    factsheet = pack.get('factsheet') or {}
    case_context = (
        f'Title: {pack.get("title")}\n'
        f'Summary: {factsheet.get("incident_summary") or ""}\n'
        f'FIR: {(pack.get("fir") or {}).get("narrative") or ""}\n'
        f'Accused: {(pack.get("accused_statement") or {}).get("narrative") or ""}\n'
    )

    thin = [w for w in pack['witnesses'] if _card_is_thin(w)]
    for start in range(0, len(thin), CARD_BATCH):
        batch = thin[start:start + CARD_BATCH]
        names = [
            {
                'name': w.get('name'),
                'role': w.get('role'),
                'called_by': w.get('called_by'),
                'designation': w.get('designation'),
            }
            for w in batch
        ]
        card_user = (
            'TEACHER BRIEF:\n'
            f'{brief or "(none)"}\n\n'
            f'CASE:\n{case_context}\n'
            f'Fill instruction cards for ALL of these witnesses ({len(names)}):\n'
            f'{json.dumps(names, ensure_ascii=False)}\n'
        )
        try:
            payload, _meta = _ai_json(CARD_SYSTEM_PROMPT, card_user, max_tokens=4000, max_retries=0)
            pack['witnesses'] = _merge_cards(pack['witnesses'], payload.get('witnesses') or [])
        except Exception:
            reset_db_session()

    exhibit_user = (
        'TEACHER BRIEF:\n'
        f'{brief or "(none)"}\n\n'
        f'CASE:\n{case_context}\n'
        f'Write FULL bodies for these exhibits:\n'
        f'{json.dumps(required_exhibits, ensure_ascii=False)}\n'
        'Also include any extra exhibit the brief named.'
    )
    try:
        payload, _meta = _ai_json(
            EXHIBIT_ONLY_SYSTEM_PROMPT, exhibit_user, max_tokens=4000, max_retries=0,
        )
        generated = _normalize_exhibits(
            _collect_exhibit_rows(payload),
            required_titles=required_exhibits,
        )
        if generated:
            pack['exhibits'] = generated
    except Exception:
        reset_db_session()

    if not pack.get('exhibits') or sum(1 for item in pack['exhibits'] if not _exhibit_is_thin(item)) < 2:
        extras = default_exhibits(
            required_titles=required_exhibits,
            incident_summary=factsheet.get('incident_summary') or '',
        )
        have = {item['title'].lower() for item in (pack.get('exhibits') or [])}
        merged = list(pack.get('exhibits') or [])
        for item in extras:
            if item['title'].lower() not in have:
                merged.append(item)
        pack['exhibits'] = merged

    if meta:
        pack['provider'] = meta.get('provider')
        pack['model_name'] = meta.get('model_name')
    return pack


def generate_quiz_questions(
    *,
    brief,
    count=5,
    side='both',
    title='',
    case_type_label='',
    course_label='',
    factsheet=None,
    fir=None,
    accused=None,
):
    """Teacher-directed MCQs. Hidden cards and exhibit bodies are never sent."""
    from utils.ai.session_utils import reset_db_session

    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(20, count))
    side = (side or 'both').strip().lower()
    if side in ('defense',):
        side = 'defence'
    if side not in ('both', 'prosecution', 'defence'):
        side = 'both'
    factsheet = factsheet if isinstance(factsheet, dict) else {}
    fir = fir if isinstance(fir, dict) else {}
    accused = accused if isinstance(accused, dict) else {}
    context = {
        'title': title or '',
        'case_type': case_type_label or '',
        'course': course_label or '',
        'place': factsheet.get('place') or '',
        'date_time': factsheet.get('date_time') or '',
        'incident_summary': (factsheet.get('incident_summary') or '')[:800],
        'legal_provisions': factsheet.get('legal_provisions') or [],
        'fir_police_station': fir.get('police_station') or '',
        'fir_narrative': (fir.get('narrative') or '')[:800],
        'accused_narrative': (accused.get('narrative') or '')[:800],
    }
    user = (
        'TEACHER TOPIC / LAW PROMPT (authoritative — do not omit these subjects):\n'
        f'{_teacher_brief(brief) or "(none — use the public papers and named provisions)"}\n\n'
        f'Create EXACTLY {count} MCQs. Set each question side to "{side}".\n'
        'If the prompt names statutes or doctrines, the questions must test those — not generic trivia.\n'
        'Do not invent hidden witness facts or locked exhibit text.\n\n'
        f'Public case context:\n{json.dumps(context, ensure_ascii=False)}\n\n'
        'Return JSON: {"questions":[{"prompt":"","choices":["","","",""],"answer":"","side":"'
        f'{side}'
        '"}]}'
    )
    try:
        payload, _meta = _ai_json(QUIZ_SYSTEM_PROMPT, user, max_tokens=3500, max_retries=1)
    except Exception:
        reset_db_session()
        raise
    rows = payload.get('questions') if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError('এআই কোনো কুইজ প্রশ্ন তৈরি করেনি। প্রম্পট বদলে আবার চেষ্টা করুন।')
    questions = []
    for index, raw in enumerate(rows[:count], start=1):
        item = raw if isinstance(raw, dict) else {}
        item['side'] = item.get('side') or side
        questions.append(item)
    if not questions:
        raise ValueError('এআই কোনো কুইজ প্রশ্ন তৈরি করেনি। প্রম্পট বদলে আবার চেষ্টা করুন।')
    return questions[:count]
