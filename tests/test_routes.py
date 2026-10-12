from io import BytesIO
from pathlib import Path

import pytest

from app.extensions import db
from app.models import ResumeAnalysis

from .conftest import JOB, RESUME, docx_bytes, pdf_bytes


@pytest.mark.parametrize("path", ["/", "/about", "/login", "/register"])
def test_public_routes_load(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    "path", ["/dashboard", "/analyze", "/history", "/admin/dashboard"]
)
def test_protected_routes_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 302 and "/login" in response.location


def test_not_found(client):
    assert client.get("/does-not-exist").status_code == 404


def test_custom_server_error_does_not_expose_details(client, app):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/test-server-error")
    def fail():
        raise RuntimeError("private-diagnostic-detail")

    response = client.get("/test-server-error")
    assert response.status_code == 500
    assert b"unexpected bump" in response.data
    assert b"private-diagnostic-detail" not in response.data


def test_database_error_is_handled(client, app):
    from sqlalchemy.exc import SQLAlchemyError

    @app.get("/test-database-error")
    def fail():
        raise SQLAlchemyError("private-database-detail")

    response = client.get("/test-database-error")
    assert response.status_code == 500
    assert b"private-database-detail" not in response.data


@pytest.mark.parametrize(
    "filename,content",
    [
        ("resume.txt", RESUME.encode()),
        ("resume.PDF", pdf_bytes()),
        ("resume.docx", docx_bytes()),
    ],
    ids=["txt", "pdf", "docx"],
)
def test_upload_extracts_analyzes_saves_and_renders(
    client, login, app, filename, content
):
    login()
    response = client.post(
        "/analyze",
        data={
            "resume": (BytesIO(content), filename),
            "job_description": JOB,
            "job_title": "Python Developer",
            "company_name": "Example",
        },
    )
    assert response.status_code == 302
    result = client.get(response.location)
    assert result.status_code == 200
    assert b"keyword-donut" in result.data and b"improvement plan" in result.data
    assert client.get("/dashboard").status_code == 200
    assert client.get("/history").status_code == 200
    with app.app_context():
        analysis = db.session.scalar(db.select(ResumeAnalysis))
        assert analysis.resume_text and analysis.job_description == JOB
        assert 0 <= analysis.match_score <= 100
        assert analysis.user.username == "tester"
        report = client.get(f"/analysis/{analysis.id}/download")
        assert report.status_code == 200
        assert "attachment" in report.headers["Content-Disposition"]
        assert b"MATCHED KEYWORDS" in report.data
    assert not list(Path(app.config["UPLOAD_FOLDER"]).iterdir())


@pytest.mark.parametrize(
    "filename,content,expected",
    [
        ("resume.exe", b"example", b"Choose a PDF"),
        ("resume.txt", b"", b"file is empty"),
        ("resume.txt", b"\x00\x01", b"binary data"),
        ("resume.pdf", b"not a PDF", b"not a valid PDF"),
        ("resume.docx", b"not a DOCX", b"could not read"),
        ("resume.txt", b"\xff\xfe", b"UTF-8 encoding"),
    ],
)
def test_invalid_uploads_are_rejected(client, login, filename, content, expected):
    login()
    response = client.post(
        "/analyze",
        data={"resume": (BytesIO(content), filename), "job_description": JOB},
    )
    assert response.status_code == 200 and expected in response.data


def test_size_limit(client, login, app):
    login()
    app.config["MAX_FILE_SIZE"] = 10
    response = client.post(
        "/analyze",
        data={
            "resume": (BytesIO(RESUME.encode()), "resume.txt"),
            "job_description": JOB,
        },
    )
    assert b"smaller than 5 MB" in response.data
    app.config["MAX_CONTENT_LENGTH"] = 10
    assert client.post("/analyze", data={"x": "x" * 100}).status_code == 413


def test_blank_job_is_rejected(client, login, app):
    login()
    response = client.post(
        "/analyze",
        data={
            "resume": (BytesIO(RESUME.encode()), "resume.txt"),
            "job_description": " " * 30,
        },
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(ResumeAnalysis.id))) == 0


def test_other_users_cannot_read_download_or_delete(client, login, app):
    login()
    response = client.post(
        "/analyze",
        data={
            "resume": (BytesIO(RESUME.encode()), "resume.txt"),
            "job_description": JOB,
        },
    )
    result_path = response.location
    client.post("/logout")
    login("other")
    assert client.get(result_path).status_code == 404
    assert client.get(result_path + "/download").status_code == 404
    assert client.post(result_path + "/delete").status_code == 404
    assert b"Untitled role" not in client.get("/history").data


def test_owner_can_delete(client, login, app):
    login()
    response = client.post(
        "/analyze",
        data={
            "resume": (BytesIO(RESUME.encode()), "resume.txt"),
            "job_description": JOB,
        },
    )
    assert client.post(response.location + "/delete").status_code == 302
    assert client.get(response.location).status_code == 404


def test_stored_text_is_escaped(client, login):
    login()
    response = client.post(
        "/analyze",
        data={
            "resume": (
                BytesIO((RESUME + "<script>alert(1)</script>").encode()),
                "resume.txt",
            ),
            "job_description": JOB,
            "job_title": '<img src=x onerror="alert(1)">',
        },
    )
    page = client.get(response.location)
    assert b"<script>alert(1)</script>" not in page.data
    assert b"&lt;script&gt;" in page.data


def test_secure_filename(client, login, app):
    login()
    client.post(
        "/analyze",
        data={
            "resume": (BytesIO(RESUME.encode()), "../../private resume.txt"),
            "job_description": JOB,
        },
    )
    with app.app_context():
        assert (
            db.session.scalar(db.select(ResumeAnalysis)).original_filename
            == "private_resume.txt"
        )


def test_security_headers(client, login):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    login()
    assert client.get("/history").headers["Cache-Control"] == "no-store"
