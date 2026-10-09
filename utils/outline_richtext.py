"""Rich-text helpers for course-outline Part D (textbooks, references, etc.)."""
import json
import re
from html.parser import HTMLParser
from html import unescape

from markupsafe import Markup, escape

_ALLOWED = {
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'ul', 'ol', 'li',
    'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div', 'blockquote', 'sup', 'sub',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'caption',
    'colgroup', 'col', 'hr',
}
_VOID = {'br', 'hr'}
_FOOTNOTE_CLASSES = {'wa-fn-ref', 'wa-footnotes', 'wa-fn-rule'}
_STYLE_SAFE = re.compile(
    r'^(?:\s*(?:color|background-color|font-family|font-size|font-weight|font-style|text-decoration|text-align|line-height|margin-left|padding-left)\s*:\s*[^;]+;?\s*)+$',
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
                    if not href.startswith('#'):
                        safe.append(('target', '_blank'))
                        safe.append(('rel', 'noopener noreferrer'))
            elif name == 'class':
                kept = [part for part in str(value).split() if part in _FOOTNOTE_CLASSES]
                if kept:
                    safe.append(('class', ' '.join(kept)))
            elif name == 'id' and re.match(r'^wa-fn(ref)?-[1-9]\d{0,3}$', str(value).strip()):
                safe.append(('id', str(value).strip()))
            elif name == 'style' and _STYLE_SAFE.match(value or ''):
                lowered = value.lower()
                if 'url(' not in lowered and 'expression' not in lowered:
                    safe.append(('style', value))
            elif name in ('colspan', 'rowspan') and tag in ('th', 'td'):
                try:
                    span = int(str(value).strip())
                    if 1 <= span <= 50:
                        safe.append((name, str(span)))
                except (TypeError, ValueError):
                    pass
            elif name == 'border' and tag == 'table':
                try:
                    border = int(str(value).strip())
                    if 0 <= border <= 4:
                        safe.append((name, str(border)))
                except (TypeError, ValueError):
                    pass
            elif name in ('cellpadding', 'cellspacing') and tag == 'table':
                try:
                    pad = int(str(value).strip())
                    if 0 <= pad <= 20:
                        safe.append((name, str(pad)))
                except (TypeError, ValueError):
                    pass
            elif name == 'width' and tag in ('table', 'th', 'td', 'col'):
                width = str(value or '').strip()
                if width and len(width) <= 12 and re.match(r'^(\d{1,4}(\.\d+)?%?|auto)$', width, re.I):
                    safe.append((name, width))
            elif name == 'align' and tag in ('table', 'th', 'td'):
                align = str(value or '').strip().lower()
                if align in ('left', 'center', 'right', 'justify'):
                    safe.append((name, align))
            elif name == 'valign' and tag in ('th', 'td'):
                valign = str(value or '').strip().lower()
                if valign in ('top', 'middle', 'bottom', 'baseline'):
                    safe.append((name, valign))
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


class _HtmlToPlain(HTMLParser):
    """Turn TinyMCE lists into numbered/bulleted plain text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = []
        self._stack = []
        self._buf = []
        self._in_li = 0

    def handle_starttag(self, tag, attrs):
        tag = (tag or '').lower()
        if tag in ('ol', 'ul'):
            self._flush_paragraph()
            self._stack.append({'type': tag, 'index': 0})
        elif tag == 'li':
            self._flush_item()
            self._in_li += 1
            if self._stack:
                self._stack[-1]['index'] += 1
        elif tag == 'br':
            if self._in_li:
                self._buf.append(' ')
            else:
                self._flush_paragraph()
        elif tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'hr') and not self._in_li:
            self._flush_paragraph()

    def handle_endtag(self, tag):
        tag = (tag or '').lower()
        if tag == 'li':
            self._flush_item()
            if self._in_li:
                self._in_li -= 1
        elif tag in ('ol', 'ul'):
            self._flush_item()
            if self._stack:
                self._stack.pop()
        elif tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'hr') and not self._in_li:
            self._flush_paragraph()

    def handle_data(self, data):
        if data:
            self._buf.append(data)

    def _take(self):
        text = unescape(''.join(self._buf)).replace('\xa0', ' ')
        self._buf = []
        return ' '.join(text.split())

    def _prefix(self):
        if not self._stack:
            return ''
        indent = '  ' * (len(self._stack) - 1)
        top = self._stack[-1]
        if top['type'] == 'ol':
            return f'{indent}{top["index"]}. '
        return f'{indent}- '

    def _flush_item(self):
        text = self._take()
        if text:
            self.lines.append(self._prefix() + text)

    def _flush_paragraph(self):
        text = self._take()
        if text:
            self.lines.append(text)


def html_to_plain_text(html):
    """Convert rich-text HTML to plain text, keeping numbered and bullet lists."""
    text = (html or '').strip()
    if not text:
        return ''
    if '<' not in text:
        return unescape(text).replace('\xa0', ' ').strip()
    parser = _HtmlToPlain()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        stripped = re.sub(r'<[^>]+>', ' ', text)
        return ' '.join(unescape(stripped).split())
    parser._flush_paragraph()
    return '\n'.join(parser.lines).strip()


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
