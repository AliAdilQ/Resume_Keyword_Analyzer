"""Persisted accounts, private analyses, and administrative activity."""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    analyses = db.relationship(
        "ResumeAnalysis", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class ResumeAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    original_filename = db.Column(db.String(255), nullable=False)
    job_title = db.Column(db.String(100), nullable=False, default="Untitled role")
    company_name = db.Column(db.String(100), nullable=False, default="")
    resume_text = db.Column(db.Text, nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    match_score = db.Column(db.Float, nullable=False)
    similarity_score = db.Column(db.Float, nullable=False)
    matched_keywords = db.Column(db.JSON, nullable=False)
    missing_keywords = db.Column(db.JSON, nullable=False)
    resume_keywords = db.Column(db.JSON, nullable=False)
    job_keywords = db.Column(db.JSON, nullable=False)
    result = db.Column(db.JSON, nullable=False)
    seed_key = db.Column(db.String(60), unique=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    user = db.relationship("User", back_populates="analyses")

    @property
    def score_state(self):
        if self.match_score >= 85:
            return "Excellent"
        if self.match_score >= 70:
            return "Good"
        if self.match_score >= 50:
            return "Moderate"
        return "Needs improvement"

    @property
    def score_color(self):
        if self.match_score >= 70:
            return "success"
        if self.match_score >= 50:
            return "warning"
        return "danger"


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    user = db.relationship("User")
