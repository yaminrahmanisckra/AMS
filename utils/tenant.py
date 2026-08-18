"""Per-process discipline tenant: branding, academic rules, feature flags, plugin packs.

Isolation is at the database / deployment layer. This module only loads the
config for TENANT_CODE (default: law). Unknown codes raise at startup so a
mis-set MCJ app cannot silently show Law branding.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

_TENANT: Optional['Tenant'] = None

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TENANTS_ROOT = PACKAGE_ROOT / 'tenants'
DEFAULT_TENANT_CODE = 'law'


class TenantConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tenant:
    code: str
    name: str
    short_name: str
    institute_label: str
    head_title: str
    office_label: str
    university_name: str
    public_url: str
    course_code_prefix: str
    year_digit_map: dict
    term_digit_map: dict
    pg_year_labels: tuple
    pg_course_year_digit: str
    features: dict
    app_id_prefix: str
    academic_exam_rows: tuple
    developer_title: str
    logo_static: str
    surveys_use_pack: bool
    default_program: str
    program_options: tuple
    root: Path
    raw: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def head_designation(self) -> str:
        return f'{self.head_title}, {self.institute_label}'

    @property
    def office_contact_line(self) -> str:
        return self.office_label

    @property
    def display_with_university(self) -> str:
        return f'{self.name}, {self.university_name}'

    @property
    def footer_credit(self) -> str:
        return f'Academic Management System (AMS), {self.name}, {self.university_name}'

    def feature_enabled(self, name: str, default: bool = True) -> bool:
        if name not in self.features:
            return default
        return bool(self.features[name])

    @property
    def year_labels_in_order(self) -> list:
        labels = []
        seen = set()
        for digit in sorted(self.year_digit_map.keys(), key=lambda d: (len(d), d)):
            label = self.year_digit_map[digit]
            if label not in seen:
                seen.add(label)
                labels.append(label)
        return labels

    @property
    def year_select_options(self) -> list:
        labels = list(self.year_labels_in_order)
        pg_lower = {str(x).lower() for x in self.pg_year_labels}
        if pg_lower & {'llm', 'masters', 'master', 'fifth'} and 'Fifth' not in labels:
            # Keep Fifth as a UI alias used by older registration screens
            labels.append('Fifth')
        return labels

    def to_template_dict(self) -> dict:
        return {
            'code': self.code,
            'name': self.name,
            'short_name': self.short_name,
            'institute_label': self.institute_label,
            'head_title': self.head_title,
            'head_designation': self.head_designation,
            'office_label': self.office_label,
            'office_contact_line': self.office_contact_line,
            'university_name': self.university_name,
            'public_url': self.public_url,
            'course_code_prefix': self.course_code_prefix,
            'app_id_prefix': self.app_id_prefix,
            'developer_title': self.developer_title,
            'logo_static': self.logo_static,
            'display_with_university': self.display_with_university,
            'footer_credit': self.footer_credit,
            'year_labels': self.year_labels_in_order,
            'year_select_options': self.year_select_options,
            'pg_year_labels': list(self.pg_year_labels),
            'pg_course_year_digit': self.pg_course_year_digit,
            'year_digit_map': dict(self.year_digit_map),
            'term_digit_map': dict(self.term_digit_map),
            'default_program': self.default_program,
            'program_options': list(self.program_options),
            'features': dict(self.features),
        }


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding='utf-8') as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise TenantConfigError(f'{path} must contain a YAML mapping')
    return data


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding='utf-8') as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise TenantConfigError(f'{path} must contain a JSON object')
    return data


def available_tenant_codes() -> list:
    if not TENANTS_ROOT.is_dir():
        return []
    codes = []
    for child in sorted(TENANTS_ROOT.iterdir()):
        if child.name.startswith('_') or child.name.startswith('.'):
            continue
        if child.is_dir() and (child / 'tenant.yaml').is_file():
            codes.append(child.name)
    return codes


_TENANT_CODE_RE = re.compile(r'^[a-z][a-z0-9_]{1,20}$')
_RESERVED_TENANT_CODES = {'_default', 'static', 'templates', 'admin', 'default'}


def normalize_tenant_code(raw: str) -> str:
    return (raw or '').strip().lower()


def validate_new_tenant_code(code: str) -> str:
    code = normalize_tenant_code(code)
    if not _TENANT_CODE_RE.match(code):
        raise TenantConfigError(
            'Code must start with a letter and use only lowercase letters, digits, or underscore (2–21 chars).'
        )
    if code in _RESERVED_TENANT_CODES:
        raise TenantConfigError(f'Code {code!r} is reserved.')
    dest = TENANTS_ROOT / code
    if dest.exists():
        raise TenantConfigError(f'A tenant pack already exists for {code!r}.')
    return code


def create_tenant_pack(
    *,
    code: str,
    name: str,
    short_name: str,
    copy_from: str = 'mcj',
    institute_label: str = '',
    university_name: str = 'Khulna University',
    course_code_prefix: str = '',
    app_id_prefix: str = '',
    pg_year_label: str = 'Masters',
    office_label: str = '',
    developer_title: str = '',
    public_url: str = '',
    features: Optional[dict] = None,
) -> Path:
    """Scaffold tenants/<code>/ from an existing pack. Does not create a database or switch TENANT_CODE."""
    code = validate_new_tenant_code(code)
    name = (name or '').strip()
    short_name = (short_name or code.upper()).strip()
    if not name:
        raise TenantConfigError('Discipline name is required.')

    copy_from = normalize_tenant_code(copy_from) or 'mcj'
    source_dir = TENANTS_ROOT / copy_from
    if not (source_dir / 'tenant.yaml').is_file():
        source_dir = TENANTS_ROOT / 'mcj'
    if not (source_dir / 'tenant.yaml').is_file():
        source_dir = TENANTS_ROOT / '_default'

    dest = TENANTS_ROOT / code
    try:
        dest.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise TenantConfigError(f'A tenant pack already exists for {code!r}.') from exc

    try:
        return _write_tenant_pack_contents(
            dest=dest,
            code=code,
            name=name,
            short_name=short_name,
            source_dir=source_dir,
            institute_label=institute_label,
            university_name=university_name,
            course_code_prefix=course_code_prefix,
            app_id_prefix=app_id_prefix,
            pg_year_label=pg_year_label,
            office_label=office_label,
            developer_title=developer_title,
            public_url=public_url,
            features=features,
        )
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise


def _write_tenant_pack_contents(
    *,
    dest: Path,
    code: str,
    name: str,
    short_name: str,
    source_dir: Path,
    institute_label: str,
    university_name: str,
    course_code_prefix: str,
    app_id_prefix: str,
    pg_year_label: str,
    office_label: str,
    developer_title: str,
    public_url: str,
    features: Optional[dict],
) -> Path:
    def _copy_file(src: Path, target: Path):
        if src.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)

    academic_src = source_dir / 'academic.yaml'
    if not academic_src.is_file():
        academic_src = TENANTS_ROOT / '_default' / 'academic.yaml'
    _copy_file(academic_src, dest / 'academic.yaml')

    curric_src = source_dir / 'curriculator.yaml'
    if not curric_src.is_file():
        curric_src = TENANTS_ROOT / '_default' / 'curriculator.yaml'
    _copy_file(curric_src, dest / 'curriculator.yaml')

    survey_src = TENANTS_ROOT / 'mcj' / 'surveys'
    if not survey_src.is_dir():
        survey_src = TENANTS_ROOT / '_default' / 'surveys'
    if survey_src.is_dir():
        shutil.copytree(survey_src, dest / 'surveys')

    (dest / 'templates').mkdir(exist_ok=True)
    (dest / 'static').mkdir(exist_ok=True)
    readme = dest / 'static' / 'README.md'
    if not readme.exists():
        readme.write_text(
            f'Optional static files for the {short_name} tenant (logo, etc.).\n',
            encoding='utf-8',
        )

    pg_label = (pg_year_label or 'Masters').strip() or 'Masters'
    prefix = (course_code_prefix or short_name).strip()
    app_prefix = (app_id_prefix or short_name).strip().upper() or short_name.upper()
    inst = (institute_label or f'{short_name} Discipline, KU').strip()
    office = (office_label or f'{short_name} Discipline office').strip()
    uni = (university_name or 'Khulna University').strip()
    feat = dict(features or {})
    for key in ('curriculator', 'self_assessment', 'admission_exam', 'remuneration', 'leave_application'):
        feat.setdefault(key, True)

    payload = {
        'code': code,
        'name': name,
        'short_name': short_name,
        'institute_label': inst,
        'head_title': 'Head',
        'office_label': office,
        'university_name': uni,
        'public_url': (public_url or '').strip().rstrip('/'),
        'course_code_prefix': prefix,
        'app_id_prefix': app_prefix,
        'developer_title': (developer_title or f'Assistant Professor, {name}, {uni}').strip(),
        'logo_static': 'images/KU_logo_2.png',
        'year_digit_map': {
            '1': 'First', '2': 'Second', '3': 'Third', '4': 'Fourth', '5': pg_label,
        },
        'term_digit_map': {'1': 'First', '2': 'Second'},
        'pg_year_labels': [pg_label],
        'pg_course_year_digit': '5',
        'surveys_use_pack': True,
        'default_program': 'Bachelor (Hons.)',
        'program_options': ['Bachelor (Hons.)', pg_label],
        'features': feat,
        'academic_exam_rows': [
            ['ssc', 'S.S.C. / Equivalent'],
            ['hsc', 'H.S.C. / Equivalent'],
            ['honours', 'Bachelor (Hons.)'],
            ['other', 'Others'],
        ],
        'document_tags': [
            'SSC Certificate',
            'SSC Transcript / Marksheet',
            'HSC Certificate',
            'HSC Transcript / Marksheet',
            'Bachelor Certificate',
            'Bachelor Transcript / Marksheet',
            'Other Certificate / Transcript',
        ],
    }
    yaml_path = dest / 'tenant.yaml'
    with yaml_path.open('w', encoding='utf-8') as fh:
        yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return dest


def _coerce_rows(raw) -> tuple:
    rows = []
    for item in raw or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append((str(item[0]), str(item[1])))
        elif isinstance(item, dict) and item.get('key') and item.get('label'):
            rows.append((str(item['key']), str(item['label'])))
    return tuple(rows)


def load_tenant(code: str) -> Tenant:
    code = (code or '').strip().lower()
    if not code:
        code = DEFAULT_TENANT_CODE
    tenant_dir = TENANTS_ROOT / code
    yaml_path = tenant_dir / 'tenant.yaml'
    if not yaml_path.is_file():
        known = ', '.join(available_tenant_codes()) or '(none)'
        raise TenantConfigError(
            f'Unknown TENANT_CODE={code!r}. Known tenants: {known}. '
            f'Expected file: {yaml_path}'
        )
    data = _read_yaml(yaml_path)
    year_digit_map = {str(k): str(v) for k, v in (data.get('year_digit_map') or {}).items()}
    if not year_digit_map:
        year_digit_map = {
            '1': 'First', '2': 'Second', '3': 'Third', '4': 'Fourth', '5': 'LLM',
        }
    term_digit_map = {str(k): str(v) for k, v in (data.get('term_digit_map') or {}).items()}
    if not term_digit_map:
        term_digit_map = {'1': 'First', '2': 'Second'}
    pg_labels = tuple(str(x) for x in (data.get('pg_year_labels') or ['LLM']))
    features = dict(data.get('features') or {})
    academic_rows = _coerce_rows(data.get('academic_exam_rows'))
    default_program = str(data.get('default_program') or '').strip()
    if not default_program:
        for key, label in academic_rows:
            if key not in ('ssc', 'hsc', 'other'):
                default_program = label
                break
    program_options = tuple(str(x) for x in (data.get('program_options') or []) if str(x).strip())
    if not program_options:
        program_options = tuple(lbl for _, lbl in academic_rows if _ not in ('ssc', 'hsc', 'other')) or tuple(pg_labels)
    return Tenant(
        code=code,
        name=str(data.get('name') or code.upper()),
        short_name=str(data.get('short_name') or code.upper()),
        institute_label=str(data.get('institute_label') or data.get('name') or code.upper()),
        head_title=str(data.get('head_title') or 'Head'),
        office_label=str(data.get('office_label') or f'{data.get("name") or code} office'),
        university_name=str(data.get('university_name') or 'Khulna University'),
        public_url=str(data.get('public_url') or '').rstrip('/'),
        course_code_prefix=str(data.get('course_code_prefix') or ''),
        year_digit_map=year_digit_map,
        term_digit_map=term_digit_map,
        pg_year_labels=pg_labels,
        pg_course_year_digit=str(data.get('pg_course_year_digit') or '5'),
        features=features,
        app_id_prefix=str(data.get('app_id_prefix') or 'APP').strip().upper() or 'APP',
        academic_exam_rows=academic_rows,
        developer_title=str(data.get('developer_title') or ''),
        logo_static=str(data.get('logo_static') or 'images/KU_logo_2.png'),
        surveys_use_pack=bool(data.get('surveys_use_pack', False)),
        default_program=default_program,
        program_options=program_options,
        root=tenant_dir,
        raw=data,
    )


def init_tenant(app=None, code: Optional[str] = None) -> Tenant:
    """Load tenant for this process. Call once from create_app()."""
    global _TENANT
    resolved = (code or os.getenv('TENANT_CODE') or DEFAULT_TENANT_CODE).strip().lower()
    _TENANT = load_tenant(resolved)
    load_curriculator_pack.cache_clear()
    load_survey_pack.cache_clear()
    try:
        from utils.academic_rules import reset_academic_rules_cache
        reset_academic_rules_cache()
    except Exception:
        pass
    if app is not None:
        app.config['TENANT_CODE'] = _TENANT.code
        app.extensions['tenant'] = _TENANT
        _install_template_loader(app, _TENANT)
    return _TENANT


def current_tenant() -> Tenant:
    global _TENANT
    if _TENANT is None:
        _TENANT = load_tenant((os.getenv('TENANT_CODE') or DEFAULT_TENANT_CODE).strip().lower())
    return _TENANT


def reset_tenant_cache():
    """Test helper."""
    global _TENANT
    _TENANT = None
    load_curriculator_pack.cache_clear()
    load_survey_pack.cache_clear()
    try:
        from utils.academic_rules import reset_academic_rules_cache
        reset_academic_rules_cache()
    except Exception:
        pass


def _install_template_loader(app, tenant: Tenant):
    from jinja2 import ChoiceLoader, FileSystemLoader

    tenant_templates = tenant.root / 'templates'
    if not tenant_templates.is_dir():
        return
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(str(tenant_templates)),
        app.jinja_loader,
    ])


def tenant_pack_path(*parts: str, fallback: bool = True) -> Optional[Path]:
    tenant = current_tenant()
    candidate = tenant.root.joinpath(*parts)
    if candidate.is_file():
        return candidate
    if fallback:
        default_path = TENANTS_ROOT / '_default' / Path(*parts)
        if default_path.is_file():
            return default_path
    return None


@lru_cache(maxsize=8)
def load_curriculator_pack() -> dict:
    path = tenant_pack_path('curriculator.yaml')
    if not path:
        return {
            'parts': [
                {'key': 'A', 'title': 'Part A'},
                {'key': 'B', 'title': 'Part B'},
                {'key': 'C', 'title': 'Part C'},
                {'key': 'D', 'title': 'Part D'},
            ],
            'year_term_grid': [
                ['First', 'First'], ['First', 'Second'],
                ['Second', 'First'], ['Second', 'Second'],
                ['Third', 'First'],
                ['Fourth', 'First'], ['Fourth', 'Second'],
                ['LLM', 'First'], ['LLM', 'Second'],
            ],
            'part_a_sections': [],
            'mapping_course_plo_year_term': {},
        }
    return _read_yaml(path)


@lru_cache(maxsize=32)
def load_survey_pack(survey_type: str) -> dict:
    survey_type = (survey_type or '').strip().lower()
    path = tenant_pack_path('surveys', f'{survey_type}.json')
    if not path:
        return {}
    return _read_json(path)


def infer_year_term_from_code(course_code: str) -> tuple:
    """Infer (year_label, term_label) from last 4 digits of a course code."""
    if not course_code:
        return '', ''
    digits = ''.join(ch for ch in str(course_code) if ch.isdigit())
    if len(digits) < 4:
        return '', ''
    relevant = digits[-4:]
    tenant = current_tenant()
    year = tenant.year_digit_map.get(relevant[0], '')
    term = tenant.term_digit_map.get(relevant[1], '')
    return year, term


def year_is_postgraduate(year_label: Any) -> bool:
    if not year_label:
        return False
    value = str(year_label).strip().upper()
    tenant = current_tenant()
    labels = {str(x).strip().upper() for x in tenant.pg_year_labels}
    labels.update({'PG', 'MPHIL', 'M.PHIL', 'PHD', 'MASTER', 'MASTERS'})
    return any(token in value for token in labels)


def course_year_digit_is_pg(course_code: str) -> bool:
    digits = ''.join(ch for ch in str(course_code or '') if ch.isdigit())
    if len(digits) < 4:
        return False
    return digits[-4:][0] == str(current_tenant().pg_course_year_digit)


def normalize_registration_year(label: Any) -> str:
    """Canonical year key for registration matching (tenant PG aliases collapse)."""
    if not label:
        return ''
    value = str(label).strip().lower()
    for suffix in (' year', 'yr', ' years'):
        if value.endswith(suffix):
            value = value[:-len(suffix)].strip()
    ordinal = {
        '1': 'first', '1st': 'first', 'first': 'first',
        '2': 'second', '2nd': 'second', 'second': 'second',
        '3': 'third', '3rd': 'third', 'third': 'third',
        '4': 'fourth', '4th': 'fourth', 'fourth': 'fourth',
        '5': 'fifth', '5th': 'fifth', 'fifth': 'fifth',
    }
    canonical = ordinal.get(value, value)
    tenant = current_tenant()
    pg_lower = {str(x).strip().lower() for x in tenant.pg_year_labels}
    pg_lower.update({'fifth', 'llm', 'masters', 'master'})
    if canonical in pg_lower:
        # Stable key: first configured PG label, lowercased
        return str(tenant.pg_year_labels[0]).strip().lower() if tenant.pg_year_labels else 'llm'
    return canonical


def public_app_url() -> str:
    from flask import current_app, has_app_context, request

    if has_app_context():
        configured = (current_app.config.get('PUBLIC_APP_URL') or '').strip().rstrip('/')
        if configured:
            return configured
        try:
            if request and request.host_url:
                return request.host_url.rstrip('/')
        except RuntimeError:
            pass
    return (current_tenant().public_url or '').rstrip('/')
