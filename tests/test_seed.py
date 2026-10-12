from app.extensions import db
from app.models import ResumeAnalysis, User
from seed import seed_database


def test_seed_is_idempotent_and_does_not_reset_passwords(app):
    with app.app_context():
        # Test fixtures contain an admin; remove it for a fresh seed scenario.
        admin = db.session.scalar(db.select(User).where(User.username == "admin"))
        db.session.delete(admin)
        db.session.commit()
        seed_database()
        demo = db.session.scalar(db.select(User).where(User.username == "demo_user"))
        demo.set_password("Changedpass123")
        db.session.commit()
        count = db.session.scalar(db.select(db.func.count(ResumeAnalysis.id)))
        seed_database()
        assert (
            db.session.scalar(db.select(db.func.count(ResumeAnalysis.id))) == count == 4
        )
        assert demo.check_password("Changedpass123")
        assert not demo.check_password("Demo@123")
        seeded_admin = db.session.scalar(
            db.select(User).where(User.username == "admin")
        )
        assert seeded_admin.check_password("Admin@123") and seeded_admin.is_admin
        for analysis in db.session.scalars(db.select(ResumeAnalysis)):
            assert analysis.match_score == analysis.result["match_score"]
