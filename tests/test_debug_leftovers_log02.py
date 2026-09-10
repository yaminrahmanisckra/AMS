"""LOG-02: Cursor debug.log, ngrok hacks, and /test_download must stay gone."""
import importlib.util
from pathlib import Path

_CHECKER = Path(__file__).resolve().parents[1] / 'scripts/security/check_debug_leftovers.py'
_spec = importlib.util.spec_from_file_location('check_debug_leftovers', _CHECKER)
_checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checker)


def test_no_cursor_debug_leftovers():
    hits = _checker.find_leftovers()
    assert hits == [], 'Debug leftovers:\n' + '\n'.join(hits)
