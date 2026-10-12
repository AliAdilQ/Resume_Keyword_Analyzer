import re

import pytest

from app.auth import safe_next
from app.extensions import db
from app.models import User


def test_registration_hashes_password(client, app):
    response = client.post(
        "/register",
        data={
            "username": "new_user",
            "email": "new@example.com",
            "password": "Securepass123",
            "confirm_password": "Securepass123",
            "consent": "y",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.username == "new_user"))
        assert user and user.password_hash != "Securepass123"
        assert user.check_password("Securepass123")
        assert not user.is_admin


def test_duplicate_registration(client):
    response = client.post(
        "/register",
        data={
            "username": "TESTER",
            "email": "unused@example.com",
            "password": "Securepass123",
            "confirm_password": "Securepass123",
            "consent": "y",
        },
    )
    assert b"already registered" in response.data


@pytest.mark.parametrize("identity", ["tester", "TESTER", "tester@example.com"])
def test_login(client, identity):
    response = client.post(
        "/login", data={"identity": identity, "password": "Testpass123"}
    )
    assert response.status_code == 302
    assert response.location.endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200


def test_invalid_login(client):
    response = client.post(
        "/login", data={"identity": "tester", "password": "incorrect"}
    )
    assert b"Invalid credentials" in response.data
    assert client.get("/dashboard").status_code == 302


def test_logout(client, login):
    login()
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302
    assert client.get("/dashboard").status_code == 302


@pytest.mark.parametrize(
    "destination",
    [
        "https://evil.example",
        "//evil.example",
        "/\\evil.example",
        "javascript:alert(1)",
        "\n//evil.example",
    ],
)
def test_reject_external_redirect(destination):
    assert safe_next(destination) is None


def test_local_redirect_allowed(client):
    assert safe_next("/history?q=python") == "/history?q=python"
    response = client.post(
        "/login?next=/history", data={"identity": "tester", "password": "Testpass123"}
    )
    assert response.location.endswith("/history")


def test_inactive_account_cannot_login(client, app):
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.username == "tester"))
        user.is_active = False
        db.session.commit()
    response = client.post(
        "/login", data={"identity": "tester", "password": "Testpass123"}
    )
    assert b"inactive account" in response.data
    assert client.get("/dashboard").status_code == 302


def test_login_throttle(client, app):
    app.config["LOGIN_MAX_ATTEMPTS"] = 2
    for _ in range(2):
        assert (
            client.post(
                "/login", data={"identity": "tester", "password": "wrong"}
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/login", data={"identity": "tester", "password": "wrong"}
        ).status_code
        == 429
    )


def test_csrf_is_required(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    assert (
        client.post(
            "/login", data={"identity": "tester", "password": "Testpass123"}
        ).status_code
        == 400
    )


def test_valid_csrf_login_and_logout(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    page = client.get("/login")
    token = (
        re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data)
        .group(1)
        .decode()
    )
    response = client.post(
        "/login",
        data={"identity": "tester", "password": "Testpass123", "csrf_token": token},
    )
    assert response.status_code == 302
    assert client.post("/logout", data={"csrf_token": token}).status_code == 302


def test_valid_csrf_registration(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    page = client.get("/register")
    token = (
        re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page.data)
        .group(1)
        .decode()
    )
    response = client.post(
        "/register",
        data={
            "username": "csrf_user",
            "email": "csrf@example.com",
            "password": "Securepass123",
            "confirm_password": "Securepass123",
            "consent": "y",
            "csrf_token": token,
        },
    )
    assert response.status_code == 302


def test_weak_password_is_rejected(client):
    response = client.post(
        "/register",
        data={
            "username": "weak",
            "email": "weak@example.com",
            "password": "abcdefgh",
            "confirm_password": "abcdefgh",
            "consent": "y",
        },
    )
    assert b"Include a letter and a number" in response.data
