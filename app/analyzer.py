"""Deterministic NLP: technical aliases, lookup lemmas, and lexical TF-IDF.

No model download or network call is needed at analysis time. A match score is
an explainable text comparison, not a prediction of hiring or ATS outcomes.
"""

import re
import unicodedata
from collections import Counter
from functools import lru_cache

import spacy
from nltk.tokenize import RegexpTokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from spacy.lang.en.stop_words import STOP_WORDS

# Canonical spelling makes equivalent technology names compare consistently.
SKILLS = {
    "Programming languages": {
        "Python": ["python"],
        "Java": ["java"],
        "JavaScript": ["javascript", "js"],
        "TypeScript": ["typescript"],
        "C++": ["c++"],
        "C#": ["c#", "c sharp"],
        "PHP": ["php"],
        "R": ["r"],
        "SQL": ["sql", "structured query language"],
        "Go": ["golang", "go"],
        "Rust": ["rust"],
        "Ruby": ["ruby"],
    },
    "Frameworks": {
        "Flask": ["flask"],
        "Django": ["django"],
        "React": ["react", "react.js", "reactjs"],
        "Angular": ["angular", "angularjs"],
        "Vue": ["vue", "vue.js", "vuejs"],
        "FastAPI": ["fastapi"],
        "Laravel": ["laravel"],
        "Node.js": ["node.js", "nodejs", "node js"],
        ".NET": [".net", "dotnet"],
        "Spring": ["spring", "spring boot"],
    },
    "Machine learning": {
        "Machine learning": ["machine learning", "ml"],
        "Deep learning": ["deep learning"],
        "TensorFlow": ["tensorflow"],
        "PyTorch": ["pytorch"],
        "Scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
        "NLP": ["nlp", "natural language processing"],
        "Computer vision": ["computer vision"],
        "spaCy": ["spacy"],
        "NLTK": ["nltk"],
    },
    "Data skills": {
        "Pandas": ["pandas"],
        "NumPy": ["numpy"],
        "Matplotlib": ["matplotlib"],
        "Data analysis": ["data analysis", "data analytics"],
        "Data science": ["data science"],
        "Data mining": ["data mining"],
        "Power BI": ["power bi", "powerbi"],
        "Tableau": ["tableau"],
        "Excel": ["excel"],
        "PostgreSQL": ["postgresql", "postgres"],
        "SQLite": ["sqlite", "sqlite3"],
        "ETL": ["etl"],
        "Statistics": ["statistics", "statistical"],
    },
    "Tools & platforms": {
        "Git": ["git"],
        "GitHub": ["github"],
        "Docker": ["docker"],
        "Linux": ["linux"],
        "AWS": ["aws", "amazon web services"],
        "Azure": ["azure"],
        "Kubernetes": ["kubernetes", "k8s"],
        "CI/CD": ["ci/cd", "ci cd", "continuous integration"],
        "REST API": ["rest api", "restful", "rest apis"],
        "Testing": ["testing", "pytest", "unit tests", "unit testing"],
    },
}
BACKGROUND_WORDS = {
    "resume",
    "curriculum",
    "vitae",
    "email",
    "phone",
    "address",
    "com",
    "example",
    "fictional",
    "job",
    "role",
    "candidate",
    "company",
    "experience",
    "year",
    "work",
    "working",
    "team",
    "looking",
    "seek",
    "seeking",
    "required",
    "requirement",
    "preferred",
    "qualification",
    "responsibility",
    "include",
    "including",
    "ability",
    "strong",
    "excellent",
    "knowledge",
    "skill",
    "education",
    "degree",
    "bachelor",
    "university",
    "benefit",
    "apply",
    "opportunity",
    "equal",
    "employer",
    "salary",
    "position",
    "join",
    "proficiency",
    "proficient",
    "familiar",
    "familiarity",
    "understanding",
}
TOKENIZER = RegexpTokenizer(r"(?:\.net|[a-z][a-z0-9]*(?:[.+#/-][a-z0-9+#]+)*|c\+\+|c#)")


def clean_text(text):
    """Normalize Unicode and case while retaining technical punctuation."""
    return unicodedata.normalize("NFKC", text).lower().replace("\x00", " ")


@lru_cache(maxsize=1)
def language_pipeline():
    pipeline = spacy.blank("en")
    pipeline.add_pipe("lemmatizer", config={"mode": "lookup"})
    pipeline.initialize()
    return pipeline


def alias_pattern(alias):
    return re.compile(r"(?<![\w.+#])" + re.escape(alias) + r"(?![\w+#])", re.I)


def detect_skills(text):
    """Extract known skills with boundaries, preserving names like C++ and .NET."""
    normalized = clean_text(text)
    categories = {}
    for category, skills in SKILLS.items():
        found = [
            name
            for name, aliases in skills.items()
            if any(alias_pattern(alias).search(normalized) for alias in aliases)
        ]
        if found:
            categories[category] = found
    return categories


def canonicalize(text):
    normalized = clean_text(text)
    replacements = [
        (alias, name.lower())
        for skills in SKILLS.values()
        for name, aliases in skills.items()
        for alias in aliases
    ]
    for alias, name in sorted(
        replacements, key=lambda item: len(item[0]), reverse=True
    ):
        normalized = alias_pattern(alias).sub(name, normalized)
    return normalized


def preprocess_text(text):
    """NLTK tokenization and spaCy lookup lemmatization, with protected skills."""
    normalized = canonicalize(text)
    # Protect complete technical phrases from stop-word removal and lemmatization.
    phrases = [name.lower() for skills in SKILLS.values() for name in skills]
    protected = {}
    for index, phrase in enumerate(sorted(phrases, key=len, reverse=True)):
        marker = f"skilltoken{index}"
        pattern = alias_pattern(phrase)
        if pattern.search(normalized):
            normalized = pattern.sub(marker, normalized)
            protected[marker] = phrase
    tokens = TOKENIZER.tokenize(normalized)
    lemmas = language_pipeline()(" ".join(tokens))
    cleaned = []
    for token in lemmas:
        if token.text in protected:
            cleaned.append(protected[token.text])
            continue
        lemma = token.lemma_.lower()
        if (
            len(lemma) > 1
            and lemma.isalpha()
            and lemma not in STOP_WORDS
            and lemma not in BACKGROUND_WORDS
        ):
            cleaned.append(lemma)
    return cleaned


def text_features(text):
    tokens = preprocess_text(text)
    return set(tokens) | {f"{a} {b}" for a, b in zip(tokens, tokens[1:])}


def similarity_score(resume_text, job_description):
    """Cosine similarity of pair-fitted unigram/bigram TF-IDF, on a 0–100 scale."""
    if not preprocess_text(resume_text) or not preprocess_text(job_description):
        return 0.0
    vectorizer = TfidfVectorizer(
        tokenizer=preprocess_text,
        token_pattern=None,
        lowercase=False,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    vectors = vectorizer.fit_transform([resume_text, job_description])
    return round(float(cosine_similarity(vectors[0], vectors[1])[0, 0]) * 100, 2)


def extract_keywords(text, limit=24):
    """All recognized skills plus data-driven TF-IDF terms from this document.

    Single-document TF-IDF ranks frequency-normalized tokens. Dynamic bigrams
    must recur, and adjacent dictionary skills are excluded as incidental pairs.
    """
    tokens = preprocess_text(text)
    if not tokens:
        return []
    vectorizer = TfidfVectorizer(
        tokenizer=preprocess_text,
        token_pattern=None,
        lowercase=False,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform([text])
    terms = vectorizer.get_feature_names_out()
    scores = matrix.toarray()[0]
    counts = Counter(tokens)
    counts.update(f"{a} {b}" for a, b in zip(tokens, tokens[1:]))
    known = [name.lower() for names in detect_skills(text).values() for name in names]
    skill_pairs = {f"{first} {second}" for first in known for second in known}
    dynamic = [
        str(terms[i])
        for i in sorted(range(len(terms)), key=lambda i: (-scores[i], terms[i]))
        if terms[i] not in known
        and terms[i] not in skill_pairs
        and (" " not in terms[i] or counts[terms[i]] >= 2)
    ]
    return list(dict.fromkeys(known + dynamic[:limit]))


def keyword_frequency(text, keywords):
    tokens = preprocess_text(text)
    counts = Counter(tokens)
    counts.update(f"{a} {b}" for a, b in zip(tokens, tokens[1:]))
    return {keyword: counts[keyword] for keyword in keywords}


def analyze_resume(resume_text, job_description):
    """Build an explainable, JSON-serializable comparison report."""
    resume_keywords = extract_keywords(resume_text)
    job_keywords = extract_keywords(job_description)
    if not resume_keywords or not job_keywords:
        raise ValueError(
            "Both documents must contain meaningful English words or technical skills."
        )
    resume_skills = detect_skills(resume_text)
    job_skills = detect_skills(job_description)
    resume_skill_set = {skill for skills in resume_skills.values() for skill in skills}
    job_skill_set = {skill for skills in job_skills.values() for skill in skills}
    features = text_features(resume_text)
    matched = [keyword for keyword in job_keywords if keyword in features]
    missing = [keyword for keyword in job_keywords if keyword not in features]
    matched_skills = sorted(resume_skill_set & job_skill_set)
    missing_skills = sorted(job_skill_set - resume_skill_set)
    job_frequency = keyword_frequency(job_description, job_keywords)
    technical = {skill.lower() for skill in job_skill_set}
    # Known job skills receive twice the weight; repeated terms get a capped boost.
    weights = {
        key: (2 if key in technical else 1)
        * (1 + min(job_frequency[key] - 1, 2) * 0.25)
        for key in job_keywords
    }
    keyword_score = 100 * sum(weights[key] for key in matched) / sum(weights.values())
    similarity = similarity_score(resume_text, job_description)
    skill_score = (
        100 * len(matched_skills) / len(job_skill_set) if job_skill_set else None
    )
    # When no recognized skills occur, redistribute their 20% to keyword coverage.
    overall = (
        0.5 * keyword_score + 0.3 * similarity + 0.2 * skill_score
        if skill_score is not None
        else 0.7 * keyword_score + 0.3 * similarity
    )
    frequencies = keyword_frequency(resume_text, resume_keywords)
    top_frequency = sorted(frequencies.items(), key=lambda pair: (-pair[1], pair[0]))[
        :10
    ]
    comparison_keywords = job_keywords[:10]
    resume_job_frequency = keyword_frequency(resume_text, comparison_keywords)
    word_count = len(re.findall(r"\b[\w+#.]+\b", resume_text))
    tokens = preprocess_text(resume_text)
    recommendations = []
    if missing_skills:
        recommendations.append(
            {
                "title": "Make relevant skills visible",
                "text": f"If you have experience with {', '.join(missing_skills[:5])}, describe where you used it. Never add skills you cannot substantiate.",
            }
        )
    if missing:
        recommendations.append(
            {
                "title": "Connect your experience to the role",
                "text": f"Review these job terms: {', '.join(missing[:7])}. Use the employer's terminology where it accurately describes your work.",
            }
        )
    if not re.search(
        r"\b\d+(?:\.\d+)?\s*(?:%|percent|users|hours|revenue|projects|customers)\b|\b\d+%",
        resume_text,
        re.I,
    ):
        recommendations.append(
            {
                "title": "Show measurable impact",
                "text": "Add verified outcomes to your experience bullets, such as time saved, users served, or an improvement percentage.",
            }
        )
    if not re.search(r"\b(?:skills|technologies|toolkit)\b", resume_text, re.I):
        recommendations.append(
            {
                "title": "Make your skills easy to scan",
                "text": "Add a concise Skills section grouping technologies you have used in projects or work.",
            }
        )
    if word_count < 200:
        recommendations.append(
            {
                "title": "Give your experience more context",
                "text": "This resume is brief. Add relevant projects, responsibilities, and outcomes while keeping it focused.",
            }
        )
    recommendations.append(
        {
            "title": "Keep the final review human",
            "text": "Check clarity, spelling, and evidence for every claim. This lexical score is a comparison aid, not an ATS certification or hiring prediction.",
        }
    )
    return {
        "match_score": round(min(100, max(0, overall)), 1),
        "similarity_score": similarity,
        "keyword_score": round(keyword_score, 1),
        "skills_score": round(skill_score, 1) if skill_score is not None else None,
        "weights": {
            "keywords": 50 if skill_score is not None else 70,
            "similarity": 30,
            "skills": 20 if skill_score is not None else 0,
        },
        "resume_keywords": resume_keywords,
        "job_keywords": job_keywords,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "resume_skills": resume_skills,
        "job_skills": job_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "keyword_frequency": frequencies,
        "job_keyword_frequency": job_frequency,
        "top_frequency": {
            "labels": [k for k, _ in top_frequency],
            "values": [v for _, v in top_frequency],
        },
        "comparison": {
            "labels": comparison_keywords,
            "resume": [resume_job_frequency[k] for k in comparison_keywords],
            "job": [job_frequency[k] for k in comparison_keywords],
        },
        "statistics": {
            "word_count": word_count,
            "unique_keywords": len(resume_keywords),
            "detected_skills": len(resume_skill_set),
            "keyword_density": round(
                100
                * sum(t in set(resume_keywords) for t in tokens)
                / max(1, word_count),
                1,
            ),
        },
        "recommendations": recommendations,
        "algorithm_version": "1.0",
    }
