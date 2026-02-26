"""create fee definitions table with tenant rls

Revision ID: 0006_fee_definitions
Revises: 0005_students_assoc
Create Date: 2026-02-26 09:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_fee_definitions"
down_revision = "0005_students_assoc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    recurrence_enum = sa.Enum("monthly", "annual", "one_time", name="fee_recurrence")

    op.create_table(
        "fee_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("recurrence", recurrence_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_fee_definitions_id", "fee_definitions", ["id"], unique=False)
    op.create_index("ix_fee_definitions_school_id", "fee_definitions", ["school_id"], unique=False)
    op.create_index("ix_fee_definitions_name", "fee_definitions", ["name"], unique=False)
    op.create_index("ix_fee_definitions_recurrence", "fee_definitions", ["recurrence"], unique=False)
    op.create_index("ix_fee_definitions_deleted_at", "fee_definitions", ["deleted_at"], unique=False)

    op.execute("ALTER TABLE fee_definitions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE fee_definitions FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS fee_definitions_tenant_isolation ON fee_definitions")
    op.execute(
        """
        CREATE POLICY fee_definitions_tenant_isolation
        ON fee_definitions
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
    op.execute("DROP POLICY IF EXISTS fee_definitions_tenant_isolation ON fee_definitions")
    op.execute("ALTER TABLE fee_definitions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE fee_definitions DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_fee_definitions_deleted_at", table_name="fee_definitions")
    op.drop_index("ix_fee_definitions_recurrence", table_name="fee_definitions")
    op.drop_index("ix_fee_definitions_name", table_name="fee_definitions")
    op.drop_index("ix_fee_definitions_school_id", table_name="fee_definitions")
    op.drop_index("ix_fee_definitions_id", table_name="fee_definitions")
    op.drop_table("fee_definitions")
    op.execute("DROP TYPE IF EXISTS fee_recurrence")
