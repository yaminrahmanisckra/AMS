"""Shared WeasyPrint font resolution for cPanel-safe PDF generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple

from flask import current_app


def _static_root() -> Path:
    return Path(current_app.static_folder or (Path(current_app.root_path) / 'static'))


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


def resolve_dejavu_pdf_fonts() -> Tuple[Optional[str], Optional[str], Optional[Path]]:
    """DejaVu Sans for dense table PDFs (attendance). Returns (regular, bold, fonts_dir)."""
    for dirname in ('fonts', 'Fonts'):
        fonts_dir = _static_root() / dirname
        regular = fonts_dir / 'DejaVuSans.ttf'
        bold = fonts_dir / 'DejaVuSans-Bold.ttf'
        if regular.is_file() and bold.is_file():
            return regular.resolve().as_uri(), bold.resolve().as_uri(), fonts_dir.resolve()
    return None, None, None


def formal_font_face_css(fonts: dict[str, Any], family: str = 'PDFSerif') -> str:
    """Build @font-face CSS block for Liberation Serif URIs."""
    parts = [
        f"""@font-face {{
            font-family: '{family}';
            src: url('{fonts['regular']}');
            font-weight: normal;
            font-style: normal;
        }}""",
        f"""@font-face {{
            font-family: '{family}';
            src: url('{fonts['bold']}');
            font-weight: bold;
            font-style: normal;
        }}""",
    ]
    if fonts.get('italic'):
        parts.append(
            f"""@font-face {{
            font-family: '{family}';
            src: url('{fonts['italic']}');
            font-weight: normal;
            font-style: italic;
        }}"""
        )
    if fonts.get('bold_italic'):
        parts.append(
            f"""@font-face {{
            font-family: '{family}';
            src: url('{fonts['bold_italic']}');
            font-weight: bold;
            font-style: italic;
        }}"""
        )
    return '\n'.join(parts)
