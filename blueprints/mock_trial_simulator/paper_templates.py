"""Document templates that IO / expert witnesses fill in.

Add entries to WITNESS_PAPER_TEMPLATES when the teacher names the papers.
Each item:

    {
        'key': 'seizure_list',
        'title': 'Seizure list',
        'title_bn': 'জব্দনামা',
        'description': 'Short hint for the student.',
        'fields': [
            {'key': 'place', 'label': 'Place of seizure', 'type': 'text'},
            {'key': 'items', 'label': 'Items seized', 'type': 'textarea'},
        ],
    }
"""
from .models import WITNESS_EXPERT, WITNESS_IO

WITNESS_PAPER_TEMPLATES = {
    WITNESS_IO: [],
    WITNESS_EXPERT: [],
}

PAPER_STATUS_EMPTY = 'empty'
PAPER_STATUS_DRAFT = 'draft'
PAPER_STATUS_SUBMITTED = 'submitted'


def templates_for_role(role):
    return list(WITNESS_PAPER_TEMPLATES.get(role) or [])


def get_template(role, key):
    key = (key or '').strip()
    if not key:
        return None
    return next((item for item in templates_for_role(role) if item.get('key') == key), None)


def template_fields(spec):
    fields = list((spec or {}).get('fields') or [])
    if fields:
        return fields
    return [{
        'key': 'body',
        'label': (spec or {}).get('title') or 'Draft',
        'type': 'textarea',
    }]


def paper_rows_for_witness(witness):
    """Catalog rows joined with any saved draft for this witness."""
    if witness is None or not getattr(witness, 'is_official_prosecution', lambda: False)():
        return []
    saved = {item.template_key: item for item in (getattr(witness, 'papers', None) or [])}
    rows = []
    for spec in templates_for_role(witness.role):
        paper = saved.get(spec.get('key'))
        rows.append({
            'key': spec.get('key'),
            'spec': spec,
            'title': spec.get('title_bn') or spec.get('title') or spec.get('key'),
            'description': spec.get('description') or '',
            'paper': paper,
            'status': paper.status if paper else PAPER_STATUS_EMPTY,
        })
    return rows
