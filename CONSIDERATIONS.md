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

## Payment considerations

Payments can be partial and may not settle the full invoice amount in a single transaction. In this scope, the seed data intentionally includes both full and partial invoice payments to exercise historical reporting and visibility flows.

Interest accrues only on fee charges. Unpaid interest charges do not compound.