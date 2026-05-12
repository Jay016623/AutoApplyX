# AutoApplyX Development Setup

This document provides exact commands to get the repository running locally.

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | Required |
| Node.js | 18+ | Required for frontend |
| Redis | Optional | Can use fakeredis for testing |

## Quick Start (Backend Only)

```bash
# 1. Navigate to project
cd /workspace/project/AutoApplyX

# 2. Copy environment config
cp .env.example .env

# 3. Install Python dependencies
cd backend
pip install -e ".[dev]"

# 4. Verify backend imports
python -c "from app.main import app; print('OK')"

# 5. Start backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 6. Verify in another terminal
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"2.0.0"}
```

## Quick Start (Frontend)

```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
# Opens at http://localhost:5173
```

## Redis (Optional)

Redis is optional for local development. The system uses fakeredis when Redis is unavailable.

To use real Redis:
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Or install locally and start redis-server
```

Then update `.env`:
```
FAKE_REDIS=0
REDIS_URL=redis://localhost:6379/0
```

## Docker Compose (Full Stack)

```bash
# Build and start all services
docker compose up --build

# Services:
# - Backend: http://localhost:8000
# - Frontend: http://localhost:3000
# - Redis: localhost:6379
# - Worker: (background)
```

## Verification Commands

| Test | Command | Expected |
|------|---------|----------|
| Backend health | `curl http://localhost:8000/health` | `{"status":"ok"}` |
| Swagger docs | `curl http://localhost:8000/docs` | HTML page |
| Database tables | Check `data/db/autoapply.db` exists | File created |
| Frontend build | `cd frontend && npm run build` | `dist/` folder created |

## Troubleshooting

### Port Already in Use
```bash
# Kill existing process
lsof -ti:8000 | xargs kill -9
```

### Import Errors
```bash
# Reinstall dependencies
pip install -e ".[dev]" --force-reinstall
```

### Database Locked
```bash
# Delete SQLite file and recreate
rm data/db/autoapply.db
```

## Environment Variables

Key variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite+aiosqlite:///data/db/autoapply.db | Database connection |
| REDIS_URL | redis://localhost:6379/0 | Redis connection |
| FAKE_REDIS | 1 | Use fakeredis (1) or real Redis (0) |
| ENVIRONMENt | development | development/staging/production |
| LOG_LEVEL | INFO | DEBUG/INFO/WARNING/ERROR |
| APPLY_MODE | review | autonomous/review/batch |
| LLM__OPENAI_API_KEY | (empty) | OpenAI key for AI features |

## Running Tests

```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend tests
cd frontend
npm run test
```