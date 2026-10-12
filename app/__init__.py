"""Flask application factory."""

import os
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import current_user, logout_user
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import SQLAlchemyError

from config import Config

from .extensions import csrf, db, login_manager


def create_app(test_config=None):
    app = Flask(
        __name__, instance_path=str(Path(__file__).resolve().parent.parent / "instance")
    )
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if app.config["APP_ENV"] == "production" and (
        not os.getenv("SECRET_KEY")
        or os.getenv("SECRET_KEY") == "change-this-secret-key"
    ):
        raise RuntimeError("Set a strong SECRET_KEY before running in production.")
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    from .admin import admin
    from .auth import auth
    from .models import User
    from .routes import main

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(admin)

    @app.before_request
    def reject_inactive_sessions():
        if current_user.is_authenticated and not current_user.is_active:
            logout_user()
            flash("Your account is inactive. Contact the administrator.", "warning")
            return redirect(url_for("auth.login"))

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if current_user.is_authenticated or request.endpoint in {
            "auth.login",
            "auth.register",
        }:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def shared_context():
        from .models import utcnow

        return {"current_year": utcnow().year}

    @app.errorhandler(CSRFError)
    def csrf_error(_):
        return render_template(
            "errors/400.html",
            message="Your form expired. Reload the page and try again.",
        ), 400

    @app.errorhandler(413)
    def too_large(_):
        return render_template(
            "errors/400.html", message="Upload too large. Choose a resume under 5 MB."
        ), 413

    for code in (403, 404, 500):

        def handler(error, status=code):
            if status == 500:
                db.session.rollback()
            return render_template(f"errors/{status}.html"), status

        app.register_error_handler(code, handler)

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.error("Database operation failed: %s", type(error).__name__)
        return render_template("errors/500.html"), 500

    with app.app_context():
        db.create_all()
    return app
