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
- `GET /api/v1/students/{student_id}` (visible when admin in active school, or when student is associated with current user; hidden/non-visible records return `404`)
- `PUT /api/v1/students/{student_id}` (admin only; supports partial association sync via `associations.add/remove`)
- `DELETE /api/v1/students/{student_id}` (soft delete, admin only)
- `POST /api/v1/students/{student_id}/users` and `DELETE /.../users/{user_id}` (associate/deassociate user-student, admin only)
- `POST /api/v1/students/{student_id}/schools` and `DELETE /.../schools/{school_id}` (associate/deassociate student-school, admin only)

Frontend admin association actions for user-school and student-school use the active school session (`X-School-Id`) as context.

## Fee definition endpoints

- `GET /api/v1/fees` (admin only, active school-scoped, paginated envelope)
- `POST /api/v1/fees` (admin only, creates fee definition for active school)
- `GET /api/v1/fees/{fee_id}` (admin only, `404` if not visible in active school)
- `PUT /api/v1/fees/{fee_id}` (admin only, updates active-school fee definition)
- `DELETE /api/v1/fees/{fee_id}` (admin only, soft delete)

`POST /api/v1/fees` payload example:

```json
{
  "name": "Cuota mensual",
  "amount": "150.00",
  "recurrence": "monthly",
  "is_active": true
}
```

## Charge endpoints

- `GET /api/v1/charges` (admin only, active school-scoped, paginated envelope)
- `POST /api/v1/charges` (admin only, creates charge for active school and valid student)
- `GET /api/v1/charges/{charge_id}` (admin only, `404` if not visible in active school)
- `PUT /api/v1/charges/{charge_id}` (admin only, updates active-school charge)
- `DELETE /api/v1/charges/{charge_id}` (admin only, soft delete + status `cancelled`)
- `GET /api/v1/students/{student_id}/charges/unpaid` (admin only; returns unpaid items and `total_unpaid_amount`)
- `GET /api/v1/students/{student_id}/charges/unpaid` (visibility-aware; paginated/searchable unpaid items and `total_unpaid_amount`)
- `GET /api/v1/students/{student_id}/financial-summary` (visibility-aware; school-scoped all-time totals for unpaid/charged/paid and account status)
- Charge status values: `paid`, `unpaid`, `cancelled`
- Charge type values: `fee`, `interest`, `penalty`
- `debt_created_at` is required for charge create/update flows

## Invoice endpoints

- `GET /api/v1/students/{student_id}/invoices` (paginated/searchable summaries only; each row excludes invoice items)
- `GET /api/v1/invoices/{invoice_id}` (invoice detail with nested `items`)
- `GET /api/v1/invoices/{invoice_id}/items` (invoice items list; compatibility read endpoint)
- `POST /api/v1/students/{student_id}/invoices/generate` (admin only; closes existing open invoice, computes interest deltas, and creates a new open invoice from unpaid charges)
- Visibility rules:
  - school `admin`: can read all invoices from active school
  - non-admin: can read invoices only for students associated to current user in active school
  - non-visible existing records return `404`

## Payment endpoints

- `POST /api/v1/payments` (admin only, active school-scoped)
- `GET /api/v1/students/{student_id}/payments` (paginated/searchable, visibility-aware)
- `GET /api/v1/payments/{payment_id}` (visibility-aware)
- `POST /api/v1/payments` rules:
  - invoice is required
  - invoice must be open
  - overdue invoices are rejected (`400`)
  - payment allocation marks charges paid/unpaid using deterministic ordering and may split a cutoff charge
- Visibility rules:
  - school `admin`: can read all payments from active school
  - non-admin: can read payments only for students associated to current user in active school
  - non-visible existing records return `404`

`POST /api/v1/charges` payload example:

```json
{
  "student_id": 1,
  "fee_definition_id": null,
  "description": "Cuota mensual marzo",
  "amount": "150.00",
  "period": "2026-03",
  "debt_created_at": "2026-03-01T09:00:00Z",
  "due_date": "2026-03-10",
  "charge_type": "fee",
  "status": "unpaid"
}
```

### Partial association sync payloads

`PUT /api/v1/users/{user_id}` can include:

```json
{
  "associations": {
    "add": { "school_roles": [{ "school_id": 1, "role": "teacher" }] },
    "remove": { "school_roles": [{ "school_id": 2, "role": "student" }] }
  }
}
```

`PUT /api/v1/students/{student_id}` can include:

```json
{
  "associations": {
    "add": { "user_ids": [10], "school_ids": [3] },
    "remove": { "user_ids": [11], "school_ids": [2] }
  }
}
```

## Frontend navigation

- Default route after login: `/dashboard`.
- Sidebar sections:
  - `Dashboard`
  - `Configuration` (admin only): `Users`, `Students`, `Schools`, `Fees`, `Charges`
  - `Students` (one item per student associated with current user in active school)
- Top-right area includes:
  - school selector (switches active `X-School-Id` context)
  - avatar shortcut to `/profile`
- Configuration lists (`users`, `students`, `schools`, `fees`, `charges`) support:
  - server-side search and pagination (`offset`, `limit`, `search`)
  - create/edit modals
  - row delete actions with confirmation
- Student dashboard view supports:
  - financial summary cards and summary table (unpaid, charged, paid, debt, credit, account status)
  - unpaid charges table with server-side search/pagination
  - invoices table with server-side search/pagination, payment action modal, and admin-only manual generation button
  - payments table with server-side search/pagination
  - payment button behavior:
    - disabled when there is no open invoice (`There is no open invoice`)
    - disabled when open invoice is overdue (`Invoice is due. Generate a new one`)
    - enabled only for non-overdue open invoice and submits `POST /api/v1/payments`

## School dashboard metrics

- `GET /api/v1/schools/{school_id}/financial-summary` (admin only; requires `X-School-Id` matching path id)
- Metrics shown on home dashboard for active school:
  - `total_billed_amount`: sum of currently open invoices (billed and still unpaid/open)
  - `total_charged_amount`: sum of all positive, non-cancelled charges in the school
  - `total_paid_amount`: sum of all payments received by the school
  - `total_pending_amount`: net sum of unpaid charges (includes negative credits)
  - `student_count`: distinct count of active students linked to the school
- User create/edit modals include school-role assignment management:
  - table of assigned school + role rows
  - school selector + role selector + add button
  - remove action per row

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
- Sample fee definitions per school
- Sample charges per school/student
- Sample invoices and invoice items (with charge snapshot values)
- Sample payments (including partial and full payments tied to invoices)
- `tc-lab` school with `TC-01`..`TC-15` billing fixtures for manual invoice/payment process validation

`tc-lab` quick manual flow:

- Log in as `admin@example.com` / `admin123`
- Switch school selector to `tc-lab`
- TC fixture dates are seeded with a rolling month anchor based on the current date, so scenarios stay valid over time
- Open `Configuration > Students`, search by `TC-XX`, then open the student dashboard by clicking the student ID
- For generation scenarios (`TC-07`..`TC-10`, `TC-14`, `TC-15`), use the `Generate Invoice` button on billing view
- For payment scenarios (`TC-01`..`TC-06`, `TC-11`..`TC-13`), create payments against the open invoice and validate charge/invoice transitions

Use the frontend login form at `http://localhost:13000` to verify authenticated session and the dummy home page.
