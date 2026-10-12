"""Small persistence and reporting helpers shared by user and admin views."""

from sqlalchemy import func

from .analyzer import analyze_resume
from .extensions import db
from .models import ActivityLog, ResumeAnalysis


def save_analysis(
    user_id,
    filename,
    resume_text,
    job_description,
    job_title="",
    company_name="",
    **extra,
):
    result = analyze_resume(resume_text, job_description)
    analysis = ResumeAnalysis(
        user_id=user_id,
        original_filename=filename,
        resume_text=resume_text,
        job_description=job_description,
        job_title=job_title.strip() or "Untitled role",
        company_name=company_name.strip(),
        match_score=result["match_score"],
        similarity_score=result["similarity_score"],
        matched_keywords=result["matched_keywords"],
        missing_keywords=result["missing_keywords"],
        resume_keywords=result["resume_keywords"],
        job_keywords=result["job_keywords"],
        result=result,
        **extra,
    )
    db.session.add(analysis)
    db.session.add(ActivityLog(user_id=user_id, action="Resume analyzed"))
    return analysis


def analysis_statistics(user_id=None):
    query = db.select(
        func.count(ResumeAnalysis.id),
        func.avg(ResumeAnalysis.match_score),
        func.max(ResumeAnalysis.match_score),
    )
    if user_id is not None:
        query = query.where(ResumeAnalysis.user_id == user_id)
    count, average, best = db.session.execute(query).one()
    return {
        "total": count,
        "average": round(average or 0, 1),
        "best": round(best or 0, 1),
    }


def analysis_report(analysis):
    result = analysis.result
    lines = [
        "RESUME KEYWORD ANALYZER",
        "=" * 45,
        f"Role: {analysis.job_title}",
        f"Company: {analysis.company_name or 'Not specified'}",
        f"Analyzed: {analysis.created_at:%Y-%m-%d %H:%M} UTC",
        f"Resume: {analysis.original_filename}",
        "",
        f"Overall match: {analysis.match_score}% ({analysis.score_state})",
        f"Weighted keyword coverage: {result['keyword_score']}%",
        f"TF-IDF lexical similarity: {analysis.similarity_score}%",
        f"Skills overlap: {result['skills_score'] if result['skills_score'] is not None else 'N/A'}",
        "",
        "MATCHED KEYWORDS",
        ", ".join(analysis.matched_keywords) or "None",
        "",
        "MISSING KEYWORDS",
        ", ".join(analysis.missing_keywords) or "None",
        "",
        "RECOMMENDATIONS",
    ]
    lines.extend(
        f"- {item['title']}: {item['text']}" for item in result["recommendations"]
    )
    lines.extend(
        [
            "",
            "This is an explainable lexical comparison, not a hiring prediction.",
            f"Algorithm version: {result['algorithm_version']}",
        ]
    )
    return "\n".join(lines)
