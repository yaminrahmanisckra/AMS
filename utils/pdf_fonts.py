"""Shared WeasyPrint font resolution for cPanel-safe PDF generation."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Optional, Tuple

from flask import current_app


def _static_root() -> Path:
    return Path(current_app.static_folder or (Path(current_app.root_path) / 'static'))


def _ttf_data_src(path: Path) -> str:
    raw = path.read_bytes()
    b64 = base64.standard_b64encode(raw).decode('ascii')
    return f"url(data:font/ttf;base64,{b64}) format('truetype')"


def _font_src(path: Optional[Path], uri: str) -> str:
    """Prefer a data URI so WeasyPrint does not need file:// (fails on cPanel)."""
    if path is not None and path.is_file():
        try:
            return _ttf_data_src(path)
        except OSError:
            pass
    return f"url('{uri}')"


def resolve_formal_pdf_fonts() -> Optional[dict[str, Any]]:
    """Liberation Serif (Times New Roman–compatible) for formal academic PDFs.

    Returns dict with: regular, bold, fonts_dir, and optional italic / bold_italic URIs.
    """
    for dirname in ('fonts', 'Fonts'):
        fonts_dir = _static_root() / dirname
        regular = fonts_dir / 'LiberationSerif-Regular.ttf'
        bold = fonts_dir / 'LiberationSerif-Bold.ttf'
        italic = fonts_dir / 'LiberationSerif-Italic.ttf'
        bold_italic = fonts_dir / 'LiberationSerif-BoldItalic.ttf'
        if regular.is_file() and bold.is_file():
            result: dict[str, Any] = {
                'regular': regular.resolve().as_uri(),
                'bold': bold.resolve().as_uri(),
                'fonts_dir': fonts_dir.resolve(),
            }
            if italic.is_file():
                result['italic'] = italic.resolve().as_uri()
            if bold_italic.is_file():
                result['bold_italic'] = bold_italic.resolve().as_uri()
            return result
    return None


def resolve_bangla_pdf_font() -> Optional[Path]:
    """Kalpurush, then Noto Sans Bengali. Case-insensitive path search for cPanel."""
    names = (
        'kalpurush.ttf',
        'Kalpurush.ttf',
        'NotoSansBengali-Regular.ttf',
    )
    for dirname in ('Fonts', 'fonts'):
        folder = _static_root() / dirname
        for name in names:
            path = folder / name
            if path.is_file():
                return path.resolve()
    return None


def resolve_dejavu_pdf_fonts() -> Tuple[Optional[str], Optional[str], Optional[Path]]:
    """DejaVu Sans for dense table PDFs (attendance). Returns (regular, bold, fonts_dir)."""
    for dirname in ('fonts', 'Fonts'):
        fonts_dir = _static_root() / dirname
        regular = fonts_dir / 'DejaVuSans.ttf'
        bold = fonts_dir / 'DejaVuSans-Bold.ttf'
        if regular.is_file() and bold.is_file():
            return regular.resolve().as_uri(), bold.resolve().as_uri(), fonts_dir.resolve()
    return None, None, None


# Keep Latin off Kalpurush (its Latin glyphs look doubled) and Bengali off Liberation.
LATIN_UNICODE_RANGE = 'U+0000-024F, U+1E00-1EFF, U+2000-206F, U+20A0-20CF, U+2100-214F'
BANGLA_UNICODE_RANGE = 'U+0980-09FF, U+0964-0965, U+09E6-09EF, U+200C-200D, U+25CC'


def _face(
    family: str,
    src: str,
    weight: str = 'normal',
    style: str = 'normal',
    unicode_range: Optional[str] = None,
) -> str:
    extra = f" unicode-range: {unicode_range};" if unicode_range else ''
    return (
        f"@font-face {{ font-family: '{family}'; src: {src}; "
        f"font-weight: {weight}; font-style: {style};{extra} }}"
    )


def formal_font_face_css(fonts: dict[str, Any], family: str = 'PDFSerif') -> str:
    """Build @font-face CSS for Liberation Serif, embedded when the TTF is on disk."""
    fonts_dir = fonts.get('fonts_dir')
    directory = Path(fonts_dir) if fonts_dir else None

    def src(filename: str, uri_key: str) -> str:
        path = (directory / filename) if directory else None
        return _font_src(path, fonts[uri_key])

    parts = [
        _face(family, src('LiberationSerif-Regular.ttf', 'regular'), unicode_range=LATIN_UNICODE_RANGE),
        _face(family, src('LiberationSerif-Bold.ttf', 'bold'), 'bold', unicode_range=LATIN_UNICODE_RANGE),
    ]
    if fonts.get('italic'):
        parts.append(_face(
            family, src('LiberationSerif-Italic.ttf', 'italic'), 'normal', 'italic',
            unicode_range=LATIN_UNICODE_RANGE,
        ))
    if fonts.get('bold_italic'):
        parts.append(_face(
            family, src('LiberationSerif-BoldItalic.ttf', 'bold_italic'), 'bold', 'italic',
            unicode_range=LATIN_UNICODE_RANGE,
        ))
    return '\n'.join(parts)


def bangla_font_face_css(family: str = 'Kalpurush') -> str:
    path = resolve_bangla_pdf_font()
    if not path:
        return ''
    return _face(family, _ttf_data_src(path), unicode_range=BANGLA_UNICODE_RANGE)


def noto_bangla_font_face_css(family: str = 'NotoBengali') -> str:
    for dirname in ('Fonts', 'fonts'):
        path = _static_root() / dirname / 'NotoSansBengali-Regular.ttf'
        if path.is_file():
            return _face(family, _ttf_data_src(path.resolve()), unicode_range=BANGLA_UNICODE_RANGE)
    return ''


def weasyprint_font_css() -> str:
    """Liberation Serif (Latin) plus Kalpurush/Noto (Bengali), embedded as data URIs."""
    parts = []
    formal = resolve_formal_pdf_fonts()
    if formal:
        parts.append(formal_font_face_css(formal))
    bangla = bangla_font_face_css()
    if bangla:
        parts.append(bangla)
    noto = noto_bangla_font_face_css()
    if noto:
        parts.append(noto)
    return '\n'.join(parts)


def inject_weasyprint_fonts(html_content: str) -> Tuple[str, str]:
    """Insert embedded @font-face CSS. Returns (html, base_url)."""
    css = weasyprint_font_css()
    if css:
        block = f'<style>{css}</style>'
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', block + '</head>', 1)
        else:
            html_content = block + html_content
    formal = resolve_formal_pdf_fonts()
    if formal and formal.get('fonts_dir'):
        return html_content, formal['fonts_dir'].as_uri() + '/'
    return html_content, '.'
