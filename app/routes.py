"""Public pages and user-owned analysis workflows."""

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from .extensions import db
from .forms import AnalyzeForm
from .models import ActivityLog, ResumeAnalysis
from .services import analysis_report, analysis_statistics, save_analysis
from .utils import ExtractionError, extract_resume

main = Blueprint("main", __name__)


def owned_analysis(analysis_id):
    analysis = db.get_or_404(ResumeAnalysis, analysis_id)
    if analysis.user_id != current_user.id and not current_user.is_admin:
        abort(404)
    return analysis


@main.get("/")
def index():
    return render_template("index.html")


@main.get("/about")
def about():
    return render_template("about.html")


@main.get("/dashboard")
@login_required
def dashboard():
    recent = db.session.scalars(
        db.select(ResumeAnalysis)
        .where(ResumeAnalysis.user_id == current_user.id)
        .order_by(ResumeAnalysis.created_at.desc())
        .limit(5)
    ).all()
    trend = db.session.scalars(
        db.select(ResumeAnalysis)
        .where(ResumeAnalysis.user_id == current_user.id)
        .order_by(ResumeAnalysis.created_at.desc())
        .limit(12)
    ).all()[::-1]
    chart = {
        "labels": [a.job_title for a in trend],
        "scores": [a.match_score for a in trend],
    }
    return render_template(
        "dashboard.html",
        stats=analysis_statistics(current_user.id),
        recent=recent,
        chart=chart,
    )


@main.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze():
    form = AnalyzeForm()
    if form.validate_on_submit():
        try:
            filename, text = extract_resume(form.resume.data)
            analysis = save_analysis(
                current_user.id,
                filename,
                text,
                form.job_description.data.strip(),
                form.job_title.data or "",
                form.company_name.data or "",
            )
            db.session.commit()
        except (ExtractionError, ValueError) as error:
            db.session.rollback()
            flash(str(error), "danger")
        else:
            flash("Analysis complete. Your results have been saved.", "success")
            return redirect(url_for("main.result", analysis_id=analysis.id))
    return render_template("analyze.html", form=form)


@main.get("/analysis/<int:analysis_id>")
@login_required
def result(analysis_id):
    analysis = owned_analysis(analysis_id)
    return render_template("result.html", analysis=analysis, report=analysis.result)


@main.get("/analysis/<int:analysis_id>/download")
@login_required
def download(analysis_id):
    analysis = owned_analysis(analysis_id)
    return Response(
        analysis_report(analysis),
        mimetype="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="analysis-{analysis.id}.txt"'
        },
    )


@main.get("/history")
@login_required
def history():
    search = request.args.get("q", "").strip()[:100]
    query = db.select(ResumeAnalysis).where(ResumeAnalysis.user_id == current_user.id)
    if search:
        query = query.where(
            or_(
                ResumeAnalysis.job_title.icontains(search, autoescape=True),
                ResumeAnalysis.company_name.icontains(search, autoescape=True),
            )
        )
    pagination = db.paginate(
        query.order_by(ResumeAnalysis.created_at.desc()), per_page=10, error_out=False
    )
    return render_template("history.html", pagination=pagination, search=search)


@main.post("/analysis/<int:analysis_id>/delete")
@login_required
def delete_analysis(analysis_id):
    analysis = owned_analysis(analysis_id)
    # Admin deletion of other accounts is kept in the explicit admin workflow.
    if analysis.user_id != current_user.id:
        abort(403)
    db.session.delete(analysis)
    db.session.add(ActivityLog(user_id=current_user.id, action="Analysis deleted"))
    db.session.commit()
    flash("Analysis and its extracted text deleted.", "success")
    return redirect(url_for("main.history"))
