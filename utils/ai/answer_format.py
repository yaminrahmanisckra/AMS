"""Convert model-answer Markdown to sanitized HTML for display/print."""
import re
from html import escape


_ALLOWED = {
    'p', 'br', 'strong', 'em', 'b', 'i', 'u', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'blockquote', 'hr', 'table', 'thead',
    'tbody', 'tr', 'th', 'td', 'a', 'code', 'pre', 'sup', 'sub', 'figure',
    'figcaption', 'span', 'div',
}
_VOID = {'br', 'hr'}


def markdown_to_html(text):
    """GitHub-flavoured subset: headings, lists, tables, quotes, bold/italic."""
    raw = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not raw:
        return ''
    if _looks_like_html(raw) and not _looks_like_markdown(raw):
        return _sanitize(raw)
    html = _md_to_html(raw)
    return _sanitize(html)


def decorate_payload(payload):
    """Add display HTML plus guideline banner fields without changing storage."""
    payload = payload if isinstance(payload, dict) else {}
    items = []
    for item in payload.get('answers') or []:
        if not isinstance(item, dict):
            continue
        items.append({
            'number': item.get('number') or '',
            'question': item.get('question') or '',
            'followed_model': item.get('followed_model') or item.get('answer_model') or '',
            'model_answer': item.get('model_answer') or '',
            'model_answer_html': markdown_to_html(item.get('model_answer') or ''),
            'marking_points': item.get('marking_points') or [],
            'citations': item.get('citations') or [],
        })
    return {
        'guideline_title': payload.get('guideline_title') or '',
        'guideline_id': payload.get('guideline_id'),
        'warnings': payload.get('warnings') or [],
        'items': items,
        'answers': payload.get('answers') or [],
        'generated': payload.get('generated') or [],
        'from_cache': bool(payload.get('from_cache')),
    }


def _looks_like_html(text):
    return bool(re.search(r'<[a-zA-Z][^>]*>', text or ''))


def _looks_like_markdown(text):
    return bool(re.search(r'(^|\n)\s{0,3}#{1,5}\s|(^|\n)\s*[-*+]\s|(^|\n)\|.+\||(^|\n)>\s|\*\*[^*]+\*\*', text or ''))


def _inline(text):
    text = escape(text)
    text = re.sub(r'!\[([^\]]*)\]\((https?://[^)\s]+)\)', r'<figure class="qb-figure"><figcaption>\1</figcaption></figure>', text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+|/[^\s)]+|#[^)\s]+)\)', r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<em>\1</em>', text)
    return text


def _is_table_row(line):
    stripped = line.strip()
    return stripped.startswith('|') and stripped.count('|') >= 2


def _is_table_sep(line):
    stripped = line.strip().strip('|')
    return bool(stripped) and all(re.fullmatch(r'\s*:?-{3,}:?\s*', part or '') for part in stripped.split('|'))


def _table_cells(line):
    stripped = line.strip()
    if stripped.startswith('|'):
        stripped = stripped[1:]
    if stripped.endswith('|'):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split('|')]


def _md_to_html(text):
    lines = text.split('\n')
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith('```'):
            fence = []
            i += 1
            while i < n and not lines[i].strip().startswith('```'):
                fence.append(escape(lines[i]))
                i += 1
            if i < n:
                i += 1
            out.append('<pre><code>' + '\n'.join(fence) + '</code></pre>')
            continue
        if re.match(r'^#{1,5}\s+', stripped):
            hashes, rest = re.match(r'^(#{1,5})\s+(.*)$', stripped).groups()
            level = min(len(hashes), 5)
            out.append(f'<h{level}>{_inline(rest)}</h{level}>')
            i += 1
            continue
        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', stripped):
            out.append('<hr>')
            i += 1
            continue
        if stripped.startswith('>'):
            quotes = []
            while i < n and lines[i].strip().startswith('>'):
                quotes.append(re.sub(r'^>\s?', '', lines[i].strip()))
                i += 1
            inner = '<br>'.join(_inline(q) for q in quotes if q)
            out.append(f'<blockquote>{inner}</blockquote>')
            continue
        if _is_table_row(stripped) and i + 1 < n and _is_table_sep(lines[i + 1]):
            headers = _table_cells(stripped)
            i += 2
            rows = []
            while i < n and _is_table_row(lines[i].strip()) and not _is_table_sep(lines[i]):
                rows.append(_table_cells(lines[i]))
                i += 1
            thead = '<thead><tr>' + ''.join(f'<th>{_inline(c)}</th>' for c in headers) + '</tr></thead>'
            body_rows = []
            for row in rows:
                cells = row + [''] * (len(headers) - len(row))
                body_rows.append('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in cells[:len(headers)]) + '</tr>')
            out.append('<div class="table-responsive"><table class="table table-bordered table-sm qb-md-table">' + thead + '<tbody>' + ''.join(body_rows) + '</tbody></table></div>')
            continue
        if re.match(r'^(\d+[.)]\s+|[-*+]\s+)', stripped):
            ordered = bool(re.match(r'^\d+[.)]\s+', stripped))
            tag = 'ol' if ordered else 'ul'
            items = []
            while i < n:
                cur = lines[i].rstrip()
                if not cur.strip():
                    if i + 1 < n and re.match(r'^(\d+[.)]\s+|[-*+]\s+)', lines[i + 1].strip()):
                        i += 1
                        continue
                    break
                m = re.match(r'^(\d+[.)]\s+|[-*+]\s+)(.*)$', cur.strip())
                if not m:
                    break
                items.append(m.group(2))
                i += 1
            out.append(f'<{tag}>' + ''.join(f'<li>{_inline(it)}</li>' for it in items) + f'</{tag}>')
            continue
        para = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if not nxt or nxt.startswith('#') or nxt.startswith('>') or nxt.startswith('```') or re.match(r'^(\d+[.)]\s+|[-*+]\s+)', nxt) or _is_table_row(nxt):
                break
            para.append(nxt)
            i += 1
        joined = ' '.join(para)
        if re.match(r'^(\*\*)?(figure|fig\.|চিত্র)\b', joined, re.I):
            out.append(f'<figure class="qb-figure"><figcaption>{_inline(joined)}</figcaption></figure>')
        else:
            out.append(f'<p>{_inline(joined)}</p>')
    return '\n'.join(out)


def _sanitize(html):
    from html.parser import HTMLParser

    class _Sanitizer(HTMLParser):
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
                if name == 'class' and re.fullmatch(r'[a-zA-Z0-9 _-]+', value):
                    safe.append(('class', value))
                elif tag == 'a' and name == 'href':
                    href = value.strip()
                    if href.startswith(('http://', 'https://', '/', '#')):
                        safe.append(('href', href))
                        safe.append(('target', '_blank'))
                        safe.append(('rel', 'noopener noreferrer'))
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
                self._out.append(escape(data))

        def get_html(self):
            return ''.join(self._out)

    parser = _Sanitizer()
    try:
        parser.feed(html or '')
        parser.close()
    except Exception:
        return escape(html or '')
    return parser.get_html()
