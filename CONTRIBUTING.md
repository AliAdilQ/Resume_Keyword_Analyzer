# Contributing

Thanks for contributing to Resume Keyword Analyzer.

1. Fork [AliAdilQ/Resume_Keyword_Analyzer](https://github.com/AliAdilQ/Resume_Keyword_Analyzer) and clone your fork.
2. Create a branch: `git checkout -b feature/your-change`.
3. Use Python 3.11+ and follow the virtual environment, dependency installation, and demo setup steps in [README.md](README.md).
4. Make a focused change. Keep NLP, extraction, persistence, and routes in their respective modules. Use PEP 8, meaningful names, and useful docstrings.
5. Run `python -m pytest -q`. Add meaningful tests for changed behavior, especially authorization, privacy, extraction, or scoring.
6. For UI changes, verify desktop and mobile layouts and keyboard access. Use the optional browser script to refresh genuine screenshots when the visible interface changes.
7. Update documentation if behavior, configuration, or the scoring formula changes. Explain any algorithm version change.
8. Commit: `git add .` and `git commit -m "Describe the change"`.
9. Push: `git push origin feature/your-change`.
10. Open a pull request explaining the problem, resulting behavior, and validation.

Never commit environment secrets, real resumes, personal data, live databases, or virtual environments. Use fictional fixtures. Keep third-party notices with vendored assets. Recommendations must encourage honest resume content, and scoring claims must describe the actual implementation.

Report reproducible bugs with your Python version, operating system, steps, and a fictional example. Avoid posting private resume text or credentials in issues.
