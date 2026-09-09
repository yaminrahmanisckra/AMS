"""FILE-03/04/05: unified upload validation."""
import io
import zipfile

import pytest
from werkzeug.datastructures import FileStorage

from utils.uploads import (
    DOCUMENT_IMAGE_PURPOSE,
    LANDING_PURPOSE,
    QA_PURPOSE,
    UploadError,
    sniff_kind,
    validate_upload,
)


def _storage(name: str, data: bytes) -> FileStorage:
    return FileStorage(stream=io.BytesIO(data), filename=name, content_type='application/octet-stream')


def _minimal_png() -> bytes:
    # 1x1 PNG
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
        b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )


def _minimal_jpeg() -> bytes:
    # Minimal JFIF-ish JPEG (1x1)
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x14, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x03, 0xFF, 0xC4, 0x00, 0x14, 0x10, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
        0x7F, 0xFF, 0xD9,
    ])


def _docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types/>')
        zf.writestr('word/document.xml', '<?xml version="1.0"?><w:document/>')
    return buf.getvalue()


def test_sniff_png_jpeg_pdf_txt():
    assert sniff_kind(_minimal_png()) == 'png'
    assert sniff_kind(_minimal_jpeg()) == 'jpg'
    assert sniff_kind(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n') == 'pdf'
    assert sniff_kind(b'Hello world\n') == 'txt'


def test_qa_rejects_exe_and_html():
    with pytest.raises(UploadError):
        validate_upload(_storage('malware.exe', b'MZ\x90\x00fake'), QA_PURPOSE)
    with pytest.raises(UploadError):
        validate_upload(_storage('x.html', b'<html><script>alert(1)</script></html>'), QA_PURPOSE)


def test_qa_rejects_polyglot_extension_mismatch():
    with pytest.raises(UploadError):
        validate_upload(_storage('photo.jpg', b'%PDF-1.4\nfake'), QA_PURPOSE)


def test_qa_accepts_pdf_and_png():
    pdf = validate_upload(_storage('note.pdf', b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\ntrailer'), QA_PURPOSE)
    assert pdf.ext == 'pdf'
    png = validate_upload(_storage('pic.png', _minimal_png()), QA_PURPOSE)
    assert png.kind == 'png'


def test_landing_rejects_zip_and_rar():
    zip_data = _docx_bytes()  # zip container; but named .zip without ooxml path... use plain zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('readme.txt', 'hi')
    plain_zip = buf.getvalue()
    with pytest.raises(UploadError):
        validate_upload(_storage('payload.zip', plain_zip), LANDING_PURPOSE)
    with pytest.raises(UploadError):
        validate_upload(_storage('payload.rar', b'Rar!\x1a\x07\x00'), LANDING_PURPOSE)


def test_landing_accepts_docx():
    v = validate_upload(_storage('guide.docx', _docx_bytes()), LANDING_PURPOSE)
    assert v.ext == 'docx'
    assert v.kind == 'docx'


def test_document_image_rejects_non_image():
    with pytest.raises(UploadError):
        validate_upload(_storage('cert.pdf', b'%PDF-1.4\nx'), DOCUMENT_IMAGE_PURPOSE)


def test_document_image_accepts_jpeg():
    v = validate_upload(_storage('cert.jpeg', _minimal_jpeg()), DOCUMENT_IMAGE_PURPOSE)
    assert v.kind == 'jpg'
