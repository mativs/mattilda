"""create invoices and invoice_items with tenant rls

Revision ID: 0008_invoices
Revises: 0007_charges
Create Date: 2026-02-26 14:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0008_invoices"
down_revision = "0007_charges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.Enum("open", "closed", "cancelled", name="invoice_status"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_invoices_id", "invoices", ["id"], unique=False)
    op.create_index("ix_invoices_school_id", "invoices", ["school_id"], unique=False)
    op.create_index("ix_invoices_student_id", "invoices", ["student_id"], unique=False)
    op.create_index("ix_invoices_period", "invoices", ["period"], unique=False)
    op.create_index("ix_invoices_issued_at", "invoices", ["issued_at"], unique=False)
    op.create_index("ix_invoices_due_date", "invoices", ["due_date"], unique=False)
    op.create_index("ix_invoices_status", "invoices", ["status"], unique=False)
    op.create_index("ix_invoices_deleted_at", "invoices", ["deleted_at"], unique=False)

    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("charge_id", sa.Integer(), sa.ForeignKey("charges.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "charge_type",
            sa.Enum("fee", "interest", "penalty", "balance_forward", name="charge_type", create_type=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_invoice_items_id", "invoice_items", ["id"], unique=False)
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"], unique=False)
    op.create_index("ix_invoice_items_charge_id", "invoice_items", ["charge_id"], unique=False)
    op.create_index("ix_invoice_items_charge_type", "invoice_items", ["charge_type"], unique=False)

    op.add_column("charges", sa.Column("invoice_id", sa.Integer(), nullable=True))
    op.add_column("charges", sa.Column("origin_invoice_id", sa.Integer(), nullable=True))
    op.create_index("ix_charges_invoice_id", "charges", ["invoice_id"], unique=False)
    op.create_index("ix_charges_origin_invoice_id", "charges", ["origin_invoice_id"], unique=False)
    op.create_foreign_key("fk_charges_invoice_id", "charges", "invoices", ["invoice_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(
        "fk_charges_origin_invoice_id",
        "charges",
        "invoices",
        ["origin_invoice_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoices FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS invoices_tenant_isolation ON invoices")
    op.execute(
        """
        CREATE POLICY invoices_tenant_isolation
        ON invoices
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
    op.execute("DROP POLICY IF EXISTS invoices_tenant_isolation ON invoices")
    op.execute("ALTER TABLE invoices NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoices DISABLE ROW LEVEL SECURITY")

    op.drop_constraint("fk_charges_origin_invoice_id", "charges", type_="foreignkey")
    op.drop_constraint("fk_charges_invoice_id", "charges", type_="foreignkey")
    op.drop_index("ix_charges_origin_invoice_id", table_name="charges")
    op.drop_index("ix_charges_invoice_id", table_name="charges")
    op.drop_column("charges", "origin_invoice_id")
    op.drop_column("charges", "invoice_id")

    op.drop_index("ix_invoice_items_charge_type", table_name="invoice_items")
    op.drop_index("ix_invoice_items_charge_id", table_name="invoice_items")
    op.drop_index("ix_invoice_items_invoice_id", table_name="invoice_items")
    op.drop_index("ix_invoice_items_id", table_name="invoice_items")
    op.drop_table("invoice_items")

    op.drop_index("ix_invoices_deleted_at", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_due_date", table_name="invoices")
    op.drop_index("ix_invoices_issued_at", table_name="invoices")
    op.drop_index("ix_invoices_period", table_name="invoices")
    op.drop_index("ix_invoices_student_id", table_name="invoices")
    op.drop_index("ix_invoices_school_id", table_name="invoices")
    op.drop_index("ix_invoices_id", table_name="invoices")
    op.drop_table("invoices")

    op.execute("DROP TYPE IF EXISTS invoice_status")
