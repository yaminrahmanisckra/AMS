"""Admin switch for whether teachers can see who submitted student feedback."""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_SHOW_RESPONDENT_IDENTITY = True


def _settings_path() -> Path:
    code = 'law'
    try:
        from utils.tenant import current_tenant
        code = current_tenant().code or code
    except Exception:
        pass
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            root = Path(current_app.instance_path)
            root.mkdir(parents=True, exist_ok=True)
            return root / f'feedback_identity_{code}.json'
    except Exception:
        pass
    from utils.tenant import PACKAGE_ROOT
    root = PACKAGE_ROOT / 'instance'
    root.mkdir(parents=True, exist_ok=True)
    return root / f'feedback_identity_{code}.json'


def feedback_identity_visible() -> bool:
    """True when teachers may see student names and the submitted/pending lists."""
    path = _settings_path()
    if not path.is_file():
        return DEFAULT_SHOW_RESPONDENT_IDENTITY
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError):
        return DEFAULT_SHOW_RESPONDENT_IDENTITY
    if not isinstance(data, dict) or 'show_respondent_identity' not in data:
        return DEFAULT_SHOW_RESPONDENT_IDENTITY
    return bool(data.get('show_respondent_identity'))


def save_feedback_identity_visible(enabled: bool) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({'show_respondent_identity': bool(enabled)}, indent=2),
        encoding='utf-8',
    )
