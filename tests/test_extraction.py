from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from pypdf import PdfWriter
from werkzeug.datastructures import FileStorage

from app.utils import ExtractionError, extract_resume

from .conftest import docx_bytes, pdf_bytes


def test_docx_table_text_is_included(app):
    with app.app_context():
        _, text = extract_resume(
            FileStorage(stream=BytesIO(docx_bytes()), filename="resume.docx")
        )
        assert "GitHub Linux" in text


def test_scanned_or_empty_pdf_has_useful_error(app):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    with (
        app.app_context(),
        pytest.raises(ExtractionError, match="Scanned PDFs need OCR"),
    ):
        extract_resume(
            FileStorage(stream=BytesIO(buffer.getvalue()), filename="scan.pdf")
        )


def test_encrypted_pdf_is_rejected(app):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("fictional-password")
    buffer = BytesIO()
    writer.write(buffer)
    with app.app_context(), pytest.raises(ExtractionError, match="PDF password"):
        extract_resume(
            FileStorage(stream=BytesIO(buffer.getvalue()), filename="encrypted.pdf")
        )


def test_docx_container_expansion_is_bounded(app):
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "a" * (20 * 1024 * 1024 + 1))
    with app.app_context(), pytest.raises(ExtractionError, match="expands beyond"):
        extract_resume(
            FileStorage(stream=BytesIO(buffer.getvalue()), filename="large.docx")
        )


def test_extracted_text_limit(app):
    app.config["MAX_TEXT_LENGTH"] = 5
    with app.app_context(), pytest.raises(ExtractionError, match="too long"):
        extract_resume(FileStorage(stream=BytesIO(pdf_bytes()), filename="resume.pdf"))
