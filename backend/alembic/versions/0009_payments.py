"""create payments table with tenant rls

Revision ID: 0009_payments
Revises: 0008_invoices
Create Date: 2026-02-26 17:05:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0009_payments"
down_revision = "0008_invoices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(length=50), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_payments_id", "payments", ["id"], unique=False)
    op.create_index("ix_payments_school_id", "payments", ["school_id"], unique=False)
    op.create_index("ix_payments_student_id", "payments", ["student_id"], unique=False)
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"], unique=False)
    op.create_index("ix_payments_paid_at", "payments", ["paid_at"], unique=False)
    op.create_index("ix_payments_method", "payments", ["method"], unique=False)
    op.create_index("ix_payments_deleted_at", "payments", ["deleted_at"], unique=False)

    op.execute("ALTER TABLE payments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payments FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS payments_tenant_isolation ON payments")
    op.execute(
        """
        CREATE POLICY payments_tenant_isolation
        ON payments
        FOR ALL
        USING (
            current_setting('app.current_school_id', true) IS NOT NULL
            AND school_id = current_setting('app.current_school_id', true)::int
        )
        WITH CHECK (
            current_setting('app.current_school_id', true) IS NOT NULL
            AND school_id = current_setting('app.current_school_id', true)::int
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS payments_tenant_isolation ON payments")
    op.execute("ALTER TABLE payments NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payments DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_payments_deleted_at", table_name="payments")
    op.drop_index("ix_payments_method", table_name="payments")
    op.drop_index("ix_payments_paid_at", table_name="payments")
    op.drop_index("ix_payments_invoice_id", table_name="payments")
    op.drop_index("ix_payments_student_id", table_name="payments")
    op.drop_index("ix_payments_school_id", table_name="payments")
    op.drop_index("ix_payments_id", table_name="payments")
    op.drop_table("payments")
