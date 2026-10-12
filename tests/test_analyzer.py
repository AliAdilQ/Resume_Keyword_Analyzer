import pytest

from app.analyzer import (
    analyze_resume,
    detect_skills,
    extract_keywords,
    preprocess_text,
    similarity_score,
)


def test_preprocessing_removes_noise_and_lemmatizes():
    tokens = preprocess_text("The developers built applications, and running services!")
    assert "the" not in tokens and "and" not in tokens
    assert "application" in tokens
    assert "run" in tokens


def test_technical_keywords_are_preserved():
    tokens = preprocess_text(
        "C++ C# .NET Node.js React.js machine learning data science"
    )
    assert set(
        ["c++", "c#", ".net", "node.js", "react", "machine learning", "data science"]
    ) <= set(tokens)


def test_skill_aliases_and_boundaries():
    skills = {
        s
        for values in detect_skills(
            "React.js Nodejs PostgreSQL scikit learn C++ C# .NET"
        ).values()
        for s in values
    }
    assert {
        "React",
        "Node.js",
        "PostgreSQL",
        "Scikit-learn",
        "C++",
        "C#",
        ".NET",
    } <= skills
    assert "Java" not in {
        s for values in detect_skills("JavaScript").values() for s in values
    }


def test_dynamic_keywords_go_beyond_dictionary():
    assert "forecast" in extract_keywords(
        "Demand forecasting optimizes supply chains. Demand forecasting improves planning."
    )


def test_incidental_skill_pairs_and_demo_disclaimers_are_excluded():
    keywords = extract_keywords(
        "Python SQL Git. Python SQL Git. This example is fictional."
    )
    assert "python" in keywords and "sql" in keywords and "git" in keywords
    assert "python sql" not in keywords and "sql git" not in keywords
    assert "fictional" not in keywords


def test_similarity_identical_and_unrelated():
    assert similarity_score("Python Flask SQL", "Python Flask SQL") == pytest.approx(
        100
    )
    assert similarity_score("Python Flask SQL", "gardening flowers soil") == 0
    assert similarity_score("", "Python") == 0


@pytest.mark.parametrize(
    "resume,job",
    [
        ("Python Flask SQL", "Python Flask SQL"),
        ("gardening flowers soil", "Python Flask SQL"),
        ("Python Git SQL", "Python Docker Kubernetes AWS"),
    ],
)
def test_score_boundaries(resume, job):
    result = analyze_resume(resume, job)
    assert 0 <= result["match_score"] <= 100
    assert set(result["matched_keywords"]).isdisjoint(result["missing_keywords"])
    assert set(result["matched_keywords"] + result["missing_keywords"]) == set(
        result["job_keywords"]
    )


def test_identical_documents_score_100():
    assert analyze_resume("Python Flask SQL", "Python Flask SQL")["match_score"] == 100


def test_weighted_formula():
    result = analyze_resume("Python Flask Git", "Python Flask SQL Docker")
    expected = (
        0.5 * result["keyword_score"]
        + 0.3 * result["similarity_score"]
        + 0.2 * result["skills_score"]
    )
    assert result["match_score"] == pytest.approx(expected, abs=0.11)
    assert "Docker" in result["missing_skills"]


def test_no_known_skills_redistributes_weight():
    result = analyze_resume(
        "forecasting planning reporting", "forecasting planning logistics"
    )
    assert result["skills_score"] is None
    assert result["weights"] == {"keywords": 70, "similarity": 30, "skills": 0}
    assert result["match_score"] == pytest.approx(
        0.7 * result["keyword_score"] + 0.3 * result["similarity_score"], abs=0.1
    )


def test_aliases_match_consistently():
    result = analyze_resume(
        "Reactjs nodejs dotnet sklearn", "React.js Node.js .NET Scikit-learn"
    )
    assert not result["missing_skills"]
    assert result["match_score"] == 100


def test_empty_meaningful_content():
    with pytest.raises(ValueError):
        analyze_resume("the and a of", "Python Flask")


def test_recommendations_are_honest():
    result = analyze_resume("Python development", "Python Flask Docker development")
    assert "Never add skills" in result["recommendations"][0]["text"]
    assert any("measurable" in item["title"] for item in result["recommendations"])
