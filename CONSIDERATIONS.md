# Authorization Model

## Identified risks

Before choosing an authorization model, the following scenarios were mapped:

**The most critical risk:** a user from one school accessing data from another school — grades, billing, students, or any resource. Without explicit tenant isolation, a single missing filter in any query is enough to cause a data breach across organizations.

- A student accessing another student's grades or personal data
- A parent viewing information about children that are not their own
- A teacher accessing records from courses they are not assigned to
- A student or parent reaching administrative endpoints (billing, reports)
- A teacher writing records they are allowed to read (e.g. finalizing grades outside their course)
- Any authenticated user accessing a resource by guessing its ID (IDOR)
- Billing or financial reports leaking to non-administrative roles
- Treating frontend filtering as a security boundary

## Decisions

**Multi-tenant isolation via `school_id`.** Every entity in the system is scoped to a school. All queries are filtered by the tenant extracted from the authenticated user's token. As an additional safety net, PostgreSQL Row-Level Security (RLS) is used to enforce isolation at the database level — ensuring that even if an application-level filter is missed, the database will not return data from another tenant.

**RBAC with hardcoded Enum roles.** Each role maps to a real actor with predictable needs — `admin`, `director`, `teacher`, `student`, `parent`. Roles are scoped per tenant: a user can be `teacher` in one school and `admin` in another. This makes the permission model easy to reason about, audit, and test exhaustively.

**Two enforcement layers on every endpoint:** role check (can this role access this resource type?) and ownership check (does this user own this specific resource?). Both live in the backend. Frontend adapts to the role for UX only.

**No per-user granular permissions or read/write/create dimensions.** The added flexibility is not worth the configuration surface area at this stage. The model is structured to support that evolution if the business requires it.

## Scope disclaimer

Due to the scope and time constraints of this take-home project, a platform-level superadmin is intentionally not implemented. All authorization is school-scoped through memberships and per-school roles.

## Soft delete policy

For auditability and historical consistency (for example, invoice trails), `users`, `schools`, and `students` use soft delete (`deleted_at`). In this scope, deleted users cannot be recreated with the same email.

## Search and pagination considerations

List endpoints use offset/limit pagination and a shared `search` parameter with declarative per-resource fields (users: email/name, schools: name/slug, students: first/last/external_id). Search currently uses standard `ILIKE` predicates without PostgreSQL extensions to keep deployment/setup simple for this scope.

If dataset size or latency requirements increase, the next optimization step is adopting `pg_trgm` with GIN indexes for search-heavy columns.

## Invoice immutability

`invoice_items` persist snapshots of `charge.description`, `charge.amount`, and `charge_type` at billing time. This keeps issued invoices stable and auditable even if the original charge is later updated or cancelled.

## Why invoices are not full CRUD

Although the take-home asks for invoice CRUD, this implementation intentionally exposes invoices as read-only documents plus controlled generation/closure flows. The reason is domain integrity: an invoice is the result of charge aggregation and payment allocation, so allowing arbitrary update/delete operations would break auditability and create inconsistencies between `invoices`, `invoice_items`, `charges`, and `payments`.

To stay compliant with the requirement while preserving accounting consistency, invoice lifecycle changes are handled through business actions (generate invoice, apply payment, close/reopen through process rules) instead of generic CRUD mutations.

## Payment considerations

Payments can be partial and may not settle the full invoice amount in a single transaction. In this scope, the seed data intentionally includes both full and partial invoice payments to exercise historical reporting and visibility flows.

Interest accrues only on fee charges. Unpaid interest charges do not compound.

## Cache and locking decisions

Three optimizations were evaluated for value versus implementation complexity:

- Student balance cache
- Active invoice cache
- Payment double-submit lock

### Implemented now

**Student balance cache (`student_balance:{school_id}:{student_id}`).** Student financial summary totals are cached for a short TTL and invalidated on any write that changes balance semantics (`charge` create/update/delete, invoice generation, payment creation). The design is fail-safe: if Redis is unavailable, reads fall back to DB and writes are skipped without breaking requests.

**Payment creation lock (`payment_lock:{school_id}:{invoice_id}`).** A short-lived Redis lock is taken before creating a payment so duplicate submits cannot process concurrently for the same invoice. Lock contention returns `409 Conflict`.

### Deferred

**Active invoice cache deferred.** In this scope, active-invoice queries are not the main bottleneck and introducing a second cache domain increases invalidation complexity. It can be added later if query volume or latency indicates clear value.

## Async invoice generation

School-wide invoice generation is implemented asynchronously with Celery using Redis as broker/result backend. This avoids long-running synchronous requests when a school has many students and reuses the same per-student invoice generation business service.

Celery beat is intentionally not included in this scope. If periodic invoice generation becomes a requirement, beat can be added later to schedule recurring dispatches over the same school-wide task entrypoint.

## Reconciliation checks

Reconciliation is implemented as **school-scoped** asynchronous checks. Each execution writes one run record and multiple finding records so admins can review results historically from the UI.

### Usefulness evaluation

The current billing flow is multi-step and stateful (charges, invoices, invoice items, payments, credits, and interest). These checks provide high operational value because they detect cross-step inconsistencies that ordinary endpoint validations cannot fully prevent.

- High-signal checks:
  - invoice total vs invoice items sum mismatch
  - interest charges with invalid origin reference
  - open invoices where confirmed payments already cover invoice total
  - duplicate payments within a narrow timestamp window
- Medium-signal checks (guarded to reduce false positives):
  - orphan unpaid charges while student has an open and not-due invoice
  - unapplied negative unpaid charges attached to invoices that already have payments
- Contextual integrity check:
  - invoice items referencing cancelled charges with no residual replacement

### False-positive guards

- Orphan-charge check only flags charges when the student already has an open, not-due invoice.
- Negative-charge check only flags charges linked to invoices that already received payments.
- Duplicate-payment check requires same student, same amount, and very close timestamps.

### Future bank-feed reconciliation

When a payment provider or bank feed is integrated, each `Payment` should include an `external_reference` field carrying the provider transaction ID.

A future reconciliation layer should compare bank movements against confirmed `Payment` records and flag:

- a bank movement with no matching `Payment` in the system
- a confirmed `Payment` with no corresponding bank movement
- amount mismatches between bank record and `Payment`

## Structured logging for operational analysis

The project uses structured logging with `structlog` so backend events are emitted with contextual fields (for example `school_id`, `student_id`, `invoice_id`, `run_id`, totals, and status transitions). This improves debugging and makes metric/event analysis easier in local logs or centralized log pipelines.

As the project grows, service-level event logs can be used to build operational dashboards and alerting around critical workflows such as invoice generation, payment allocation, and reconciliation execution outcomes.