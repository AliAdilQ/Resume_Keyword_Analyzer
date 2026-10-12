"""Idempotent local demo seed. Existing credentials are never reset."""

from datetime import timedelta
from pathlib import Path

import click

from app import create_app
from app.extensions import db
from app.models import ResumeAnalysis, User, utcnow
from app.services import save_analysis

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"
EXAMPLES = [
    (
        "python-developer-v1",
        "Python Developer",
        "TechNova",
        "sample_resume.txt",
        "python_developer_job.txt",
        4,
    ),
    (
        "ml-engineer-v1",
        "Machine Learning Engineer",
        "DataVision Labs",
        "machine_learning_resume.txt",
        "machine_learning_job.txt",
        2,
    ),
    (
        "data-analyst-v1",
        "Data Analyst",
        "InsightWorks",
        "data_analyst_resume.txt",
        "data_analyst_job.txt",
        1,
    ),
    (
        "backend-developer-v1",
        "Backend Developer",
        "CloudStack Solutions",
        "backend_developer_resume.txt",
        "backend_developer_job.txt",
        0,
    ),
]


def seed_database():
    """Create missing demo accounts and compute genuine sample analyses."""
    db.create_all()
    click.echo("Database initialized successfully.")
    accounts = {}
    for username, email, password, admin in (
        ("admin", "admin@example.com", "Admin@123", True),
        ("demo_user", "demo@example.com", "Demo@123", False),
    ):
        user = db.session.scalar(db.select(User).where(User.username == username))
        if not user:
            email_owner = db.session.scalar(db.select(User).where(User.email == email))
            if email_owner:
                raise click.ClickException(
                    f"Cannot seed {username}: demo email is already in use."
                )
            user = User(username=username, email=email, is_admin=admin)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            click.echo(f"{'Admin' if admin else 'Demo user'} account created.")
        else:
            if user.email != email or user.is_admin != admin:
                raise click.ClickException(
                    f"Cannot seed {username}: an incompatible account already exists."
                )
            click.echo(f"{username} already exists; credentials preserved.")
        accounts[username] = user
    inserted = 0
    for key, title, company, resume_file, job_file, days_ago in EXAMPLES:
        if db.session.scalar(
            db.select(ResumeAnalysis).where(ResumeAnalysis.seed_key == key)
        ):
            continue
        analysis = save_analysis(
            accounts["demo_user"].id,
            resume_file,
            (SAMPLE_DIR / resume_file).read_text(encoding="utf-8"),
            (SAMPLE_DIR / job_file).read_text(encoding="utf-8"),
            title,
            company,
            seed_key=key,
            created_at=utcnow() - timedelta(days=days_ago),
        )
        click.echo(f"Sample: {title} — {analysis.match_score}% match")
        inserted += 1
    db.session.commit()
    click.echo(f"Sample analyses inserted: {inserted}. Existing records preserved.")
    click.echo("Local demo accounts: admin / Admin@123 and demo_user / Demo@123")
    click.echo("Change demo passwords before any public deployment.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_database()
