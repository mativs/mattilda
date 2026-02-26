"""create charges table with tenant rls

Revision ID: 0007_charges
Revises: 0006_fee_definitions
Create Date: 2026-02-26 10:45:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0007_charges"
down_revision = "0006_fee_definitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fee_definition_id", sa.Integer(), sa.ForeignKey("fee_definitions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("charge_type", sa.Enum("fee", "interest", "penalty", "balance_forward", name="charge_type"), nullable=False),
        sa.Column("status", sa.Enum("unbilled", "billed", "cancelled", name="charge_status"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_charges_id", "charges", ["id"], unique=False)
    op.create_index("ix_charges_school_id", "charges", ["school_id"], unique=False)
    op.create_index("ix_charges_student_id", "charges", ["student_id"], unique=False)
    op.create_index("ix_charges_fee_definition_id", "charges", ["fee_definition_id"], unique=False)
    op.create_index("ix_charges_due_date", "charges", ["due_date"], unique=False)
    op.create_index("ix_charges_charge_type", "charges", ["charge_type"], unique=False)
    op.create_index("ix_charges_status", "charges", ["status"], unique=False)
    op.create_index("ix_charges_deleted_at", "charges", ["deleted_at"], unique=False)

    op.execute("ALTER TABLE charges ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE charges FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS charges_tenant_isolation ON charges")
    op.execute(
        """
        CREATE POLICY charges_tenant_isolation
        ON charges
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
    op.execute("DROP POLICY IF EXISTS charges_tenant_isolation ON charges")
    op.execute("ALTER TABLE charges NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE charges DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_charges_deleted_at", table_name="charges")
    op.drop_index("ix_charges_status", table_name="charges")
    op.drop_index("ix_charges_charge_type", table_name="charges")
    op.drop_index("ix_charges_due_date", table_name="charges")
    op.drop_index("ix_charges_fee_definition_id", table_name="charges")
    op.drop_index("ix_charges_student_id", table_name="charges")
    op.drop_index("ix_charges_school_id", table_name="charges")
    op.drop_index("ix_charges_id", table_name="charges")
    op.drop_table("charges")

    op.execute("DROP TYPE IF EXISTS charge_status")
    op.execute("DROP TYPE IF EXISTS charge_type")
