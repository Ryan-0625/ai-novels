#!/bin/bash
# AI-Novels Phase 1 Startup Script (macOS/Linux)
# Run from project root: bash scripts/start_phase1.sh

set -e

echo "=== AI-Novels Phase 1 Startup ==="

# Step 1: Dependencies
echo "[1/4] Checking dependencies..."
python3 -c "import fastapi; import uvicorn; import sqlalchemy; import alembic; import jwt; import bcrypt" 2>/dev/null || {
    echo "[WARN] Installing missing dependencies..."
    pip3 install --break-system-packages bcrypt pyjwt redis alembic sqlmodel asyncpg 2>/dev/null || pip3 install bcrypt pyjwt redis alembic sqlmodel asyncpg
}
echo "[OK] Dependencies ready"

# Step 2: Database check
echo "[2/4] Checking PostgreSQL..."
python3 -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def check():
    try:
        engine = create_async_engine('postgresql+asyncpg://ai_novels:ai_novels_pass@localhost:33432/ai_novels')
        async with engine.connect() as c:
            await c.execute(text('SELECT 1'))
        print('[OK] PostgreSQL connected')
    except Exception as e:
        print(f'[WARN] DB unavailable: {e}')
asyncio.run(check())
" 2>&1 || echo "[INFO] Create DB: createdb ai_novels"

# Step 3: Migration
echo "[3/4] Running Alembic migrations..."
alembic upgrade head 2>/dev/null || {
    echo "[INFO] Running initial migration..."
    alembic revision --autogenerate -m "initial_schema" 2>/dev/null
    alembic upgrade head
}
echo "[OK] Migration complete"

# Step 4: Start
echo "[4/4] Starting server..."
echo "  API:  http://localhost:33100"
echo "  Docs: http://localhost:33100/docs"
echo "  Press Ctrl+C to stop"
echo "================================"

uvicorn src.ai_novels.api.main:app --host 0.0.0.0 --port 33100 --reload
