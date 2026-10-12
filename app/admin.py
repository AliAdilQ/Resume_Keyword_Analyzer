"""Administrative metrics, searchable accounts, and analysis moderation."""

from datetime import date, datetime, time, timedelta
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from .extensions import db
from .models import ActivityLog, ResumeAnalysis, User, utcnow
from .services import analysis_statistics

admin = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@admin.get("/")
@admin_required
def index():
    return redirect(url_for("admin.dashboard"))


@admin.get("/dashboard")
@admin_required
def dashboard():
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stats = analysis_statistics()
    stats["users"] = db.session.scalar(db.select(func.count(User.id)))
    stats["today"] = db.session.scalar(
        db.select(func.count(ResumeAnalysis.id)).where(
            ResumeAnalysis.created_at >= today
        )
    )
    recent_users = db.session.scalars(
        db.select(User).order_by(User.created_at.desc()).limit(5)
    ).all()
    recent_analyses = db.session.scalars(
        db.select(ResumeAnalysis).order_by(ResumeAnalysis.created_at.desc()).limit(5)
    ).all()
    activity = db.session.scalars(
        db.select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(5)
    ).all()
    rows = db.session.execute(
        db.select(func.date(ResumeAnalysis.created_at), func.count(ResumeAnalysis.id))
        .where(ResumeAnalysis.created_at >= today - timedelta(days=6))
        .group_by(func.date(ResumeAnalysis.created_at))
    ).all()
    counts = {str(day): count for day, count in rows}
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    chart = {
        "labels": [day.strftime("%b %d") for day in days],
        "counts": [counts.get(day.strftime("%Y-%m-%d"), 0) for day in days],
    }
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_users=recent_users,
        recent_analyses=recent_analyses,
        activity=activity,
        chart=chart,
    )


@admin.get("/users")
@admin_required
def users():
    search = request.args.get("q", "").strip()[:100]
    query = (
        db.select(User, func.count(ResumeAnalysis.id).label("analysis_count"))
        .outerjoin(ResumeAnalysis)
        .group_by(User.id)
    )
    if search:
        query = query.where(
            or_(
                User.username.icontains(search, autoescape=True),
                User.email.icontains(search, autoescape=True),
            )
        )
    # Pagination's unique/scalars behavior doesn't preserve aggregate tuples.
    page = max(1, request.args.get("page", 1, type=int))
    count = db.session.scalar(db.select(func.count()).select_from(query.subquery()))
    rows = db.session.execute(
        query.order_by(User.created_at.desc()).offset((page - 1) * 15).limit(15)
    ).all()
    return render_template(
        "admin/users.html",
        rows=rows,
        search=search,
        page=page,
        pages=max(1, (count + 14) // 15),
        total=count,
    )


@admin.get("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = db.get_or_404(User, user_id)
    analyses = db.paginate(
        db.select(ResumeAnalysis)
        .where(ResumeAnalysis.user_id == user.id)
        .order_by(ResumeAnalysis.created_at.desc()),
        per_page=10,
        error_out=False,
    )
    return render_template(
        "admin/user_detail.html",
        user=user,
        stats=analysis_statistics(user.id),
        pagination=analyses,
    )


@admin.post("/users/<int:user_id>/toggle")
@admin_required
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own administrator account.", "warning")
    elif user.is_admin:
        flash("Administrator accounts are protected from deactivation here.", "warning")
    else:
        user.is_active = not user.is_active
        db.session.add(
            ActivityLog(
                user_id=current_user.id,
                action=f"Account {user.id} {'activated' if user.is_active else 'deactivated'}",
            )
        )
        db.session.commit()
        flash(f"Account {'activated' if user.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.users"))


@admin.get("/analyses")
@admin_required
def analyses():
    query = db.select(ResumeAnalysis)
    search = request.args.get("q", "").strip()[:100]
    if search:
        query = query.where(
            or_(
                ResumeAnalysis.job_title.icontains(search, autoescape=True),
                ResumeAnalysis.company_name.icontains(search, autoescape=True),
            )
        )
    for parameter, operator in (("min_score", "min"), ("max_score", "max")):
        value = request.args.get(parameter, "").strip()
        if value:
            try:
                score = float(value)
                if not 0 <= score <= 100:
                    raise ValueError
                query = query.where(
                    ResumeAnalysis.match_score >= score
                    if operator == "min"
                    else ResumeAnalysis.match_score <= score
                )
            except ValueError:
                flash("Score filters must be numbers from 0 to 100.", "warning")
    for parameter in ("from_date", "to_date"):
        value = request.args.get(parameter, "").strip()
        if value:
            try:
                day = datetime.combine(date.fromisoformat(value), time.min)
                query = query.where(
                    ResumeAnalysis.created_at >= day
                    if parameter == "from_date"
                    else ResumeAnalysis.created_at < day + timedelta(days=1)
                )
            except (ValueError, OverflowError):
                flash("Choose a valid date for the date filter.", "warning")
    pagination = db.paginate(
        query.order_by(ResumeAnalysis.created_at.desc()), per_page=10, error_out=False
    )
    return render_template("admin/analyses.html", pagination=pagination)


@admin.post("/analyses/<int:analysis_id>/delete")
@admin_required
def delete_analysis(analysis_id):
    analysis = db.get_or_404(ResumeAnalysis, analysis_id)
    db.session.delete(analysis)
    db.session.add(
        ActivityLog(
            user_id=current_user.id,
            action=f"Analysis {analysis_id} removed by administrator",
        )
    )
    db.session.commit()
    flash("Analysis deleted.", "success")
    return redirect(url_for("admin.analyses"))
