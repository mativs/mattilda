"""add reconciliation runs and findings tables

Revision ID: 0011_reconciliation_logs
Revises: 0010_charge_process_refactor
Create Date: 2026-02-27 09:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0011_reconciliation_logs"
down_revision = "0010_charge_process_refactor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_reconciliation_runs_id", "reconciliation_runs", ["id"], unique=False)
    op.create_index("ix_reconciliation_runs_school_id", "reconciliation_runs", ["school_id"], unique=False)
    op.create_index(
        "ix_reconciliation_runs_triggered_by_user_id",
        "reconciliation_runs",
        ["triggered_by_user_id"],
        unique=False,
    )
    op.create_index("ix_reconciliation_runs_status", "reconciliation_runs", ["status"], unique=False)
    op.create_index("ix_reconciliation_runs_started_at", "reconciliation_runs", ["started_at"], unique=False)
    op.create_index("ix_reconciliation_runs_finished_at", "reconciliation_runs", ["finished_at"], unique=False)

    op.create_table(
        "reconciliation_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_reconciliation_findings_id", "reconciliation_findings", ["id"], unique=False)
    op.create_index("ix_reconciliation_findings_run_id", "reconciliation_findings", ["run_id"], unique=False)
    op.create_index("ix_reconciliation_findings_school_id", "reconciliation_findings", ["school_id"], unique=False)
    op.create_index("ix_reconciliation_findings_check_code", "reconciliation_findings", ["check_code"], unique=False)
    op.create_index("ix_reconciliation_findings_severity", "reconciliation_findings", ["severity"], unique=False)
    op.create_index("ix_reconciliation_findings_entity_type", "reconciliation_findings", ["entity_type"], unique=False)
    op.create_index("ix_reconciliation_findings_entity_id", "reconciliation_findings", ["entity_id"], unique=False)

    op.execute("ALTER TABLE reconciliation_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reconciliation_runs FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS reconciliation_runs_tenant_isolation ON reconciliation_runs")
    op.execute(
        """
        CREATE POLICY reconciliation_runs_tenant_isolation
        ON reconciliation_runs
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

    op.execute("ALTER TABLE reconciliation_findings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reconciliation_findings FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS reconciliation_findings_tenant_isolation ON reconciliation_findings")
    op.execute(
        """
        CREATE POLICY reconciliation_findings_tenant_isolation
        ON reconciliation_findings
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
    op.execute("DROP POLICY IF EXISTS reconciliation_findings_tenant_isolation ON reconciliation_findings")
    op.execute("ALTER TABLE reconciliation_findings NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reconciliation_findings DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS reconciliation_runs_tenant_isolation ON reconciliation_runs")
    op.execute("ALTER TABLE reconciliation_runs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reconciliation_runs DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_reconciliation_findings_entity_id", table_name="reconciliation_findings")
    op.drop_index("ix_reconciliation_findings_entity_type", table_name="reconciliation_findings")
    op.drop_index("ix_reconciliation_findings_severity", table_name="reconciliation_findings")
    op.drop_index("ix_reconciliation_findings_check_code", table_name="reconciliation_findings")
    op.drop_index("ix_reconciliation_findings_school_id", table_name="reconciliation_findings")
    op.drop_index("ix_reconciliation_findings_run_id", table_name="reconciliation_findings")
    op.drop_index("ix_reconciliation_findings_id", table_name="reconciliation_findings")
    op.drop_table("reconciliation_findings")

    op.drop_index("ix_reconciliation_runs_finished_at", table_name="reconciliation_runs")
    op.drop_index("ix_reconciliation_runs_started_at", table_name="reconciliation_runs")
    op.drop_index("ix_reconciliation_runs_status", table_name="reconciliation_runs")
    op.drop_index("ix_reconciliation_runs_triggered_by_user_id", table_name="reconciliation_runs")
    op.drop_index("ix_reconciliation_runs_school_id", table_name="reconciliation_runs")
    op.drop_index("ix_reconciliation_runs_id", table_name="reconciliation_runs")
    op.drop_table("reconciliation_runs")
