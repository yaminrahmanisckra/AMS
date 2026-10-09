"""Wrap pasted and AI-style spans so teachers can review them on screen and in PDF."""
from __future__ import annotations

import html
import re

from markupsafe import Markup, escape

HL_PASTE = 'hl-paste'
HL_AI = 'hl-ai'
HL_PASTE_BLOCK = 'hl-paste-block'
HL_AI_BLOCK = 'hl-ai-block'

# Inline styles so WeasyPrint paints the highlight even when CSS backgrounds
# on <mark> are dropped. Border remains if fill is still skipped.
HL_INLINE_STYLE = {
    HL_PASTE: (
        'background-color:#ffd54f;border-bottom:2.5pt solid #d97706;'
        'padding:0 1pt;print-color-adjust:exact;-webkit-print-color-adjust:exact'
    ),
    HL_AI: (
        'background-color:#f9a8d4;border-bottom:2.5pt solid #be185d;'
        'padding:0 1pt;print-color-adjust:exact;-webkit-print-color-adjust:exact'
    ),
}

PDF_HIGHLIGHT_CSS = """
mark.hl-paste, span.hl-paste, p.hl-paste, li.hl-paste, td.hl-paste, .hl-paste {
  background-color: #ffd54f !important;
  border-bottom: 2.5pt solid #d97706;
  padding: 0 1pt;
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}
mark.hl-ai, span.hl-ai, p.hl-ai, li.hl-ai, td.hl-ai, .hl-ai {
  background-color: #f9a8d4 !important;
  border-bottom: 2.5pt solid #be185d;
  padding: 0 1pt;
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}
.hl-paste-block, div.hl-paste-block, .body.hl-paste-block {
  background-color: #fff3bf !important;
  border-left: 5pt solid #d97706;
  padding: 4pt 8pt;
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}
.hl-ai-block, div.hl-ai-block, .body.hl-ai-block {
  background-color: #fce7f3 !important;
  border-left: 5pt solid #be185d;
  padding: 4pt 8pt;
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}
.legend .hl-paste, .legend .hl-ai { border-bottom: 2.5pt solid transparent; }
"""

_BLOCK_BREAK = re.compile(
    r'</?(?:p|div|li|tr|td|th|table|thead|tbody|h[1-6]|blockquote|ul|ol|section|article|br)\b',
    re.I,
)
_BLOCK_TAG = re.compile(
    r'(<(p|li|td|th|blockquote)\b)([^>]*)(>)(.*?)(</\2>)',
    re.I | re.S,
)

_MIN_SNIPPET = 16
_MAX_SNIPPET = 4000
_MAX_STORED = 40


def normalize_space(text):
    return re.sub(r'\s+', ' ', (text or '').replace('\xa0', ' ')).strip()


def clip_snippet(text, max_len=_MAX_SNIPPET):
    raw = (text or '').strip()
    if len(raw) > max_len:
        return raw[:max_len]
    return raw


def parse_snippet_list(raw, cap=12):
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out = []
    seen = set()
    for item in raw[: max(1, cap)]:
        if not isinstance(item, str):
            continue
        clipped = clip_snippet(item)
        key = normalize_space(clipped)
        if len(key) < _MIN_SNIPPET or key in seen:
            continue
        seen.add(key)
        out.append(clipped)
    return out


def remember_paste_snippets(meta, snippets, cap=_MAX_STORED):
    meta = meta if isinstance(meta, dict) else {}
    stored = meta.get('paste_snippets')
    if not isinstance(stored, list):
        stored = []
    seen = {normalize_space(item) for item in stored if isinstance(item, str)}
    for item in parse_snippet_list(snippets, cap=cap):
        key = normalize_space(item)
        if key in seen:
            continue
        stored.append(item)
        seen.add(key)
    meta['paste_snippets'] = stored[-cap:]
    return meta


def collect_ai_snippets(text):
    """Paragraphs or sentences that trip the AI-style heuristic."""
    from blueprints.class_management.models import estimate_socrates_ai_style

    body = (text or '').strip()
    if len(body) < 90:
        return []
    chunks = [part.strip() for part in re.split(r'\n{2,}', body) if part.strip()]
    sentences = [
        part.strip()
        for part in re.split(r'(?<=[.!?।])\s+', body)
        if len(part.strip()) >= 40
    ]
    candidates = chunks if len(chunks) > 1 else sentences
    snippets = []
    seen = set()
    for chunk in candidates:
        if len(chunk) < 40:
            continue
        if not estimate_socrates_ai_style(chunk).get('flag'):
            continue
        key = normalize_space(chunk)
        if key in seen:
            continue
        seen.add(key)
        snippets.append(clip_snippet(chunk, 2000))
    if not snippets and estimate_socrates_ai_style(body).get('flag'):
        snippets.append(clip_snippet(body, 2000))
    return snippets[:20]


def _plain_map(html_text):
    """Collapsed-whitespace plaintext plus (start, end) spans in the original HTML."""
    plain = []
    spans = []
    i = 0
    n = len(html_text)
    last_space = True
    while i < n:
        ch = html_text[i]
        if ch == '<':
            j = html_text.find('>', i)
            if j < 0:
                break
            i = j + 1
            continue
        if ch == '&':
            j = html_text.find(';', i)
            if 0 < j - i <= 12:
                decoded = html.unescape(html_text[i:j + 1])
                span = (i, j + 1)
                for dch in decoded:
                    if dch.isspace():
                        if not last_space and plain:
                            plain.append(' ')
                            spans.append(span)
                            last_space = True
                    else:
                        plain.append(dch)
                        spans.append(span)
                        last_space = False
                i = j + 1
                continue
        if ch.isspace():
            if not last_space and plain:
                plain.append(' ')
                spans.append((i, i + 1))
                last_space = True
            i += 1
            continue
        plain.append(ch)
        spans.append((i, i + 1))
        last_space = False
        i += 1
    return ''.join(plain), spans


def _inside_mark(html_text, start):
    open_at = html_text.rfind('<mark', 0, start)
    close_at = html_text.rfind('</mark>', 0, start)
    return open_at > close_at


def _open_highlight(css_class):
    style = HL_INLINE_STYLE.get(css_class, '')
    style_attr = f' style="{style}"' if style else ''
    return f'<mark class="{css_class}"{style_attr}>'


def _wrap_once(html_text, snippet, css_class):
    needle = normalize_space(snippet)
    if len(needle) < _MIN_SNIPPET:
        return html_text, False
    hay, spans = _plain_map(html_text)
    pos = hay.find(needle)
    used_len = len(needle)
    if pos < 0:
        short = needle[:80]
        if len(short) < _MIN_SNIPPET:
            return html_text, False
        pos = hay.find(short)
        used_len = len(short)
    last = pos + used_len - 1
    if pos < 0 or last >= len(spans):
        return html_text, False
    start = spans[pos][0]
    end = spans[last][1]
    if _inside_mark(html_text, start):
        return html_text, False
    chunk = html_text[start:end]
    if _BLOCK_BREAK.search(chunk):
        return html_text, False
    wrapped = (
        f'{html_text[:start]}{_open_highlight(css_class)}'
        f'{chunk}</mark>{html_text[end:]}'
    )
    return wrapped, True


def _snippet_covers_block(plain, snippets):
    """True when a snippet is the paragraph, or most of it (safe to fill the block)."""
    if not plain:
        return False
    for item in snippets or []:
        if not isinstance(item, str):
            continue
        key = normalize_space(item)
        if len(key) < _MIN_SNIPPET:
            continue
        if key == plain or (len(plain) >= 40 and plain in key):
            return True
        if key in plain and len(key) >= max(40, int(len(plain) * 0.6)):
            return True
    return False


def tag_matching_blocks(html_text, paste_snippets=None, ai_snippets=None):
    """Add highlight classes to block tags WeasyPrint can fill (p/li/td)."""

    def repl(match):
        prefix, name, attrs, gt, inner, close = match.groups()
        lower_attrs = attrs.lower()
        if 'hl-paste' in lower_attrs or 'hl-ai' in lower_attrs:
            return match.group(0)
        plain = normalize_space(re.sub(r'<[^>]+>', ' ', inner))
        css_class = None
        if _snippet_covers_block(plain, paste_snippets):
            css_class = HL_PASTE
        elif _snippet_covers_block(plain, ai_snippets):
            css_class = HL_AI
        if not css_class:
            return match.group(0)
        style = HL_INLINE_STYLE.get(css_class, '')
        if re.search(r'\bclass="', attrs, re.I):
            attrs = re.sub(r'\bclass="', f'class="{css_class} ', attrs, count=1, flags=re.I)
        else:
            attrs = f'{attrs} class="{css_class}"'
        if style and 'style=' not in attrs.lower():
            attrs = f'{attrs} style="{style}"'
        return f'{prefix}{attrs}{gt}{inner}{close}'

    return _BLOCK_TAG.sub(repl, html_text or '')


def wrap_snippets(html_text, snippets, css_class, limit=30):
    html_text = html_text or ''
    unique = {}
    for item in snippets or []:
        if not isinstance(item, str):
            continue
        key = normalize_space(item)
        if len(key) >= _MIN_SNIPPET:
            unique[key] = item
    ordered = sorted(unique.values(), key=lambda item: len(normalize_space(item)), reverse=True)
    applied = 0
    for snippet in ordered:
        if applied >= limit:
            break
        html_text, ok = _wrap_once(html_text, snippet, css_class)
        if ok:
            applied += 1
    return html_text


def highlight_integrity_html(html_text, *, paste_snippets=None, ai_snippets=None):
    marked = wrap_snippets(html_text or '', paste_snippets, HL_PASTE)
    marked = wrap_snippets(marked, ai_snippets, HL_AI)
    return tag_matching_blocks(marked, paste_snippets, ai_snippets)


def highlight_integrity_plain(
    text,
    *,
    paste_snippets=None,
    ai_snippets=None,
    whole_paste=False,
    whole_ai=False,
):
    marked = highlight_integrity_html(
        str(escape(text or '')),
        paste_snippets=paste_snippets,
        ai_snippets=ai_snippets,
    )
    if whole_paste and f'class="{HL_PASTE}"' not in marked:
        marked = f'<span class="{HL_PASTE}" style="{HL_INLINE_STYLE[HL_PASTE]}">{marked}</span>'
    elif whole_ai and f'class="{HL_AI}"' not in marked:
        marked = f'<span class="{HL_AI}" style="{HL_INLINE_STYLE[HL_AI]}">{marked}</span>'
    return Markup(marked)


def block_classes(*, pasted=False, ai=False):
    classes = []
    if pasted:
        classes.append(HL_PASTE_BLOCK)
    if ai:
        classes.append(HL_AI_BLOCK)
    return ' '.join(classes)
