from io import BytesIO

import pytest

from app.extensions import db
from app.models import User

from .conftest import JOB, RESUME


@pytest.mark.parametrize(
    "path", ["/admin/dashboard", "/admin/users", "/admin/analyses", "/admin/users/1"]
)
def test_normal_user_cannot_access_admin(client, login, path):
    login()
    assert client.get(path).status_code == 403


@pytest.mark.parametrize(
    "path", ["/admin/dashboard", "/admin/users", "/admin/analyses", "/admin/users/1"]
)
def test_admin_pages_load(client, login, path):
    login("admin")
    assert client.get(path).status_code == 200


def test_admin_cannot_deactivate_self(client, login, app):
    login("admin")
    with app.app_context():
        admin = db.session.scalar(db.select(User).where(User.username == "admin"))
        admin_id = admin.id
    response = client.post(f"/admin/users/{admin_id}/toggle", follow_redirects=True)
    assert b"cannot deactivate your own" in response.data
    with app.app_context():
        assert db.session.get(User, admin_id).is_active


def test_toggle_revokes_existing_session(client, login, app):
    login()
    admin_client = app.test_client()
    admin_client.post("/login", data={"identity": "admin", "password": "Testpass123"})
    with app.app_context():
        tester_id = db.session.scalar(
            db.select(User).where(User.username == "tester")
        ).id
    admin_client.post(f"/admin/users/{tester_id}/toggle")
    response = client.get("/history")
    assert response.status_code == 302 and "/login" in response.location
    admin_client.post(f"/admin/users/{tester_id}/toggle")
    assert login().status_code == 302


def test_user_search(client, login):
    login("admin")
    response = client.get("/admin/users?q=other%40example.com")
    assert b"other@example.com" in response.data
    assert b"tester@example.com" not in response.data


def test_admin_analysis_filters_and_delete(client, login):
    login()
    response = client.post(
        "/analyze",
        data={
            "resume": (BytesIO(RESUME.encode()), "resume.txt"),
            "job_description": JOB,
            "job_title": "Python Tester",
            "company_name": "Fictional",
        },
    )
    result_path = response.location
    client.post("/logout")
    login("admin")
    assert (
        b"Python Tester"
        in client.get("/admin/analyses?q=Fictional&min_score=0&max_score=100").data
    )
    assert b"Python Tester" not in client.get("/admin/analyses?min_score=100").data
    assert (
        b"Python Tester" not in client.get("/admin/analyses?from_date=2099-01-01").data
    )
    assert b"valid date" in client.get("/admin/analyses?from_date=invalid").data
    assert b"numbers from 0 to 100" in client.get("/admin/analyses?min_score=nan").data
    assert client.get(result_path).status_code == 200
    assert client.post(result_path + "/delete").status_code == 403
    analysis_id = result_path.rsplit("/", 1)[1]
    assert client.post(f"/admin/analyses/{analysis_id}/delete").status_code == 302
    assert client.get(result_path).status_code == 404
