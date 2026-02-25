# Mattilda Take-Home Project Setup

Starter environment for a take-home exercise with:

- Backend: Python + FastAPI
- Database: PostgreSQL + SQLAlchemy ORM
- Cache: Redis
- Frontend: React (Vite)
- Containers: Docker + Docker Compose
- Python dependency management: `uv` + `pyproject.toml`
- Tests: `pytest` for backend
- API docs: OpenAPI/Swagger via FastAPI
- Directory style: Hexagonal architecture-inspired layering

## Project structure

```text
.
├── backend/
│   ├── app/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── interfaces/
│   └── tests/
├── frontend/
└── docker-compose.yml
```

## Run with Docker Compose

1. Copy env file:

   ```bash
   cp .env.example .env
   ```

2. Build and start:

   ```bash
   docker compose up --build -d
   ```

3. Verify:

- Frontend: http://localhost:13000
- Backend: http://localhost:18000
- Dummy API endpoint: http://localhost:18000/api/v1/ping
- Swagger docs: http://localhost:18000/docs

4. Stop services:

   ```bash
   docker compose down
   ```

## Run backend tests

```bash
docker compose run --rm backend uv run pytest
```
