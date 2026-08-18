"""Exam remuneration bill rates (admin-editable per deployment).

Load order: built-in defaults ← instance/remuneration_rates_<tenant>.yaml
Admin saves only the instance override so git pulls do not wipe local rates.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

import yaml

DEFAULT_RATES: dict[str, list[dict[str, str]]] = {
    '1': [
        {'label': 'স্নাতক (প্রতি প্রশ্নপত্র)', 'value': '2300'},
        {'label': 'স্নাতকোত্তর/এমফিল/পিএইচডি (প্রতি প্রশ্নপত্র)', 'value': '2400'},
    ],
    '2': [
        {'label': 'সর্বোচ্চ', 'value': '2400'},
        {'label': 'সর্বনিম্ন', 'value': '1500'},
    ],
    '3': [
        {'label': 'স্নাতক - অর্ধ পত্র (প্রতি উত্তরপত্র)', 'value': '80'},
        {'label': 'স্নাতক - ক্লাস টেস্ট/টার্ম পেপার (প্রতি পরীক্ষার্থী)', 'value': '30'},
        {'label': 'স্নাতকোত্তর - অর্ধ পত্র (প্রতি উত্তরপত্র)', 'value': '100'},
        {'label': 'স্নাতকোত্তর - ক্লাস টেস্ট/টার্ম পেপার (প্রতি পরীক্ষার্থী)', 'value': '80'},
        {'label': 'স্নাতকোত্তর - মিড টার্ম পূর্ণপত্র (প্রতি উত্তরপত্র)', 'value': '60'},
        {'label': 'স্নাতকোত্তর - টার্ম ফাইনাল পূর্ণপত্র (প্রতি উত্তরপত্র)', 'value': '160'},
        {'label': 'ন্যূনতম (প্রতি কোর্স)', 'value': '600'},
    ],
    '4': [
        {'label': 'স্নাতক - ক্লাস টেস্ট/টার্ম পেপার (প্রতি পরীক্ষার্থী)', 'value': '30'},
        {'label': 'স্নাতকোত্তর - ক্লাস টেস্ট/টার্ম পেপার (প্রতি পরীক্ষার্থী)', 'value': '40'},
    ],
    '5': [
        {'label': 'প্রজেক্ট পেপার/এ্যাসাইনমেন্ট (প্রতি পরীক্ষার্থী)', 'value': '230'},
        {'label': 'ফিল্ড ওয়ার্ক/সার্ভে ওয়ার্ক (প্রতি পরীক্ষার্থী)', 'value': '300'},
        {'label': 'মৌখিক পরীক্ষা (প্রতি পরীক্ষার্থী)', 'value': '50'},
        {'label': 'ল্যাব কর্মকর্তা', 'value': '200'},
        {'label': '৩য় শ্রেণির কর্মচারী', 'value': '150'},
        {'label': '৪র্থ শ্রেণির কর্মচারী', 'value': '110'},
    ],
    '6': [
        {'label': 'প্রতি পরীক্ষার্থী', 'value': '50'},
    ],
    '7': [
        {'label': 'সুপারভিশন ও রিপোর্ট পরীক্ষণ (প্রতি পরীক্ষার্থী)', 'value': '100'},
    ],
    '8': [
        {'label': 'প্রতি উত্তরপত্র', 'value': '8'},
    ],
    '9': [
        {'label': 'কোর্স ভিত্তিক (প্রতি কোর্স)', 'value': '200'},
        {'label': 'পরীক্ষার্থী ভিত্তিক (প্রতি পরীক্ষার্থী)', 'value': '40'},
    ],
    '9a': [
        {'label': 'কোর্স ভিত্তিক (প্রতি কোর্স)', 'value': '200'},
    ],
    '9b': [
        {'label': 'পরীক্ষার্থী ভিত্তিক (প্রতি পরীক্ষার্থী)', 'value': '40'},
    ],
    '10': [
        {'label': 'অংকনসহ অন্যান্য কাজ (প্রতি প্রশ্নপত্র)', 'value': '250'},
        {'label': 'ফটোকপি (প্রতি প্রশ্নপত্র)', 'value': '7'},
    ],
    '10a': [
        {'label': 'অংকনসহ অন্যান্য কাজ (প্রতি প্রশ্নপত্র)', 'value': '250'},
    ],
    '10b': [
        {'label': 'ফটোকপি (প্রতি প্রশ্নপত্র)', 'value': '7'},
    ],
    '11': [
        {'label': 'স্নাতক - সভাপতি (প্রতি টার্ম)', 'value': '2500'},
        {'label': 'স্নাতক - সদস্য (প্রতি টার্ম)', 'value': '1000'},
        {'label': 'স্নাতকোত্তর - সভাপতি (প্রতি টার্ম)', 'value': '3000'},
        {'label': 'স্নাতকোত্তর - সদস্য (প্রতি টার্ম)', 'value': '1000'},
    ],
    '12': [
        {'label': 'প্রধান তদারকী (প্রতি ঘন্টা)', 'value': '600'},
        {'label': 'অন্যান্য তদারকী (প্রতি ঘন্টা)', 'value': '500'},
    ],
    '12a': [
        {'label': 'চীফ ইনভিজিলেশন', 'value': '1800'},
    ],
    '12b': [
        {'label': 'ইনভিজিলেশন', 'value': '1500'},
    ],
    '13': [
        {'label': 'স্নাতক - থিসিস/প্রজেক্ট মূল্যায়ন (প্রতি পরীক্ষার্থী)', 'value': '1200'},
        {'label': 'স্নাতকোত্তর - ডিজারটেশন মূল্যায়ন (প্রতি পরীক্ষার্থী)', 'value': '2500'},
        {'label': 'পিএইচডি - ডিজারটেশন মূল্যায়ন (প্রতি পরীক্ষার্থী)', 'value': '10000'},
    ],
    '13a': [
        {'label': 'স্নাতক - থিসিস/প্রজেক্ট মূল্যায়ন (প্রতি পরীক্ষার্থী)', 'value': '1200'},
        {'label': 'স্নাতকোত্তর - ডিজারটেশন মূল্যায়ন (প্রতি পরীক্ষার্থী)', 'value': '2500'},
        {'label': 'পিএইচডি - ডিজারটেশন মূল্যায়ন (প্রতি পরীক্ষার্থী)', 'value': '10000'},
    ],
    '13b': [
        {'label': 'স্নাতক - থিসিস/প্রজেক্ট সুপারভিশন (প্রতি পরীক্ষার্থী)', 'value': '2000'},
        {'label': 'স্নাতকোত্তর - ডিজারটেশন সুপারভিশন (প্রতি পরীক্ষার্থী)', 'value': '5000'},
        {'label': 'স্নাতকোত্তর - প্রজেক্ট সুপারভিশন (প্রতি পরীক্ষার্থী)', 'value': '2500'},
        {'label': 'পিএইচডি - ডিজারটেশন সুপারভিশন (প্রতি পরীক্ষার্থী)', 'value': '35000'},
    ],
    '13c': [
        {'label': 'স্নাতকোত্তর - কো-সুপারভিশন (প্রতি পরীক্ষার্থী)', 'value': '1500'},
        {'label': 'পিএইচডি - কো-সুপারভিশন (প্রতি পরীক্ষার্থী)', 'value': '15000'},
    ],
    '13d': [
        {'label': 'স্নাতক - ফাইনাল ডিফেন্স/মৌখিক (প্রতি পরীক্ষার্থী)', 'value': '120'},
        {'label': 'স্নাতকোত্তর - ফাইনাল ডিফেন্স/মৌখিক (প্রতি পরীক্ষার্থী)', 'value': '500'},
        {'label': 'পিএইচডি - ফাইনাল ডিফেন্স/মৌখিক (প্রতি পরীক্ষার্থী)', 'value': '2000'},
    ],
    '14': [
        {'label': 'পরীক্ষার্থী প্রতি ৫০টাকা', 'value': '50'},
    ],
    '15': [
        {'label': 'পরীক্ষার্থী প্রতি', 'value': '30'},
    ],
    '16': [
        {'label': 'প্রতি খাতা', 'value': '30'},
    ],
}

RATE_GROUP_TITLES: dict[str, str] = {
    '1': '১. প্রশ্নপত্র প্রণয়ন',
    '2': '২. প্রশ্নপত্র মডারেশন',
    '3': '৩. উত্তরপত্র পরীক্ষণ',
    '4': '৪. ক্লাস টেস্ট / টার্ম পেপার / হোম ওয়ার্ক / এ্যাসাইনমেন্ট',
    '5': '৫. সেশনাল',
    '6': '৬. সেশনাল মৌখিক পরীক্ষা',
    '7': '৭. প্রফেশনাল এ্যাটাসমেন্ট / ইন্ডাস্ট্রিয়াল',
    '8': '৮. উত্তরপত্র নিরীক্ষণ',
    '9': '৯. টেবুলেশন',
    '9a': '৯ক. টেবুলেশন — কোর্স ভিত্তিক',
    '9b': '৯খ. টেবুলেশন — পরীক্ষার্থী ভিত্তিক',
    '10': '১০. প্রশ্নপত্র প্রস্তুতকরণ',
    '10a': '১০ক. প্রশ্নপত্র প্রস্তুতকরণ — অংকন',
    '10b': '১০খ. প্রশ্নপত্র প্রস্তুতকরণ — ফটোকপি',
    '11': '১১. পরীক্ষা কমিটির সভাপতি / সদস্য',
    '12': '১২. চীফ ইনভিজিলেশন / ইনভিজিলেশন',
    '12a': '১২ক. চীফ ইনভিজিলেশন',
    '12b': '১২খ. ইনভিজিলেশন',
    '13': '১৩. থিসিস',
    '13a': '১৩ক. থিসিস — পরীক্ষণ',
    '13b': '১৩খ. থিসিস — সুপারভিশন',
    '13c': '১৩গ. থিসিস — কো-সুপারভিশন',
    '13d': '১৩ঘ. থিসিস — মৌখিক পরীক্ষা',
    '14': '১৪. ভাইভা',
    '15': '১৫. কোডিং / ডিকোডিং',
    '16': '১৬. অন্যান্য',
}

GROUP_ORDER: tuple[str, ...] = tuple(DEFAULT_RATES.keys())

_CACHE: Optional[dict] = None


def _tenant_code() -> str:
    try:
        from utils.tenant import current_tenant
        return current_tenant().code
    except Exception:
        return 'law'


def _instance_override_path() -> Path:
    code = _tenant_code()
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            return Path(current_app.instance_path) / f'remuneration_rates_{code}.yaml'
    except Exception:
        pass
    from utils.tenant import PACKAGE_ROOT
    return PACKAGE_ROOT / 'instance' / f'remuneration_rates_{code}.yaml'


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding='utf-8') as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def _normalize_rate_list(items: Any, fallback: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get('label') or '').strip()
        value = str(item.get('value') if item.get('value') is not None else '').strip()
        if not label:
            continue
        rows.append({'label': label, 'value': value})
    return rows or deepcopy(fallback)


def _normalize(raw: dict) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for key in GROUP_ORDER:
        fallback = DEFAULT_RATES[key]
        overlay = raw.get(key, raw.get(int(key) if key.isdigit() else key))
        if overlay is None:
            out[key] = deepcopy(fallback)
        else:
            out[key] = _normalize_rate_list(overlay, fallback)
    return out


def default_rates() -> dict[str, list[dict[str, str]]]:
    return deepcopy(DEFAULT_RATES)


def reset_remuneration_rates_cache() -> None:
    global _CACHE
    _CACHE = None


def load_remuneration_rates() -> dict[str, list[dict[str, str]]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    merged = default_rates()
    override = _read_yaml(_instance_override_path())
    if override:
        merged = _normalize({**merged, **{str(k): v for k, v in override.items()}})
    _CACHE = merged
    return merged


def save_remuneration_rates(data: dict) -> Path:
    path = _instance_override_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize(data)
    with path.open('w', encoding='utf-8') as fh:
        yaml.safe_dump(normalized, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    reset_remuneration_rates_cache()
    return path


def clear_instance_override() -> None:
    path = _instance_override_path()
    if path.is_file():
        path.unlink()
    reset_remuneration_rates_cache()


def instance_override_exists() -> bool:
    return _instance_override_path().is_file()


def rate_groups_for_admin() -> list[dict]:
    rates = load_remuneration_rates()
    return [
        {
            'key': key,
            'title': RATE_GROUP_TITLES.get(key, key),
            'rates': rates.get(key, []),
        }
        for key in GROUP_ORDER
    ]
