# ERP OS — Malaysia SME ERP Demo

> 马来西亚本土中小企业 ERP 演示系统。支持 e-Invoice (LHDN MyInvois) 全流程、AI 自动化、多仓 6 维库存。

---

## Quick Start

```bash
# 1. Clone & configure
cp .env.example .env
# Edit .env — fill in SECRET_KEY, MYSQL_PASSWORD, ANTHROPIC_API_KEY

# 2. Start all services
docker compose up -d

# 3. Verify
docker compose ps                      # all services healthy
curl http://localhost:8000/health      # {"status":"ok"}
open http://localhost:3000             # React frontend
open http://localhost                  # via nginx
```

## Ports

| Service  | Port | Description          |
|----------|------|----------------------|
| nginx    | 80   | Reverse proxy        |
| backend  | 8000 | FastAPI              |
| frontend | 3000 | Vite dev server      |
| mysql    | 3306 | MySQL 8.0            |
| redis    | 6379 | Redis 7              |

## Demo Accounts (available after Window 03)

| Email              | Password     | Role      |
|--------------------|--------------|-----------|
| admin@demo.my      | Admin@123    | Admin     |
| manager@demo.my    | Manager@123  | Manager   |
| sales@demo.my      | Sales@123    | Sales     |
| purchaser@demo.my  | Purchaser@123| Purchaser |

## Tech Stack

- **Backend**: Python 3.12 · FastAPI 0.115 · SQLAlchemy 2.0 (async) · Alembic · Celery + Redis
- **Frontend**: React 18 · TypeScript 5.4 · Vite 5 · Ant Design Pro
- **Database**: MySQL 8.0 · Redis 7
- **AI**: Anthropic Claude API (OCR / e-Invoice precheck / Dashboard summary)

## Development

```bash
# Backend (local, no Docker)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload

# Frontend (local, no Docker)
cd frontend
npm install
npm run dev
```

## Window Progress

See [`tasks/todo.md`](tasks/todo.md) for the full 21-window development plan.
# erp_os
