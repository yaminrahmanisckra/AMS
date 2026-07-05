"""User-friendly AI provider presets for non-technical admin setup."""

PROVIDER_PRESETS = {
    'gemini': {
        'label': 'Google Gemini',
        'label_bn': 'গুগল জেমিনি (সহজ ও সাশ্রয়ী)',
        'recommended': True,
        'key_url': 'https://aistudio.google.com/apikey',
        'key_steps_bn': [
            'লিংকে ক্লিক করুন → Google AI Studio খুলবে',
            '"Create API Key" বাটনে ক্লিক করুন',
            'যে key তৈরি হবে সেটা কপি করে নিচের বক্সে পেস্ট করুন',
        ],
        'models': [
            ('gemini-2.0-flash', 'Gemini 2.0 Flash — দ্রুত (সুপারিশকৃত)'),
            ('gemini-1.5-flash', 'Gemini 1.5 Flash — দ্রুত'),
            ('gemini-1.5-pro', 'Gemini 1.5 Pro — উন্নত মান'),
        ],
        'default_model': 'gemini-2.0-flash',
    },
    'openai': {
        'label': 'OpenAI (ChatGPT)',
        'label_bn': 'OpenAI / ChatGPT',
        'recommended': False,
        'key_url': 'https://platform.openai.com/api-keys',
        'key_steps_bn': [
            'OpenAI অ্যাকাউন্টে লগইন করুন',
            '"Create new secret key" ক্লিক করুন',
            'key কপি করে নিচে পেস্ট করুন',
        ],
        'models': [
            ('gpt-4o-mini', 'GPT-4o Mini — সাশ্রয়ী (সুপারিশকৃত)'),
            ('gpt-4o', 'GPT-4o — উন্নত মান'),
        ],
        'default_model': 'gpt-4o-mini',
    },
    'anthropic': {
        'label': 'Anthropic Claude',
        'label_bn': 'Anthropic Claude',
        'recommended': False,
        'key_url': 'https://console.anthropic.com/settings/keys',
        'key_steps_bn': [
            'Anthropic Console-এ লগইন করুন',
            'API Keys থেকে নতুন key তৈরি করুন',
            'key কপি করে নিচে পেস্ট করুন',
        ],
        'models': [
            ('claude-sonnet-4-6', 'Claude Sonnet 4.6 — সুপারিশকৃত'),
            ('claude-haiku-4-5-20251001', 'Claude Haiku 4.5 — দ্রুত ও সাশ্রয়ী'),
            ('claude-opus-4-8', 'Claude Opus 4.8 — সর্বোচ্চ মান'),
            ('claude-sonnet-4-5-20250929', 'Claude Sonnet 4.5'),
        ],
        'default_model': 'claude-sonnet-4-6',
    },
    'deepseek': {
        'label': 'DeepSeek',
        'label_bn': 'DeepSeek',
        'recommended': False,
        'key_url': 'https://platform.deepseek.com/api_keys',
        'key_steps_bn': [
            'DeepSeek প্ল্যাটফর্মে লগইন করুন',
            'API Keys থেকে key তৈরি করুন',
            'key কপি করে নিচে পেস্ট করুন',
        ],
        'models': [
            ('deepseek-chat', 'DeepSeek Chat (সুপারিশকৃত)'),
        ],
        'default_model': 'deepseek-chat',
    },
}


# Retired Anthropic ids → current API ids (for saved settings / old drafts).
ANTHROPIC_LEGACY_MODEL_MAP = {
    'claude-3-5-sonnet-20241022': 'claude-sonnet-4-6',
    'claude-3-5-sonnet-latest': 'claude-sonnet-4-6',
    'claude-3-5-haiku-20241022': 'claude-haiku-4-5-20251001',
    'claude-3-haiku-20240307': 'claude-haiku-4-5-20251001',
    'claude-3-opus-20240229': 'claude-opus-4-8',
}


def get_preset(provider):
    return PROVIDER_PRESETS.get((provider or '').strip().lower())


def default_model_for(provider):
    preset = get_preset(provider)
    if preset:
        return preset['default_model']
    return 'gpt-4o-mini'


def normalize_model_for_provider(provider, model_name):
    """Ensure model id matches the selected provider (avoids gemini model + openai key)."""
    provider = (provider or '').strip().lower()
    model = (model_name or '').strip()
    if provider == 'anthropic' and model in ANTHROPIC_LEGACY_MODEL_MAP:
        model = ANTHROPIC_LEGACY_MODEL_MAP[model]
    preset = get_preset(provider)
    if not preset:
        return default_model_for(provider)
    valid = {m[0] for m in preset.get('models', [])}
    if model in valid:
        return model
    return preset['default_model']


def choices_for_template():
    return [
        (key, preset['label_bn'], preset.get('recommended', False))
        for key, preset in PROVIDER_PRESETS.items()
    ]
