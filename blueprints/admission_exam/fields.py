"""Per-cycle application / admit-card field schema.

Stored as JSON on AdmissionCycle.field_schema. Custom (extra) values live in
AdmissionCandidate.extra_fields; core values use candidate columns.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy

# Keys that map to AdmissionCandidate columns (not extra_fields JSON).
CORE_KEYS = frozenset({
    'full_name', 'phone', 'email', 'photo', 'candidate_signature',
    'payment_method',
    'rocket_txn_id', 'rocket_sender_phone',
    'bank_slip_txn_no', 'bank_slip',
})

SYSTEM_KEYS = frozenset({
    'application_id', 'roll_no', 'payment_status',
})

RESERVED_KEYS = CORE_KEYS | SYSTEM_KEYS | frozenset({
    'pin', 'password', 'csrf_token', 'cycle_id', 'id',
})

PAYMENT_METHOD_LABELS = {
    'agrani_bank': 'Agrani Bank',
    'bkash': 'bKash',
    'nagad': 'Nagad',
    'rocket': 'Rocket',
}

MFS_PAYMENT_METHODS = frozenset({'bkash', 'nagad', 'rocket'})
BANK_PAYMENT_METHODS = frozenset({'agrani_bank'})
ALL_PAYMENT_METHODS = frozenset(PAYMENT_METHOD_LABELS)
DEFAULT_PAYMENT_METHOD = 'agrani_bank'
PAYMENT_METHOD_ORDER = ('agrani_bank', 'bkash', 'nagad', 'rocket')

PAYMENT_FIELD_KEYS = frozenset({
    'payment_method', 'rocket_txn_id', 'rocket_sender_phone',
    'bank_slip_txn_no', 'bank_slip',
})

FILE_FIELD_KEYS = frozenset({'photo', 'bank_slip', 'candidate_signature'})

_LAW_ACADEMIC_EXAM_ROWS = (
    ('ssc', 'S.S.C. / Equivalent'),
    ('hsc', 'H.S.C. / Equivalent'),
    ('llb', 'LL.B. (Hons.)'),
    ('other', 'Others'),
)
ACADEMIC_COL_SUFFIXES = (
    ('year', 'Year of Passing'),
    ('board', 'Board / University'),
    ('institution', 'Name of the Institution'),
    ('cgpa', 'CGPA / Total Marks'),
    ('percentage', 'Percentage of Marks'),
)


def academic_exam_rows():
    try:
        from utils.tenant import current_tenant
        rows = current_tenant().academic_exam_rows
        if rows:
            return rows
    except Exception:
        pass
    return _LAW_ACADEMIC_EXAM_ROWS


class _LazyRows:
    def __iter__(self):
        return iter(academic_exam_rows())

    def __len__(self):
        return len(academic_exam_rows())


ACADEMIC_EXAM_ROWS = _LazyRows()


def academic_field_keys():
    keys = []
    for prefix, _label in academic_exam_rows():
        if prefix == 'other':
            keys.append('other_exam_name')
        for suffix, _col in ACADEMIC_COL_SUFFIXES:
            keys.append(f'{prefix}_{suffix}')
    return keys


class _LazyFrozenSet:
    def __init__(self, factory):
        self._factory = factory

    def __contains__(self, item):
        return item in self._factory()

    def __iter__(self):
        return iter(self._factory())


ACADEMIC_FIELD_KEYS = _LazyFrozenSet(lambda: frozenset(academic_field_keys()))

ACADEMIC_EXTRA_ROWS_KEY = 'academic_extra_rows'

DEFAULT_DOCUMENT_TAGS = (
    'SSC Certificate',
    'SSC Transcript / Marksheet',
    'HSC Certificate',
    'HSC Transcript / Marksheet',
    'LL.B. Certificate',
    'LL.B. Transcript / Marksheet',
    'Other Certificate / Transcript',
)

DOCUMENT_STATUSES = ('pending', 'verified', 'rejected')
DOCUMENT_ALLOWED_EXTS = frozenset({'png', 'jpg', 'jpeg'})
DOCUMENT_MAX_BYTES = 5 * 1024 * 1024
DOCUMENT_MAX_LABEL = '5 MB'

DEFAULT_DECLARATION_TEXT = (
    'The information provided in this Application Form is true and correct. '
    'I accept that Khulna University reserves the right to cancel my admission at any time, '
    'if any of the aforementioned information is found to be false or incorrect.\n'
    'I promise that if I get myself admitted in Khulna University:\n'
    'a) I will abide by all rules and regulations of the University.\n'
    'b) I will comply with the decisions of the University or any person authorized by the University.\n'
    'c) I will arrange my own boarding when the University cannot provide me with accommodation.'
)


def default_declaration_text():
    return DEFAULT_DECLARATION_TEXT


def get_declaration_text(cycle):
    raw = getattr(cycle, 'declaration_text', None) if cycle is not None else None
    text = (raw or '').strip()
    return text if text else DEFAULT_DECLARATION_TEXT


def serialize_declaration_text(text):
    text = (text or '').strip()
    return text if text else None


def is_mfs_payment_method(method):
    return (method or '').strip().lower() in MFS_PAYMENT_METHODS


def mfs_field_labels(method):
    label = PAYMENT_METHOD_LABELS.get((method or '').strip().lower(), 'Mobile')
    return {
        'txn': f'{label} Transaction ID',
        'sender': f'Sender {label} Account Number',
    }


def _f(key, label, source='extra', section='personal', field_type='text',
       required=False, on_form=True, on_admit=False, on_app_pdf=True, locked=False):
    return {
        'key': key, 'label': label, 'source': source, 'section': section,
        'field_type': field_type, 'required': required,
        'on_form': on_form, 'on_admit': on_admit, 'on_app_pdf': on_app_pdf,
        'locked': locked,
    }


def _academic_default_fields():
    fields = []
    for prefix, exam_label in academic_exam_rows():
        if prefix == 'other':
            fields.append(_f(
                'other_exam_name', 'Others – Name of the Examination',
                section='academic', required=False,
            ))
        for suffix, col_label in ACADEMIC_COL_SUFFIXES:
            fields.append(_f(
                f'{prefix}_{suffix}',
                f'{exam_label} – {col_label}',
                section='academic', required=False,
            ))
    return fields


_DEFAULT_FIELD_SCHEMA_HEAD = [
    _f('application_id', 'Form / Application ID', source='system', section='identity',
       on_form=False, on_admit=True, locked=True),
    _f('roll_no', 'Roll Number', source='system', section='identity',
       on_form=False, on_admit=True, locked=True),
    _f('name_bangla', 'Name of the Applicant (Bangla)', section='personal',
       required=True, on_admit=True),
    _f('full_name', 'Name of the Applicant (English, CAPITAL)', source='core',
       section='personal', required=True, on_admit=True, locked=True),
    _f('mother_name', "Mother's Name", section='personal', required=True, on_admit=True),
    _f('father_name', "Father's Name", section='personal', required=True, on_admit=True),
    _f('address', 'Present Address', section='personal', field_type='textarea', required=True),
    _f('permanent_address', 'Permanent Address', section='personal',
       field_type='textarea', required=True),
    _f('date_of_birth', 'Date of Birth (dd/mm/yyyy)', section='personal',
       field_type='text', required=True),
    _f('phone', 'Phone Number', source='core', section='personal', field_type='tel',
       required=True, on_admit=False, locked=True),
    _f('guardian_phone', 'Phone Number of Guardian', section='personal',
       field_type='tel', required=True),
    _f('guardian_relation', 'Relation with Guardian', section='personal', required=True),
    _f('email', 'Email', source='core', section='personal', field_type='email',
       required=False, on_admit=False),
]
_DEFAULT_FIELD_SCHEMA_TAIL = [
    _f('photo', 'Passport-size Photo', source='core', section='personal',
       field_type='photo', required=True, on_admit=True, locked=True),
    _f('candidate_signature', 'Signature of the Applicant', source='core',
       section='personal', field_type='photo', required=True, on_admit=True, locked=True),
    _f('payment_method', 'Payment Method', source='core', section='payment',
       required=True, on_admit=False, locked=True),
    _f('rocket_txn_id', 'Transaction ID (bKash / Nagad / Rocket)', source='core',
       section='payment', required=False, on_admit=False, locked=True),
    _f('rocket_sender_phone', 'Sender Account Number (bKash / Nagad / Rocket)',
       source='core', section='payment', field_type='tel', required=False,
       on_admit=False, locked=True),
    _f('bank_slip_txn_no', 'Bank Slip / Transaction Number', source='core',
       section='payment', required=False, on_admit=False, locked=True),
    _f('bank_slip', 'Bank Deposit Slip Photo', source='core', section='payment',
       field_type='photo', required=False, on_admit=False, locked=True),
    _f('payment_status', 'Payment', source='system', section='payment',
       on_form=False, on_admit=False, locked=True),
]


def default_field_schema():
    schema = deepcopy(_DEFAULT_FIELD_SCHEMA_HEAD) + _academic_default_fields() + deepcopy(_DEFAULT_FIELD_SCHEMA_TAIL)
    for i, f in enumerate(schema):
        f['order'] = i
    return schema


def _slug_key(label, used):
    base = re.sub(r'[^a-z0-9]+', '_', (label or '').strip().lower()).strip('_')[:40] or 'field'
    key = base
    n = 2
    while key in used or key in RESERVED_KEYS:
        key = f'{base}_{n}'
        n += 1
    return key


def _normalize_field(raw, index=0):
    if not isinstance(raw, dict):
        return None
    key = re.sub(r'[^a-z0-9_]', '', str(raw.get('key') or '').strip().lower())[:40]
    if not key:
        return None
    label = (raw.get('label') or key.replace('_', ' ').title()).strip()[:120] or key
    source = (raw.get('source') or 'extra').strip().lower()
    if key in SYSTEM_KEYS:
        source = 'system'
    elif key in CORE_KEYS:
        source = 'core'
    else:
        source = 'extra'
    section = (raw.get('section') or 'personal').strip().lower()
    if section not in ('identity', 'personal', 'academic', 'payment', 'other'):
        section = 'personal'
    field_type = (raw.get('field_type') or 'text').strip().lower()
    if field_type not in ('text', 'email', 'tel', 'date', 'textarea', 'photo'):
        field_type = 'text'
    if key in ('photo', 'bank_slip', 'candidate_signature'):
        field_type = 'photo'
    locked = bool(raw.get('locked')) or key in (
        'full_name', 'phone', 'photo', 'candidate_signature', 'payment_method',
        'rocket_txn_id', 'rocket_sender_phone',
        'bank_slip_txn_no', 'bank_slip',
        'application_id', 'roll_no', 'payment_status',
    )
    on_form = bool(raw.get('on_form'))
    on_admit = bool(raw.get('on_admit'))
    on_app_pdf = bool(raw.get('on_app_pdf'))
    required = bool(raw.get('required'))
    if key in ('full_name', 'phone', 'photo', 'candidate_signature'):
        on_form = True
        required = True
    if key == 'payment_status':
        on_admit = False
    # Paper-form admit card: identity only (not contact / payment)
    if key in ('phone', 'email') or key in PAYMENT_FIELD_KEYS:
        on_admit = False
    if key in ('name_bangla', 'mother_name', 'father_name', 'candidate_signature'):
        on_admit = True
    if key in ACADEMIC_FIELD_KEYS:
        on_admit = False
    if key in PAYMENT_FIELD_KEYS:
        on_form = True
        if key == 'payment_method':
            required = True
        else:
            required = False
    if key in ('application_id', 'roll_no'):
        on_form = False
    if source == 'system':
        on_form = False
        required = False
    return {
        'key': key,
        'label': label,
        'source': source,
        'section': section,
        'field_type': field_type,
        'required': required,
        'on_form': on_form,
        'on_admit': on_admit,
        'on_app_pdf': on_app_pdf,
        'locked': locked,
        'order': index,
    }


def normalize_field_schema(raw_list):
    if not isinstance(raw_list, list) or not raw_list:
        return default_field_schema()
    out = []
    seen = set()
    for i, item in enumerate(raw_list):
        field = _normalize_field(item, i)
        if not field or field['key'] in seen:
            continue
        seen.add(field['key'])
        out.append(field)
    have = {f['key'] for f in out}
    for essential in default_field_schema():
        if essential['key'] in have:
            continue
        out.append(deepcopy(essential))
        have.add(essential['key'])
    default_order = {f['key']: i for i, f in enumerate(default_field_schema())}
    out.sort(key=lambda f: (default_order.get(f['key'], 1000 + f.get('order', 0)), f['key']))
    for i, f in enumerate(out):
        f['order'] = i
    return out


def get_field_schema(cycle):
    raw = None
    if cycle is not None:
        raw = getattr(cycle, 'field_schema', None)
    if not raw or not str(raw).strip():
        return default_field_schema()
    try:
        data = json.loads(raw)
    except Exception:
        return default_field_schema()
    if isinstance(data, dict) and isinstance(data.get('fields'), list):
        data = data['fields']
    return normalize_field_schema(data)


def serialize_field_schema(fields):
    return json.dumps(normalize_field_schema(fields), ensure_ascii=False)


def fields_where(cycle, flag):
    return [f for f in get_field_schema(cycle) if f.get(flag)]


def form_input_fields(cycle):
    """Text-like inputs on apply form (excludes files, payment, academic table keys)."""
    return [
        f for f in fields_where(cycle, 'on_form')
        if f.get('key') not in FILE_FIELD_KEYS
        and f.get('source') != 'system'
        and f.get('key') not in PAYMENT_FIELD_KEYS
        and f.get('key') not in ACADEMIC_FIELD_KEYS
    ]


def academic_form_enabled(cycle):
    keys = {f['key'] for f in fields_where(cycle, 'on_form')}
    return any(k in keys for k in ACADEMIC_FIELD_KEYS)


def extra_field_defs(cycle):
    return [(f['key'], f['label']) for f in get_field_schema(cycle) if f.get('source') == 'extra']


def parse_extra_fields(candidate):
    try:
        data = json.loads(candidate.extra_fields) if candidate and candidate.extra_fields else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def collect_extra_fields(form, cycle=None, existing=None):
    result = dict(existing or {})
    for f in get_field_schema(cycle):
        if f.get('source') != 'extra':
            continue
        key = f['key']
        if key == ACADEMIC_EXTRA_ROWS_KEY:
            continue
        if key in form:
            result[key] = (form.get(key) or '').strip()
    # Preserve / refresh dynamic academic rows from form when present
    if hasattr(form, 'getlist') and 'extra_row_exam_name' in form:
        result[ACADEMIC_EXTRA_ROWS_KEY] = collect_academic_extra_rows(form)
    return result


def collect_academic_extra_rows(form):
    """Parse optional extra academic qualification rows from multipart form."""
    names = form.getlist('extra_row_exam_name') if hasattr(form, 'getlist') else []
    years = form.getlist('extra_row_year') if hasattr(form, 'getlist') else []
    boards = form.getlist('extra_row_board') if hasattr(form, 'getlist') else []
    institutions = form.getlist('extra_row_institution') if hasattr(form, 'getlist') else []
    cgpas = form.getlist('extra_row_cgpa') if hasattr(form, 'getlist') else []
    percentages = form.getlist('extra_row_percentage') if hasattr(form, 'getlist') else []
    rows = []
    n = max(len(names), len(years), len(boards), len(institutions), len(cgpas), len(percentages))
    for i in range(n):
        exam_name = (names[i] if i < len(names) else '').strip()
        year = (years[i] if i < len(years) else '').strip()
        board = (boards[i] if i < len(boards) else '').strip()
        institution = (institutions[i] if i < len(institutions) else '').strip()
        cgpa = (cgpas[i] if i < len(cgpas) else '').strip()
        percentage = (percentages[i] if i < len(percentages) else '').strip()
        if not any((exam_name, year, board, institution, cgpa, percentage)):
            continue
        rows.append({
            'exam_name': exam_name,
            'year': year,
            'board': board,
            'institution': institution,
            'cgpa': cgpa,
            'percentage': percentage,
        })
    return rows


def parse_academic_extra_rows(extra):
    if not isinstance(extra, dict):
        return []
    rows = extra.get(ACADEMIC_EXTRA_ROWS_KEY) or []
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({
            'exam_name': (row.get('exam_name') or '').strip(),
            'year': (row.get('year') or '').strip(),
            'board': (row.get('board') or '').strip(),
            'institution': (row.get('institution') or '').strip(),
            'cgpa': (row.get('cgpa') or '').strip(),
            'percentage': (row.get('percentage') or '').strip(),
        })
    return out


def academic_display_rows(extra):
    """Fixed SSC/HSC/LLB/Other rows + dynamic extra rows for tables/PDFs."""
    extra = extra if isinstance(extra, dict) else {}
    rows = []
    for prefix, exam_label in ACADEMIC_EXAM_ROWS:
        label = exam_label
        if prefix == 'other':
            other_name = (extra.get('other_exam_name') or '').strip()
            if other_name:
                label = f'Others ({other_name})'
        rows.append({
            'label': label,
            'year': (extra.get(f'{prefix}_year') or '').strip(),
            'board': (extra.get(f'{prefix}_board') or '').strip(),
            'institution': (extra.get(f'{prefix}_institution') or '').strip(),
            'cgpa': (extra.get(f'{prefix}_cgpa') or '').strip(),
            'percentage': (extra.get(f'{prefix}_percentage') or '').strip(),
            'fixed': True,
            'prefix': prefix,
        })
    for row in parse_academic_extra_rows(extra):
        rows.append({
            'label': row['exam_name'] or 'Additional qualification',
            'year': row['year'],
            'board': row['board'],
            'institution': row['institution'],
            'cgpa': row['cgpa'],
            'percentage': row['percentage'],
            'fixed': False,
            'prefix': None,
        })
    return rows


def default_document_tags():
    try:
        from utils.tenant import current_tenant
        tags = current_tenant().raw.get('document_tags')
        if tags:
            return list(tags)
    except Exception:
        pass
    return list(DEFAULT_DOCUMENT_TAGS)


def normalize_document_tags(raw):
    tags = []
    seen = set()
    items = raw
    if isinstance(raw, str):
        try:
            items = json.loads(raw)
        except Exception:
            items = [line.strip() for line in raw.replace(',', '\n').splitlines()]
    if not isinstance(items, list):
        return default_document_tags()
    for item in items:
        tag = (str(item) if item is not None else '').strip()[:120]
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(tag)
    return tags or default_document_tags()


def get_document_tags(cycle):
    raw = getattr(cycle, 'document_tags', None) if cycle is not None else None
    if not raw or not str(raw).strip():
        return default_document_tags()
    return normalize_document_tags(raw)


def serialize_document_tags(tags):
    return json.dumps(normalize_document_tags(tags), ensure_ascii=False)


def personal_extra_field_defs(cycle):
    """Extra fields excluding academic table keys (for admin personal info lists)."""
    return [
        (f['key'], f['label'])
        for f in get_field_schema(cycle)
        if f.get('source') == 'extra'
        and f.get('key') not in ACADEMIC_FIELD_KEYS
        and f.get('key') != ACADEMIC_EXTRA_ROWS_KEY
        and f.get('section') != 'academic'
    ]


def candidate_field_value(candidate, field, extra=None):
    if not candidate or not field:
        return ''
    key = field['key']
    source = field.get('source')
    if source == 'core':
        if key == 'photo':
            return 'Yes' if candidate.photo_path else ''
        if key == 'candidate_signature':
            return 'Yes' if getattr(candidate, 'signature_path', None) else ''
        if key == 'bank_slip':
            return 'Yes' if getattr(candidate, 'bank_slip_path', None) else ''
        if key == 'payment_method':
            method = (getattr(candidate, 'payment_method', None) or DEFAULT_PAYMENT_METHOD).strip().lower()
            return PAYMENT_METHOD_LABELS.get(method, method.replace('_', ' ').title())
        method = (getattr(candidate, 'payment_method', None) or DEFAULT_PAYMENT_METHOD).strip().lower()
        if key in ('rocket_txn_id', 'rocket_sender_phone') and method in BANK_PAYMENT_METHODS:
            return ''
        if key in ('bank_slip_txn_no', 'bank_slip') and method in MFS_PAYMENT_METHODS:
            return ''
        val = getattr(candidate, key, None)
        return '' if val is None else str(val)
    if source == 'system':
        if key == 'application_id':
            return candidate.application_id or ''
        if key == 'roll_no':
            return candidate.roll_no or ''
        if key == 'payment_status':
            method = (getattr(candidate, 'payment_method', None) or DEFAULT_PAYMENT_METHOD).strip().lower()
            method_label = PAYMENT_METHOD_LABELS.get(method, 'Payment')
            if candidate.payment_status == 'verified':
                return f'Verified ({method_label})'
            status = (candidate.payment_status or '').replace('_', ' ').title()
            return f'{status} ({method_label})' if status else method_label
        return ''
    extra = extra if extra is not None else parse_extra_fields(candidate)
    return (extra.get(key) or '').strip()


def parse_schema_from_form(form):
    keys = form.getlist('field_key')
    labels = form.getlist('field_label')
    sections = form.getlist('field_section')
    types = form.getlist('field_type')
    sources = form.getlist('field_source')
    n = len(keys)
    fields = []
    used = set()
    for i in range(n):
        key = (keys[i] if i < len(keys) else '').strip().lower()
        label = (labels[i] if i < len(labels) else '').strip()
        if not key and label:
            key = _slug_key(label, used)
        key = re.sub(r'[^a-z0-9_]', '', key)[:40]
        if not key or key in used:
            continue
        used.add(key)
        source = (sources[i] if i < len(sources) else 'extra').strip().lower()
        if key in SYSTEM_KEYS:
            source = 'system'
        elif key in CORE_KEYS:
            source = 'core'
        else:
            source = 'extra'
        fields.append({
            'key': key,
            'label': label or key.replace('_', ' ').title(),
            'source': source,
            'section': (sections[i] if i < len(sections) else 'personal'),
            'field_type': (types[i] if i < len(types) else 'text'),
            'required': form.get(f'field_required_{i}') == '1',
            'on_form': form.get(f'field_on_form_{i}') == '1',
            'on_admit': form.get(f'field_on_admit_{i}') == '1',
            'on_app_pdf': form.get(f'field_on_app_pdf_{i}') == '1',
            'locked': form.get(f'field_locked_{i}') == '1',
            'order': i,
        })
    new_label = (form.get('new_field_label') or '').strip()
    if new_label:
        new_key = _slug_key(form.get('new_field_key') or new_label, used)
        fields.append({
            'key': new_key,
            'label': new_label,
            'source': 'extra',
            'section': (form.get('new_field_section') or 'personal').strip().lower(),
            'field_type': (form.get('new_field_type') or 'text').strip().lower(),
            'required': form.get('new_field_required') == '1',
            'on_form': form.get('new_field_on_form', '1') == '1',
            'on_admit': form.get('new_field_on_admit') == '1',
            'on_app_pdf': form.get('new_field_on_app_pdf', '1') == '1',
            'locked': False,
            'order': len(fields),
        })
    return normalize_field_schema(fields)
