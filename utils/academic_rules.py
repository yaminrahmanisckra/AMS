"""Per-tenant academic calculation rules (assessment totals, result splits, grades).

Load order: built-in Law defaults ← tenants/<code>/academic.yaml ← instance/academic_rules.yaml
Admin saves only the instance override so git pulls do not wipe local customisation.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

import yaml

from utils.tenant import TENANTS_ROOT, current_tenant

ASSESSMENT_TOTAL_MODE_KEYS = ('best_three', 'part_a_b_15', 'best_three_40')

DEFAULT_RULES = {
    'assessment': {
        'slots': 4,
        'take_best': 3,
        'slot_max': 10,
        'ug_out_of': 30,
        'pg_out_of': 40,
        'pg_scale_from': 30,
        'part_a_b_each': 15,
        'available_total_modes': list(ASSESSMENT_TOTAL_MODE_KEYS),
        'allow_internal_total_modes': True,
    },
    'results': {
        'theory_ug': {'attendance': 10, 'ca': 30, 'part_a': 30, 'part_b': 30},
        'theory_pg': {'attendance': 10, 'ca': 40, 'part_a': 25, 'part_b': 25},
        'sessional': {'attendance': 10, 'report': 60, 'viva': 30},
        'thesis_ug': {'contact': 10, 'evaluation': 60, 'presentation': 30},
        'dissertation_proposal': {'supervisor': 30, 'presentation': 70},
        'dissertation_defence': {'supervisor': 20, 'report': 50, 'defense': 30},
        'viva': {'viva': 100},
    },
    'grades': {
        'retake_step_down': True,
        'bands': [
            {'letter': 'A+', 'min': 80, 'point': 4.0},
            {'letter': 'A', 'min': 75, 'point': 3.75},
            {'letter': 'A-', 'min': 70, 'point': 3.5},
            {'letter': 'B+', 'min': 65, 'point': 3.25},
            {'letter': 'B', 'min': 60, 'point': 3.0},
            {'letter': 'B-', 'min': 55, 'point': 2.75},
            {'letter': 'C+', 'min': 50, 'point': 2.5},
            {'letter': 'C', 'min': 45, 'point': 2.25},
            {'letter': 'D', 'min': 40, 'point': 2.0},
        ],
    },
}

_CACHE: Optional[dict] = None


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = deepcopy(base)
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding='utf-8') as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def _instance_override_path() -> Path:
    code = 'law'
    try:
        code = current_tenant().code
    except Exception:
        pass
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            return Path(current_app.instance_path) / f'academic_rules_{code}.yaml'
    except Exception:
        pass
    from utils.tenant import PACKAGE_ROOT
    return PACKAGE_ROOT / 'instance' / f'academic_rules_{code}.yaml'


def tenant_pack_academic_path() -> Optional[Path]:
    try:
        tenant = current_tenant()
    except Exception:
        return None
    path = tenant.root / 'academic.yaml'
    if path.is_file():
        return path
    fallback = TENANTS_ROOT / '_default' / 'academic.yaml'
    return fallback if fallback.is_file() else None


def pack_defaults() -> dict:
    """Defaults + tenant pack (no instance override). Used by Reset."""
    merged = deepcopy(DEFAULT_RULES)
    pack = tenant_pack_academic_path()
    if pack:
        merged = _deep_merge(merged, _read_yaml(pack))
    return _normalize(merged)


def load_academic_rules() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    merged = pack_defaults()
    override = _read_yaml(_instance_override_path())
    if override:
        merged = _normalize(_deep_merge(merged, override))
    _CACHE = merged
    return merged


def reset_academic_rules_cache() -> None:
    global _CACHE
    _CACHE = None


def save_academic_rules(data: dict) -> Path:
    path = _instance_override_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize(_deep_merge(DEFAULT_RULES, data))
    with path.open('w', encoding='utf-8') as fh:
        yaml.safe_dump(normalized, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    reset_academic_rules_cache()
    return path


def clear_instance_override() -> None:
    path = _instance_override_path()
    if path.is_file():
        path.unlink()
    reset_academic_rules_cache()


def instance_override_exists() -> bool:
    return _instance_override_path().is_file()


def _as_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize(rules: dict) -> dict:
    assessment = dict(rules.get('assessment') or {})
    defaults_a = DEFAULT_RULES['assessment']
    raw_modes = assessment.get('available_total_modes', defaults_a['available_total_modes'])
    if isinstance(raw_modes, str):
        raw_modes = [part.strip() for part in raw_modes.split(',')]
    modes = []
    for item in raw_modes or []:
        key = str(item or '').strip().lower()
        if key in ASSESSMENT_TOTAL_MODE_KEYS and key not in modes:
            modes.append(key)
    if not modes:
        modes = list(ASSESSMENT_TOTAL_MODE_KEYS)

    allow_internal = assessment.get('allow_internal_total_modes', True)
    if isinstance(allow_internal, str):
        allow_internal = allow_internal.strip().lower() in ('1', 'true', 'yes', 'on')

    assessment = {
        'slots': max(1, min(8, _as_int(assessment.get('slots'), defaults_a['slots']))),
        'take_best': max(1, min(8, _as_int(assessment.get('take_best'), defaults_a['take_best']))),
        'slot_max': max(1, _as_int(assessment.get('slot_max'), defaults_a['slot_max'])),
        'ug_out_of': max(1, _as_int(assessment.get('ug_out_of'), defaults_a['ug_out_of'])),
        'pg_out_of': max(1, _as_int(assessment.get('pg_out_of'), defaults_a['pg_out_of'])),
        'pg_scale_from': max(1, _as_int(assessment.get('pg_scale_from'), defaults_a['pg_scale_from'])),
        'part_a_b_each': max(1, _as_int(assessment.get('part_a_b_each'), defaults_a['part_a_b_each'])),
        'available_total_modes': modes,
        'allow_internal_total_modes': bool(allow_internal),
    }
    if assessment['take_best'] > assessment['slots']:
        assessment['take_best'] = assessment['slots']

    results = {}
    for group, fields in DEFAULT_RULES['results'].items():
        raw = dict((rules.get('results') or {}).get(group) or {})
        results[group] = {
            key: max(0, _as_int(raw.get(key), default))
            for key, default in fields.items()
        }

    raw_grades = dict(rules.get('grades') or {})
    bands = []
    for item in raw_grades.get('bands') or DEFAULT_RULES['grades']['bands']:
        if not isinstance(item, dict):
            continue
        letter = str(item.get('letter') or '').strip()
        if not letter:
            continue
        bands.append({
            'letter': letter,
            'min': max(0, _as_int(item.get('min'), 0)),
            'point': _as_float(item.get('point'), 0.0),
        })
    if not bands:
        bands = deepcopy(DEFAULT_RULES['grades']['bands'])
    bands.sort(key=lambda b: b['min'], reverse=True)

    retake = raw_grades.get('retake_step_down', True)
    if isinstance(retake, str):
        retake = retake.strip().lower() in ('1', 'true', 'yes', 'on')

    return {
        'assessment': assessment,
        'results': results,
        'grades': {
            'retake_step_down': bool(retake),
            'bands': bands,
        },
    }


def assessment_cfg() -> dict:
    return load_academic_rules()['assessment']


def available_assessment_total_modes() -> list:
    return list(assessment_cfg().get('available_total_modes') or ASSESSMENT_TOTAL_MODE_KEYS)


def allow_internal_assessment_total_modes() -> bool:
    return bool(assessment_cfg().get('allow_internal_total_modes', True))


def result_split(kind: str) -> dict:
    return dict(load_academic_rules()['results'].get(kind) or {})


def take_best_marks(marks) -> list:
    vals = sorted([float(m) for m in marks if m is not None], reverse=True)
    n = assessment_cfg()['take_best']
    return vals[:n] if vals else []


def scale_pg_total(best_sum: float) -> float:
    cfg = assessment_cfg()
    scale_from = float(cfg['pg_scale_from'])
    if scale_from <= 0:
        return float(best_sum)
    return (float(best_sum) / scale_from) * float(cfg['pg_out_of'])


def calculate_grade(total_marks, is_retake=False):
    try:
        total = float(total_marks)
    except (TypeError, ValueError):
        return 0.0, 'F'
    grades = load_academic_rules()['grades']
    letter = 'F'
    point = 0.0
    for band in grades['bands']:
        if total >= band['min']:
            letter = band['letter']
            point = float(band['point'])
            break
    if is_retake and grades.get('retake_step_down') and letter != 'F':
        letters = [b['letter'] for b in grades['bands']]
        try:
            idx = letters.index(letter)
        except ValueError:
            return point, letter
        if idx + 1 < len(letters):
            nxt = grades['bands'][idx + 1]
            return float(nxt['point']), nxt['letter']
        return 0.0, 'F'
    return point, letter
