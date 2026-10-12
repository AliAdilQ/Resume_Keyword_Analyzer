"""Registration and session authentication."""

import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .forms import LoginForm, RegisterForm
from .models import ActivityLog, User

auth = Blueprint("auth", __name__)
_dummy_hash = generate_password_hash("local-timing-placeholder")


def safe_next(destination):
    """Accept only local absolute paths, avoiding open redirects."""
    if not destination or "\\" in destination or any(ord(c) < 32 for c in destination):
        return None
    parts = urlsplit(destination)
    if (
        parts.scheme
        or parts.netloc
        or not destination.startswith("/")
        or destination.startswith("//")
    ):
        return None
    return destination


def login_limited():
    """Small per-process throttle for a local deployment; no proxy-header trust."""
    attempts = current_app.extensions.setdefault("login_attempts", defaultdict(deque))
    now = time.monotonic()
    cutoff = now - current_app.config["LOGIN_WINDOW_SECONDS"]
    for address in list(attempts):
        while attempts[address] and attempts[address][0] < cutoff:
            attempts[address].popleft()
        if not attempts[address]:
            del attempts[address]
    bucket = attempts[request.remote_addr or "unknown"]
    if len(bucket) >= current_app.config["LOGIN_MAX_ATTEMPTS"]:
        return True
    bucket.append(now)
    return False


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        email = form.email.data.strip().lower()
        existing = db.session.scalar(
            db.select(User).where(
                or_(
                    func.lower(User.username) == username,
                    func.lower(User.email) == email,
                )
            )
        )
        if existing:
            flash("That username or email is already registered.", "warning")
        else:
            user = User(username=username, email=email)
            user.set_password(form.password.data)
            db.session.add(user)
            try:
                db.session.flush()
                db.session.add(
                    ActivityLog(user_id=user.id, action="Account registered")
                )
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("That username or email is already registered.", "warning")
            else:
                flash(
                    "Account created. Sign in to start your first analysis.", "success"
                )
                return redirect(url_for("auth.login"))
    return render_template("register.html", form=form)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        if login_limited():
            flash("Too many sign-in attempts. Try again in five minutes.", "warning")
            return render_template("login.html", form=form), 429
        identity = form.identity.data.strip().lower()
        user = db.session.scalar(
            db.select(User).where(
                or_(
                    func.lower(User.username) == identity,
                    func.lower(User.email) == identity,
                )
            )
        )
        valid = (
            user.check_password(form.password.data)
            if user
            else check_password_hash(_dummy_hash, form.password.data)
        )
        if user and valid and user.is_active:
            login_user(user)
            db.session.add(ActivityLog(user_id=user.id, action="Signed in"))
            db.session.commit()
            destination = safe_next(request.args.get("next"))
            return redirect(
                destination
                or url_for("admin.dashboard" if user.is_admin else "main.dashboard")
            )
        flash("Invalid credentials or an inactive account.", "danger")
    return render_template("login.html", form=form)


@auth.post("/logout")
@login_required
def logout():
    db.session.add(ActivityLog(user_id=current_user.id, action="Signed out"))
    db.session.commit()
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))
