$env:PYTHONPATH = "e:\VScode(study)\Project\AI-Novels\src"
Set-Location "e:\VScode(study)\Project\AI-Novels"
python -m pytest tests/ -v --cov=src/deepnovel --cov-report=term-missing --cov-report=html:tests/output/coverage_html
