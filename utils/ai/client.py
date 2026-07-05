"""Multi-provider AI client for JSON outline generation."""
import json
import ssl
import time
import urllib.error
import urllib.request

from flask import current_app

from utils.ai.encryption import decrypt_api_key
from utils.ai.models import AIProviderSetting


class AIClientError(Exception):
    pass


def _ssl_context():
    """Use certifi CA bundle (fixes macOS python.org SSL verify failures)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _clean_optional_url(url):
    """Treat empty, None, or literal 'None' as unset."""
    if url is None:
        return None
    cleaned = str(url).strip()
    if not cleaned or cleaned.lower() in ('none', 'null', 'undefined', 'n/a'):
        return None
    return cleaned.rstrip('/')


def _friendly_api_error(status_code, detail, provider=None):
    """Turn provider JSON errors into short Bengali messages for admins."""
    message = ''
    try:
        payload = json.loads(detail)
        err = payload.get('error') or {}
        if isinstance(err, dict):
            message = (err.get('message') or '').strip()
    except (json.JSONDecodeError, TypeError, AttributeError):
        message = (detail or '').strip()[:300]

    lowered = message.lower()
    provider = (provider or '').strip().lower()

    if status_code == 429 or 'resource_exhausted' in lowered:
        if provider == 'gemini' and ('prepayment' in lowered or 'aistudio' in lowered):
            return (
                'Google AI-এর প্রিপেইড ক্রেডিট শেষ। '
                'aistudio.google.com → Billing থেকে ক্রেডিট যোগ করুন।'
            )
        if provider == 'openai' and ('quota' in lowered or 'billing' in lowered):
            return (
                'OpenAI-এর কোটা শেষ বা বিলিং সেটআপ প্রয়োজন। '
                'platform.openai.com/account/billing চেক করুন।'
            )
        if message:
            return message[:400]
        return 'API ব্যবহারের সীমা পূর্ণ। কিছুক্ষণ পর আবার চেষ্টা করুন।'

    if status_code in (401, 403) or 'api key not valid' in lowered or 'invalid api key' in lowered:
        key_sources = {
            'gemini': 'Google AI Studio',
            'openai': 'OpenAI Platform',
            'anthropic': 'Anthropic Console',
            'deepseek': 'DeepSeek Platform',
        }
        source = key_sources.get(provider, 'নির্বাচিত সেবার ওয়েবসাইট')
        return f'API key সঠিক নয়। {source} থেকে নতুন key কপি করে পেস্ট করুন।'

    if status_code == 404 or 'not found' in lowered:
        if provider == 'anthropic':
            return (
                'Claude মডেল পাওয়া যায়নি। ড্রপডাউন থেকে '
                'Claude Sonnet 4.6 বেছে নিয়ে আবার পরীক্ষা করুন।'
            )
        return 'মডেল পাওয়া যায়নি। নির্বাচিত সেবার জন্য ড্রপডাউন থেকে সঠিক মডেল বেছে নিন।'

    if message:
        return message[:400]
    return f'AI API ত্রুটি (HTTP {status_code})।'


def _http_post_json(url, headers, body, timeout=120, provider=None):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    context = _ssl_context() if str(url).lower().startswith('https://') else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise AIClientError(_friendly_api_error(exc.code, detail, provider=provider)) from exc
    except urllib.error.URLError as exc:
        reason = str(exc.reason) if exc.reason else str(exc)
        if 'CERTIFICATE_VERIFY_FAILED' in reason:
            raise AIClientError(
                'SSL সার্টিফিকেট যাচাই ব্যর্থ। macOS-এ Python Certificates ইনস্টল করুন, '
                'অথবা pip install certifi চালিয়ে অ্যাপ রিস্টার্ট করুন।'
            ) from exc
        raise AIClientError(f'AI API connection error: {exc}') from exc


def get_active_provider_setting():
    from utils.ai.provider_presets import normalize_model_for_provider

    setting = AIProviderSetting.get_active_default()
    if not setting:
        raise AIClientError(
            'AI provider সংরক্ষণ করা হয়নি। Admin → AI Settings থেকে API key দিয়ে '
            'সংযোগ পরীক্ষা করার পর অবশ্যই **সংরক্ষণ করুন**।'
        )
    api_key = decrypt_api_key(setting.api_key_encrypted)
    if not api_key:
        raise AIClientError('Stored API key could not be decrypted. Re-save it in Admin → AI Settings.')
    return {
        'provider': setting.provider,
        'api_key': (api_key or '').strip(),
        'model_name': normalize_model_for_provider(
            setting.provider,
            (setting.model_name or AIProviderSetting.default_model_for_provider(setting.provider) or '').strip(),
        ),
        'api_base_url': _clean_optional_url(setting.api_base_url),
        'temperature': setting.temperature if setting.temperature is not None else 0.3,
        'max_tokens': setting.max_tokens or 8000,
    }


def _normalize_usage(usage):
    if not usage or not isinstance(usage, dict):
        return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    prompt = int(usage.get('prompt_tokens') or usage.get('input_tokens') or 0)
    completion = int(usage.get('completion_tokens') or usage.get('output_tokens') or 0)
    total = int(usage.get('total_tokens') or (prompt + completion))
    return {'prompt_tokens': prompt, 'completion_tokens': completion, 'total_tokens': total}


def _extract_text_openai_compatible(response):
    choices = response.get('choices') or []
    if not choices:
        raise AIClientError('AI response missing choices')
    message = choices[0].get('message') or {}
    content = message.get('content')
    if isinstance(content, list):
        parts = [p.get('text', '') for p in content if isinstance(p, dict)]
        content = '\n'.join(parts)
    if not content:
        raise AIClientError('AI response missing content')
    usage = _normalize_usage(response.get('usage'))
    return content, usage


def _call_openai(cfg, system_prompt, user_prompt, timeout=120):
    base = _clean_optional_url(cfg.get('api_base_url')) or 'https://api.openai.com/v1'
    url = f'{base}/chat/completions'
    body = {
        'model': cfg['model_name'],
        'temperature': cfg['temperature'],
        'max_tokens': cfg['max_tokens'],
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'response_format': {'type': 'json_object'},
    }
    headers = {
        'Authorization': f'Bearer {cfg["api_key"]}',
        'Content-Type': 'application/json',
    }
    return _extract_text_openai_compatible(_http_post_json(url, headers, body, timeout=timeout, provider=cfg.get('provider', 'openai')))


def _normalize_gemini_model(model_name):
    """Map friendly/erroneous names to valid Gemini model ids."""
    raw = (model_name or '').strip()
    if not raw:
        return 'gemini-1.5-flash'
    # Strip an accidental "models/" prefix; the URL adds it.
    if raw.lower().startswith('models/'):
        raw = raw[len('models/'):]
    lowered = raw.lower().replace(' ', '-')
    # Common friendly typos → valid ids.
    aliases = {
        'flash': 'gemini-1.5-flash',
        'flash-3.5': 'gemini-2.0-flash',
        'flash-2.0': 'gemini-2.0-flash',
        'flash-1.5': 'gemini-1.5-flash',
        'pro': 'gemini-1.5-pro',
        'gemini-flash': 'gemini-1.5-flash',
        'gemini-pro': 'gemini-1.5-pro',
    }
    if lowered in aliases:
        return aliases[lowered]
    if not lowered.startswith('gemini'):
        return 'gemini-1.5-flash'
    return lowered


def _call_gemini(cfg, system_prompt, user_prompt, timeout=120):
    model = _normalize_gemini_model(cfg['model_name'])
    base = _clean_optional_url(cfg.get('api_base_url')) or 'https://generativelanguage.googleapis.com/v1beta'
    url = f'{base}/models/{model}:generateContent?key={cfg["api_key"].strip()}'
    body = {
        'systemInstruction': {'parts': [{'text': system_prompt}]},
        'contents': [{'role': 'user', 'parts': [{'text': user_prompt}]}],
        'generationConfig': {
            'temperature': cfg['temperature'],
            'maxOutputTokens': cfg['max_tokens'],
            'responseMimeType': 'application/json',
        },
    }
    headers = {'Content-Type': 'application/json'}
    response = _http_post_json(url, headers, body, timeout=timeout, provider='gemini')
    candidates = response.get('candidates') or []
    if not candidates:
        raise AIClientError('Gemini response missing candidates')
    parts = candidates[0].get('content', {}).get('parts', [])
    text = '\n'.join(p.get('text', '') for p in parts if isinstance(p, dict))
    if not text:
        raise AIClientError('Gemini response missing text')
    usage = _normalize_usage(response.get('usageMetadata') or {})
    return text, usage


def _call_anthropic(cfg, system_prompt, user_prompt, timeout=120):
    from utils.ai.provider_presets import normalize_model_for_provider

    model = normalize_model_for_provider('anthropic', cfg.get('model_name'))
    base = _clean_optional_url(cfg.get('api_base_url')) or 'https://api.anthropic.com/v1'
    url = f'{base}/messages'
    body = {
        'model': model,
        'max_tokens': cfg['max_tokens'],
        'temperature': cfg['temperature'],
        'system': system_prompt,
        'messages': [{'role': 'user', 'content': user_prompt}],
    }
    headers = {
        'x-api-key': cfg['api_key'],
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
    }
    response = _http_post_json(url, headers, body, timeout=timeout, provider='anthropic')
    content = response.get('content') or []
    text = '\n'.join(block.get('text', '') for block in content if block.get('type') == 'text')
    if not text:
        raise AIClientError('Anthropic response missing text')
    usage = _normalize_usage(response.get('usage') or {})
    return text, usage


def generate_outline_json_with_meta(system_prompt, user_prompt):
    """Call AI and return text plus provider/model/token usage."""
    cfg = get_active_provider_setting()
    provider = cfg['provider']
    started = time.monotonic()

    if provider in (AIProviderSetting.PROVIDER_OPENAI, AIProviderSetting.PROVIDER_DEEPSEEK):
        if provider == AIProviderSetting.PROVIDER_DEEPSEEK and not cfg.get('api_base_url'):
            cfg = dict(cfg)
            cfg['api_base_url'] = 'https://api.deepseek.com/v1'
        text, usage = _call_openai(cfg, system_prompt, user_prompt)
    elif provider == AIProviderSetting.PROVIDER_GEMINI:
        text, usage = _call_gemini(cfg, system_prompt, user_prompt)
    elif provider == AIProviderSetting.PROVIDER_ANTHROPIC:
        text, usage = _call_anthropic(cfg, system_prompt, user_prompt)
    else:
        raise AIClientError(f'Unsupported AI provider: {provider}')

    duration_ms = int((time.monotonic() - started) * 1000)
    return {
        'text': text,
        'provider': provider,
        'model_name': cfg['model_name'],
        'usage': usage,
        'duration_ms': duration_ms,
    }


def generate_outline_json(system_prompt, user_prompt):
    return generate_outline_json_with_meta(system_prompt, user_prompt)['text']


def test_provider_connection(provider, api_key, model_name=None, api_base_url=None):
    """Quick connectivity test for admin setup (returns success message or raises AIClientError)."""
    from utils.ai.provider_presets import normalize_model_for_provider

    provider = (provider or '').strip().lower()
    api_key = (api_key or '').strip()
    if not api_key:
        raise AIClientError('API key খালি আছে। নির্বাচিত সেবার ওয়েবসাইট থেকে key কপি করে পেস্ট করুন।')

    cfg = {
        'provider': provider,
        'api_key': api_key,
        'model_name': normalize_model_for_provider(provider, model_name),
        'api_base_url': _clean_optional_url(api_base_url),
        'temperature': 0.3,
        'max_tokens': 256,
    }

    system_prompt = 'You are a helpful assistant.'
    user_prompt = 'Reply with exactly this JSON: {"status":"ok"}'

    if provider in ('openai', 'deepseek'):
        if provider == 'deepseek' and not cfg.get('api_base_url'):
            cfg = dict(cfg)
            cfg['api_base_url'] = 'https://api.deepseek.com/v1'
        text, _usage = _call_openai(cfg, system_prompt, user_prompt, timeout=20)
    elif provider == 'gemini':
        text, _usage = _call_gemini(cfg, system_prompt, user_prompt, timeout=20)
    elif provider == 'anthropic':
        text, _usage = _call_anthropic(cfg, system_prompt, user_prompt, timeout=20)
    else:
        raise AIClientError(f'অজানা provider: {provider}')

    if not text:
        raise AIClientError('AI থেকে কোনো উত্তর আসেনি।')
    return f'সংযোগ সফল! সেবা: {provider}, মডেল: {cfg["model_name"]}'
