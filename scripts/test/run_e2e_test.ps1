# AI-Novels End-to-End Test Runner
$env:PYTHONPATH = "e:\VScode(study)\Project\AI-Novels\src"

cd "e:\VScode(study)\Project\AI-Novels"

Write-Host "Starting AI-Novels End-to-End Test..." -ForegroundColor Cyan
Write-Host "="*60

python test_novel_generation.py

$exitCode = $LASTEXITCODE

Write-Host "="*60
if ($exitCode -eq 0) {
    Write-Host "Test completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Test failed with exit code: $exitCode" -ForegroundColor Red
}
