"""Question Bank paper analysis and guideline-based model answers."""
import json
import re

from extensions import db
from utils.ai.client import generate_outline_json_with_meta
from utils.ai.document_extractor import extract_text_from_file
from utils.ai.outline_parser import extract_json_from_response


def clip(text, limit=12000):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit] + '\n…[truncated]'


def infer_course_code(*values):
    for value in values:
        if not value:
            continue
        match = re.search(r'([A-Za-z]{2,8})\s*[-]?\s*(\d{4})', str(value))
        if match:
            return f'{match.group(1).upper()} {match.group(2)}'
    return None


def _reload(model, record_id):
    if not record_id:
        return None
    try:
        db.session.rollback()
    except Exception:
        pass
    return model.query.get(record_id)


def ensure_extracted(obj, refresh=False):
    """Read text from disk/OCR without leaving a detached ORM instance behind."""
    model = type(obj)
    record_id = getattr(obj, 'id', None)
    obj = _reload(model, record_id) or obj
    existing = (getattr(obj, 'extracted_text', None) or '').strip()
    path = getattr(obj, 'file_path', None) or ''
    if existing and not refresh:
        return existing
    ext = 'pdf'
    lower = path.lower()
    if lower.endswith(('.doc', '.docx')):
        ext = 'docx'
    elif lower.endswith(('.txt', '.md')):
        ext = 'txt'
    text = extract_text_from_file(path, ext)
    obj = _reload(model, record_id) or obj
    try:
        obj.extracted_text = text or None
        if record_id:
            db.session.commit()
    except Exception:
        db.session.rollback()
        obj = _reload(model, record_id) or obj
        if obj is not None:
            obj.extracted_text = text or None
    return text or ''


def find_matching_course(qb_file):
    from blueprints.course_management.models import Course

    code = (qb_file.course_code or infer_course_code(qb_file.title, qb_file.subject_name) or '').strip()
    if not code:
        return None, ''
    compact = re.sub(r'[\s\-]+', '', code).upper()
    courses = Course.query.all()
    for course in courses:
        course_compact = re.sub(r'[\s\-]+', '', course.course_code or '').upper()
        if course_compact == compact:
            return course, course.course_code
    return None, code


def _clos_from_course(course):
    if not course:
        return []
    try:
        rows = course.get_clos_list() or []
    except Exception:
        rows = []
    out = []
    for idx, row in enumerate(rows, start=1):
        if isinstance(row, dict):
            text = (row.get('text') or row.get('description') or '').strip()
            plo = row.get('plo') or ''
        else:
            text = str(row).strip()
            plo = ''
        if text:
            out.append({'number': idx, 'text': text, 'plo': plo})
    return out


def _parse_json_dict(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_questions(raw):
    out = []
    for i, item in enumerate(raw or []):
        if isinstance(item, str):
            text = item.strip()
            number = f'Q{i + 1}'
        elif isinstance(item, dict):
            text = str(item.get('text') or item.get('question') or '').strip()
            number = str(item.get('number') or f'Q{i + 1}').strip() or f'Q{i + 1}'
        else:
            continue
        if not text:
            continue
        out.append({
            'index': len(out),
            'number': number,
            'text': text,
            'marks': (item.get('marks') if isinstance(item, dict) else '') or '',
        })
    return out


def analyze_question_paper(qb_file):
    qb_id = qb_file.id
    paper_text = ensure_extracted(qb_file)
    from blueprints.class_management.models import QuestionBankFile
    qb_file = _reload(QuestionBankFile, qb_id) or qb_file
    if not paper_text:
        raise ValueError(
            'এই PDF থেকে টেক্সট পড়া যায়নি। স্ক্যান হলে Analyze আবার চাপুন '
            '(এআই পাতার ছবি পড়ে টেক্সট তুলবে)। Gemini বা OpenAI লাগবে।'
        )

    course, matched_code = find_matching_course(qb_file)
    if matched_code and not qb_file.course_code:
        qb_file.course_code = matched_code
        db.session.commit()
    clos = _clos_from_course(course)
    course_code = qb_file.course_code or matched_code
    folder = qb_file.subject_name
    year = qb_file.question_year
    title = qb_file.title

    system_prompt = (
        'You analyse university exam question papers against Course Learning Outcomes (CLOs). '
        'Return JSON only. Do not invent statutes, cases, or syllabus topics that are not in the paper or CLOs. '
        'If a CLO list is empty, say coverage is unknown rather than guessing curriculum. '
        'Split "answer any two of the following" groups into separate sub-questions (e.g. Q2(a), Q2(b)).'
    )
    user_prompt = json.dumps({
        'task': 'analyse_question_paper',
        'course_code': course_code,
        'folder': folder,
        'year': year,
        'title': title,
        'clos': clos,
        'paper_text': clip(paper_text),
        'output_schema': {
            'questions': [{'number': 'Q1', 'text': '', 'marks': '', 'bloom': 'Remember|Understand|Apply|Analyze|Evaluate|Create', 'clos': ['CLO1']}],
            'bloom_summary': {},
            'clo_coverage': [{'clo': 'CLO1', 'covered': True, 'notes': ''}],
            'missing_topics': [],
            'notes': '',
        },
    }, ensure_ascii=False)

    meta = generate_outline_json_with_meta(system_prompt, user_prompt, max_tokens=3500)
    payload = extract_json_from_response(meta.get('text') or '')
    if not isinstance(payload, dict):
        payload = {'raw': payload}
    qb_file = _reload(QuestionBankFile, qb_id)
    if qb_file:
        if matched_code and not qb_file.course_code:
            qb_file.course_code = matched_code
        qb_file.analysis_json = json.dumps(payload, ensure_ascii=False)
        db.session.commit()
    return payload


def find_active_guideline():
    from blueprints.class_management.models import AnswerGuideline

    return (
        AnswerGuideline.query.filter_by(is_active=True)
        .order_by(AnswerGuideline.created_at.desc())
        .first()
    )


def get_active_guideline_text_cached():
    """Return (id, title, text) from DB only — never OCR/extract on this request."""
    row = find_active_guideline()
    if not row:
        return None, None, None
    text = (row.extracted_text or '').strip()
    return row.id, row.title, text or None


def find_guideline_in_folder(qb_file=None):
    """Back-compat name: guidelines now live in Admin → Answer Guideline."""
    return find_active_guideline()


def _guideline_text_and_title():
    from blueprints.class_management.models import AnswerGuideline

    row = find_active_guideline()
    if not row:
        return None, None, None
    gid = row.id
    title = row.title
    text = ensure_extracted(row)
    row = _reload(AnswerGuideline, gid)
    if row:
        title = row.title
    return gid, title, text


def _ai_list_questions(paper_text, title, year):
    system_prompt = (
        'You split a university exam paper into individual questions. '
        'Each sub-part (a), (b), (c) is a separate item. '
        'Keep original numbering. Return JSON only.'
    )
    user_prompt = json.dumps({
        'task': 'list_exam_questions',
        'title': title,
        'year': year,
        'paper_text': clip(paper_text),
        'output_schema': {
            'questions': [{'number': 'Q1 / 1(a)', 'text': 'full question text', 'marks': ''}],
        },
    }, ensure_ascii=False)
    meta = generate_outline_json_with_meta(system_prompt, user_prompt, max_tokens=2500)
    payload = extract_json_from_response(meta.get('text') or '')
    if not isinstance(payload, dict):
        return []
    return _normalize_questions(payload.get('questions'))


def list_paper_questions(qb_file):
    """Questions already analysed, or freshly listed from the PDF text."""
    from blueprints.class_management.models import QuestionBankFile

    qb_id = qb_file.id
    analysis = _parse_json_dict(qb_file.analysis_json)
    questions = _normalize_questions(analysis.get('questions'))
    if questions:
        return questions

    paper_text = ensure_extracted(qb_file)
    qb_file = _reload(QuestionBankFile, qb_id) or qb_file
    title = qb_file.title
    year = qb_file.question_year
    if not paper_text:
        raise ValueError(
            'এই PDF থেকে টেক্সট পড়া যায়নি। স্ক্যান হলে আগে Analyze চাপুন, অথবা Gemini/OpenAI চালু আছে কিনা দেখুন।'
        )
    questions = _ai_list_questions(paper_text, title, year)
    if not questions:
        raise ValueError('প্রশ্ন আলাদা করা যায়নি। Analyze চাপুন, তারপর আবার চেষ্টা করুন।')
    qb_file = _reload(QuestionBankFile, qb_id)
    if qb_file:
        analysis = _parse_json_dict(qb_file.analysis_json)
        analysis['questions'] = questions
        qb_file.analysis_json = json.dumps(analysis, ensure_ascii=False)
        db.session.commit()
    return questions


def _answer_key(item):
    number = str(item.get('number') or '').strip()
    if number:
        return number
    return str(item.get('question') or '').strip()[:80]


def _merge_answers(existing, new_rows):
    existing = existing if isinstance(existing, dict) else {}
    answers = list(existing.get('answers') or [])
    by_key = {}
    for item in answers:
        if isinstance(item, dict) and _answer_key(item):
            by_key[_answer_key(item)] = item
    for item in new_rows:
        if isinstance(item, dict) and _answer_key(item):
            by_key[_answer_key(item)] = item
    existing['answers'] = list(by_key.values())
    return existing


def _find_stored_answer(answers, question):
    number = str((question or {}).get('number') or '').strip()
    if not number:
        return None
    for item in answers or []:
        if isinstance(item, dict) and str(item.get('number') or '').strip() == number:
            if (item.get('model_answer') or '').strip():
                return item
    return None


def stored_model_answers(qb_file):
    return _parse_json_dict(getattr(qb_file, 'model_answers_json', None))


def generate_model_answers(qb_file, guideline_file=None, selected_questions=None, regenerate=False):
    """Write model answers for the chosen questions only. Reuses saved answers unless regenerate."""
    from blueprints.class_management.models import QuestionBankFile

    qb_id = qb_file.id
    selected = _normalize_questions(selected_questions)
    if not selected:
        raise ValueError('কমপক্ষে একটি প্রশ্ন বেছে নিন।')

    qb_file = _reload(QuestionBankFile, qb_id) or qb_file
    existing = _parse_json_dict(qb_file.model_answers_json)
    stored_rows = existing.get('answers') or []
    to_generate = []
    cached = []
    if regenerate:
        to_generate = selected
    else:
        for question in selected:
            found = _find_stored_answer(stored_rows, question)
            if found:
                cached.append(found)
            else:
                to_generate.append(question)
        if not to_generate:
            payload = dict(existing)
            payload['generated'] = cached
            payload['from_cache'] = True
            payload.setdefault('guideline_title', existing.get('guideline_title') or '')
            return payload

    paper_text = ensure_extracted(qb_file)
    qb_file = _reload(QuestionBankFile, qb_id) or qb_file
    course_code = qb_file.course_code
    year = qb_file.question_year
    title = qb_file.title
    existing = _parse_json_dict(qb_file.model_answers_json)

    if not paper_text:
        raise ValueError('প্রশ্নপত্র থেকে টেক্সট পড়া যায়নি। স্ক্যান হলে আগে Analyze চাপুন।')

    gid, guideline_title, guideline_text = _guideline_text_and_title()
    if not guideline_title:
        raise ValueError(
            'Answer Guideline নেই। Admin Dashboard → Answer Guideline থেকে একটি PDF আপলোড করুন।'
        )
    if not guideline_text:
        raise ValueError('Answer Guideline থেকে টেক্সট পড়া যায়নি। Admin প্যানেলে ফাইলটি আবার তুলুন।')

    system_prompt = (
        'You write model answers for the SELECTED university exam questions only. '
        'Use ONLY the provided Answer Guideline. Identify which named answer model / structure '
        'in the guideline you followed (e.g. problem question, short note, analytical, IRAC). '
        'Do not invent cases, statutes, or marking points that are not in the guideline. '
        'If the guideline is silent, say so. Return JSON only. '
        'Write model_answer as GitHub-flavoured Markdown: ## headings, numbered lists, '
        'bullets, markdown tables, blockquotes for citations, and a Figure/চিত্র caption line '
        'where a diagram is needed. No HTML tags.'
    )
    user_prompt = json.dumps({
        'task': 'model_answers_from_guideline',
        'course_code': course_code,
        'year': year,
        'title': title,
        'guideline_title': guideline_title,
        'selected_questions': to_generate,
        'paper_context': clip(paper_text, 6000),
        'guideline_text': clip(guideline_text, 16000),
        'output_schema': {
            'answers': [{
                'number': 'Q1',
                'question': '',
                'followed_model': 'Name of the guideline answer model that was followed',
                'model_answer': 'Markdown: headings, lists, tables, citations',
                'marking_points': [],
                'citations': [],
                'source': 'guideline',
            }],
            'warnings': [],
        },
    }, ensure_ascii=False)

    meta = generate_outline_json_with_meta(system_prompt, user_prompt, max_tokens=6000)
    payload = extract_json_from_response(meta.get('text') or '')
    if not isinstance(payload, dict):
        payload = {'raw': payload, 'answers': []}
    new_rows = payload.get('answers') or []
    if not isinstance(new_rows, list):
        new_rows = []
    selected_by_number = {str(src.get('number') or ''): src for src in to_generate}
    generated = []
    for idx, row in enumerate(new_rows):
        if not isinstance(row, dict):
            continue
        src = selected_by_number.get(str(row.get('number') or ''))
        if src is None and idx < len(to_generate):
            src = to_generate[idx]
        if src:
            row.setdefault('number', src.get('number'))
            row.setdefault('question', src.get('text') or src.get('number'))
        row['guideline_title'] = guideline_title
        generated.append(row)

    qb_file = _reload(QuestionBankFile, qb_id)
    if qb_file:
        existing = _parse_json_dict(qb_file.model_answers_json)
        merged = _merge_answers(existing, generated)
        if payload.get('warnings'):
            merged['warnings'] = payload.get('warnings')
        merged['guideline_title'] = guideline_title
        merged['guideline_id'] = gid
        qb_file.model_answers_json = json.dumps(merged, ensure_ascii=False)
        db.session.commit()
        payload = merged
    payload['generated'] = generated
    payload['from_cache'] = False
    payload['guideline_title'] = guideline_title
    payload['guideline_id'] = gid
    return payload
