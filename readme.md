# Speech-to-Text Platform

Production-grade async transcription API built with Python, FastAPI, PostgreSQL, Redis, Celery, and faster-whisper.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│    Nginx    │────▶│   FastAPI   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                    ┌───────────────────────────┼───────────────────────┐
                    │                           │                       │
             ┌──────▼──────┐           ┌────────▼──────┐      ┌────────▼──────┐
             │  PostgreSQL │           │     Redis     │      │    MinIO/S3   │
             │  (primary   │           │  (cache +     │      │   (uploads)   │
             │   storage)  │           │   queue +     │      └───────────────┘
             └─────────────┘           │   pub/sub)    │
                                       └───────┬───────┘
                                               │
                                       ┌───────▼───────┐
                                       │ Celery Worker │
                                       │ faster-whisper│
                                       └───────────────┘
```

## Features

| Feature | Status |
|---|---|
| JWT + API Key auth | ✅ |
| Async transcription (faster-whisper) | ✅ |
| Word-level timestamps | ✅ |
| SRT / VTT / TXT export | ✅ |
| Full-text search | ✅ |
| WebSocket live updates | ✅ |
| Webhook callbacks (HMAC signed) | ✅ |
| S3 / MinIO storage | ✅ |
| Rate limiting | ✅ |
| Usage quotas | ✅ |
| Transcript versioning | ✅ |
| Multi-tenancy (organizations) | ✅ |
| Cost tracking | ✅ |
| Admin analytics | ✅ |
| Prometheus metrics | ✅ |
| Audit logging | ✅ |
| Celery Beat scheduled tasks | ✅ |
| Docker + Nginx production deploy | ✅ |

## Quick Start

```powershell
# 1. Clone and enter project
git clone <repo>
cd speech-to-text-platform

# 2. Create environment
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# 3. Configure environment
Copy-Item .env.example .env
# Edit .env — set SECRET_KEY at minimum

# 4. Start infrastructure
docker-compose up postgres redis minio -d

# 5. Run migrations
alembic upgrade head

# 6. Start API
uvicorn app.main:app --reload

# 7. Start worker (new terminal)
celery -A app.workers.celery_app worker --loglevel=info

# 8. Start beat scheduler (new terminal)
celery -A app.workers.celery_app beat --loglevel=info
```

Visit http://localhost:8000/docs for interactive API docs.

## API Reference

### Authentication

All protected endpoints require one of:
- `Authorization: Bearer <jwt_token>`
- `X-API-Key: stt_<key>`

### Core Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register user |
| POST | `/api/v1/auth/login` | Login, get tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Current user profile |
| POST | `/api/v1/transcriptions/upload` | Upload audio, create job |
| GET | `/api/v1/transcriptions/` | List jobs (paginated) |
| GET | `/api/v1/transcriptions/{id}` | Job status + transcript |
| POST | `/api/v1/transcriptions/{id}/retranscribe` | Re-run with new model |
| GET | `/api/v1/transcriptions/{id}/history` | Version history |
| GET | `/api/v1/transcriptions/{id}/export` | Export SRT/VTT/TXT |
| GET | `/api/v1/transcriptions/search` | Full-text search |
| POST | `/api/v1/webhooks/` | Register webhook |
| GET | `/api/v1/api-keys/` | List API keys |
| POST | `/api/v1/api-keys/` | Create API key |
| GET | `/api/v1/admin/analytics/stats` | Platform stats (admin) |
| GET | `/api/v1/admin/costs/dashboard` | Cost dashboard (admin) |
| WS | `/api/v1/ws/jobs?token=<jwt>` | Live job updates |

## Environment Variables

See `.env.example` for full reference.

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | JWT signing key (min 32 chars) | required |
| `WHISPER_MODEL_SIZE` | Model: tiny/base/small/medium/large-v3 | `base` |
| `WHISPER_DEVICE` | cpu or cuda | `cpu` |
| `STORAGE_BACKEND` | local or s3 | `local` |
| `QUOTA_ENFORCEMENT_ENABLED` | Enforce monthly limits | `true` |
| `DEFAULT_MONTHLY_MINUTES` | Free tier minutes | `300` |

## CLI

```powershell
python -m app.cli --help
python -m app.cli create-admin admin@example.com
python -m app.cli list-users
python -m app.cli reset-quota user@example.com
python -m app.cli stats
```

## Testing

```powershell
# Unit + API tests
pytest tests/ -v --cov=app --cov-report=term-missing

# Integration tests (requires running worker)
pytest tests/integration/ -v --integration

# Load tests
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

## Production Deployment

```powershell
# Build production image
docker build -f deploy/Dockerfile.prod -t stt-platform:prod .

# Start full production stack
docker-compose -f deploy/docker-compose.prod.yml up -d

# Run migrations
docker-compose -f deploy/docker-compose.prod.yml exec api alembic upgrade head
```

## Design Decisions

**Why faster-whisper over OpenAI Whisper API?**
Zero cost, runs locally, no data leaves your infrastructure, configurable model sizes.

**Why Celery + Redis over FastAPI BackgroundTasks?**
BackgroundTasks die if the process restarts. Celery persists jobs to Redis, supports retries, and scales horizontally.

**Why PostgreSQL full-text search over Elasticsearch?**
No extra service to manage. PostgreSQL tsvector with GIN index handles millions of transcripts efficiently for a single-tenant deployment.

**Why modular monolith over microservices?**
Microservices multiply operational complexity for a solo developer. This architecture has clean domain boundaries ready to extract if scale demands it.

## License

MIT