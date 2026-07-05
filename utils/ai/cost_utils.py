"""Rough token cost estimates for AI outline generation logging."""

# USD per 1M tokens (input, output) — approximate; update as pricing changes.
MODEL_PRICING = {
    'gpt-4o-mini': (0.15, 0.60),
    'gpt-4o': (2.50, 10.00),
    'claude-sonnet-4-6': (3.00, 15.00),
    'claude-haiku-4-5-20251001': (1.00, 5.00),
    'claude-opus-4-8': (5.00, 25.00),
    'claude-sonnet-4-5-20250929': (3.00, 15.00),
    'claude-3-5-sonnet-20241022': (3.00, 15.00),
    'claude-3-haiku-20240307': (0.25, 1.25),
    'gemini-1.5-flash': (0.075, 0.30),
    'gemini-1.5-pro': (1.25, 5.00),
    'deepseek-chat': (0.14, 0.28),
}


def estimate_cost_usd(model_name, prompt_tokens, completion_tokens):
    """Return estimated USD cost or None if model unknown."""
    if not model_name:
        return None
    prompt_tokens = int(prompt_tokens or 0)
    completion_tokens = int(completion_tokens or 0)
    if prompt_tokens == 0 and completion_tokens == 0:
        return None

    key = model_name.lower()
    rates = MODEL_PRICING.get(key)
    if not rates:
        for known, price in MODEL_PRICING.items():
            if known in key:
                rates = price
                break
    if not rates:
        return None

    input_rate, output_rate = rates
    return round(
        (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000,
        6,
    )
