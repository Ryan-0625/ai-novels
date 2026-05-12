$env:PYTHONPATH = "e:\VScode(study)\Project\AI-Novels\src"
Set-Location "e:\VScode(study)\Project\AI-Novels"
python -m pytest tests/ -v --cov=src/ai_novels --cov-report=term-missing --cov-report=html:tests/output/coverage_html
