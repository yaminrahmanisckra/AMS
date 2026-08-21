"""Rich-text helpers for course-outline Part D (textbooks, references, etc.)."""
import json
import re
from html.parser import HTMLParser
from html import unescape

from markupsafe import Markup, escape

_ALLOWED = {
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li',
    'a', 'h2', 'h3', 'h4', 'span', 'div', 'blockquote', 'sup', 'sub',
}
_VOID = {'br'}
_STYLE_SAFE = re.compile(
    r'^(?:\s*(?:color|background-color|font-size|font-weight|font-style|text-decoration|text-align)\s*:\s*[^;]+;?\s*)+$',
    re.I,
)


class _HtmlSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._out = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        tag = (tag or '').lower()
        if tag not in _ALLOWED:
            if tag not in _VOID:
                self._skip += 1
            return
        if self._skip:
            return
        safe = []
        for name, value in attrs:
            name = (name or '').lower()
            value = value or ''
            if name.startswith('on') or 'javascript:' in value.lower():
                continue
            if tag == 'a' and name == 'href':
                href = value.strip()
                if href.startswith(('http://', 'https://', 'mailto:', '/', '#')):
                    safe.append(('href', href))
                    safe.append(('target', '_blank'))
                    safe.append(('rel', 'noopener noreferrer'))
            elif name == 'style' and _STYLE_SAFE.match(value or ''):
                safe.append(('style', value))
        attr_html = ''.join(f' {escape(n)}="{escape(v)}"' for n, v in safe)
        self._out.append(f'<{tag}{attr_html}>')

    def handle_endtag(self, tag):
        tag = (tag or '').lower()
        if tag not in _ALLOWED:
            if tag not in _VOID and self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        if tag not in _VOID:
            self._out.append(f'</{tag}>')

    def handle_data(self, data):
        if not self._skip:
            self._out.append(str(escape(data)))

    def handle_entityref(self, name):
        if not self._skip:
            self._out.append(f'&{name};')

    def handle_charref(self, name):
        if not self._skip:
            self._out.append(f'&#{name};')

    def get_html(self):
        return ''.join(self._out)


def sanitize_outline_html(raw):
    text = (raw or '').strip()
    if not text:
        return ''
    if '<' not in text or '>' not in text:
        return str(escape(text)).replace('\n', '<br>\n')
    parser = _HtmlSanitizer()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        return str(escape(text)).replace('\n', '<br>\n')
    return parser.get_html().strip()


def _looks_like_html(text):
    return isinstance(text, str) and '<' in text and '>' in text


def stored_to_html(stored):
    """Turn DB JSON (list of lines or HTML string) into editor/PDF HTML."""
    parsed = stored
    if isinstance(stored, str):
        text = stored.strip()
        if not text:
            return ''
        if text[:1] in '[{"':
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = stored
        else:
            parsed = stored
    if isinstance(parsed, list):
        parts = []
        for item in parsed:
            if isinstance(item, dict):
                item = item.get('title') or item.get('content') or item.get('name') or ''
            s = str(item or '').strip()
            if not s:
                continue
            parts.append(s if _looks_like_html(s) else f'<p>{escape(s)}</p>')
        return ''.join(parts)
    if isinstance(parsed, str):
        if _looks_like_html(parsed):
            return parsed
        lines = [ln.strip() for ln in parsed.splitlines() if ln.strip()]
        return ''.join(f'<p>{escape(ln)}</p>' for ln in lines)
    return ''


def html_is_empty(html):
    text = re.sub(r'<[^>]+>', '', html or '')
    text = unescape(text).replace('\xa0', ' ').strip()
    return not text


def dump_rich_field(value):
    """JSON-encode sanitized HTML for CourseOutline text columns."""
    if isinstance(value, list):
        html = stored_to_html(value)
    else:
        html = value or ''
    html = sanitize_outline_html(html)
    if html_is_empty(html):
        html = ''
    return json.dumps(html)


def pdf_markup(stored):
    html = sanitize_outline_html(stored_to_html(stored))
    if html_is_empty(html):
        return None
    return Markup(html)


def editor_html(stored):
    html = sanitize_outline_html(stored_to_html(stored))
    return html if not html_is_empty(html) else ''


def plain_items(stored):
    """Plain-text lines for DOCX export."""
    html = stored_to_html(stored)
    if not html:
        return []
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.I)
    text = re.sub(r'</(p|li|h[1-6]|div|blockquote)>', '\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return [ln.strip() for ln in unescape(text).splitlines() if ln.strip()]
