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
│   ├── alembic/
│   ├── scripts/
│   └── tests/
├── frontend/
└── docker-compose.yml
```

## Run with Docker Compose

1. Initialize local environment file:

   ```bash
   make init-env
   ```

2. Build and start:

   ```bash
   make up
   ```

3. Apply migrations:

   ```bash
   make migrate
   ```

4. Seed mock data:

   ```bash
   make seed
   ```

5. Verify:

- Frontend: http://localhost:13000
- Backend: http://localhost:18000
- Dummy API endpoint: http://localhost:18000/api/v1/ping
- Swagger docs: http://localhost:18000/docs
- OAuth token endpoint: `POST /api/v1/auth/token`

6. Stop services:

   ```bash
   make down
   ```

## Run backend tests

```bash
make test
```

## Makefile shortcuts

Use `make help` to see all available commands.

```bash
make init-env
make up
make migrate
make seed
make test
make down
```

## Login test users

Seed command creates:

- `admin@example.com` / `admin123`
- `teacher@example.com` / `teacher123`
- `student@example.com` / `student123`

Use the frontend login form at `http://localhost:13000` to verify authenticated session and the dummy home page.
