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
- Multi-tenant model: School-based isolation with PostgreSQL RLS
- Student model: many-to-many user/student and student/school associations

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
- Schools endpoint: `GET /api/v1/schools`

6. Stop services:

   ```bash
   make down
   ```

## Run backend tests

```bash
make test
```

Tests run locally (from your host machine) with `uv`, and use a real PostgreSQL container via `testcontainers`.
Ensure both `uv` and Docker are available locally before running tests.

## Code quality checks

```bash
make lint
make format
make typecheck
make quality
```

- `make lint`: runs `ruff check` on backend `app` and `tests`.
- `make format`: runs `ruff format` on backend `app` and `tests`.
- `make typecheck`: runs `mypy` on backend `app`.
- `make quality`: runs lint + typecheck + full tests.

### Local test prerequisites

1. Install `uv` (if not installed):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Reload your shell (or open a new terminal):

   ```bash
   source ~/.zshrc
   ```

3. Verify `uv`:

   ```bash
   uv --version
   ```

4. Ensure Docker Desktop (or Docker daemon) is running before `make test`.

## Tenant flow

- User logs in via `POST /api/v1/auth/token`.
- Frontend fetches `GET /api/v1/users/me` and receives school memberships with per-school roles.
- Frontend selects one active school and sends `X-School-Id` in school-scoped requests.
- Backend validates membership and school roles and binds tenant context for PostgreSQL RLS.
- Soft deletes are applied to `users`, `schools`, and `students` (`deleted_at`).

## School endpoints

- `GET /api/v1/schools`
- Returns only schools where the user has memberships.
- `POST /api/v1/schools` (school `admin` in active school)
- Creating a school auto-links the creator as `admin` in that new school.
- `GET /api/v1/schools/{school_id}` (requires matching `X-School-Id`)
- `PUT /api/v1/schools/{school_id}` (requires school role: `admin`)
- `DELETE /api/v1/schools/{school_id}` (requires school role: `admin`, soft delete)
- `POST /api/v1/schools/{school_id}/users` (associate user+role to school, admin only)
- `DELETE /api/v1/schools/{school_id}/users/{user_id}` (deassociate user from school, admin only)

## Student endpoints

- `GET /api/v1/students` (role-aware in active school: admin sees all, non-admin sees only own associated students)
- `POST /api/v1/students` (create student, admin only; auto-associates student to active school)
- `GET /api/v1/students/{student_id}` (admin only)
- `PUT /api/v1/students/{student_id}` (admin only)
- `DELETE /api/v1/students/{student_id}` (soft delete, admin only)
- `POST /api/v1/students/{student_id}/users` and `DELETE /.../users/{user_id}` (associate/deassociate user-student, admin only)
- `POST /api/v1/students/{student_id}/schools` and `DELETE /.../schools/{school_id}` (associate/deassociate student-school, admin only)

Frontend admin association actions for user-school and student-school use the active school session (`X-School-Id`) as context.

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

And also creates:

- `north-high` and `south-high` schools
- Per-school memberships and roles for seeded users
- Sample students linked to users and schools

Use the frontend login form at `http://localhost:13000` to verify authenticated session and the dummy home page.
