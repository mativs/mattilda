"""schools multitenant and rls

Revision ID: 0002_schools_multitenant_rls
Revises: 0001_initial_auth
Create Date: 2026-02-25 12:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_schools_multitenant_rls"
down_revision = "0001_initial_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_schools_id", "schools", ["id"], unique=False)
    op.create_index("ix_schools_slug", "schools", ["slug"], unique=True)

    op.create_table(
        "user_school_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "school_id", "role", name="uq_user_school_role"),
    )
    op.create_index("ix_user_school_roles_id", "user_school_roles", ["id"], unique=False)
    op.create_index("ix_user_school_roles_user_id", "user_school_roles", ["user_id"], unique=False)
    op.create_index("ix_user_school_roles_school_id", "user_school_roles", ["school_id"], unique=False)
    op.create_index("ix_user_school_roles_role", "user_school_roles", ["role"], unique=False)

    op.execute(
        """
        INSERT INTO schools (name, slug, is_active)
        SELECT 'Default School', 'default-school', true
        WHERE NOT EXISTS (SELECT 1 FROM schools)
        """
    )

    op.add_column("dummy_records", sa.Column("school_id", sa.Integer(), nullable=True))
    op.create_index("ix_dummy_records_school_id", "dummy_records", ["school_id"], unique=False)
    op.create_foreign_key(
        "fk_dummy_records_school_id_schools",
        "dummy_records",
        "schools",
        ["school_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        UPDATE dummy_records
        SET school_id = (SELECT id FROM schools ORDER BY id LIMIT 1)
        WHERE school_id IS NULL
        """
    )
    op.alter_column("dummy_records", "school_id", nullable=False)

    op.execute("ALTER TABLE dummy_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_school_roles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dummy_records FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_school_roles FORCE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS dummy_records_tenant_isolation ON dummy_records")
    op.execute(
        """
        CREATE POLICY dummy_records_tenant_isolation
        ON dummy_records
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

    op.execute("DROP POLICY IF EXISTS user_school_roles_visibility ON user_school_roles")
    op.execute(
        """
        CREATE POLICY user_school_roles_visibility
        ON user_school_roles
        FOR ALL
        USING (
            current_setting('app.is_global_admin', true) = 'true'
            OR (
                current_setting('app.current_user_id', true) IS NOT NULL
                AND user_id = current_setting('app.current_user_id', true)::int
            )
        )
        WITH CHECK (
            current_setting('app.is_global_admin', true) = 'true'
            OR (
                current_setting('app.current_user_id', true) IS NOT NULL
                AND user_id = current_setting('app.current_user_id', true)::int
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS user_school_roles_visibility ON user_school_roles")
    op.execute("DROP POLICY IF EXISTS dummy_records_tenant_isolation ON dummy_records")
    op.execute("ALTER TABLE user_school_roles NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dummy_records NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_school_roles DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dummy_records DISABLE ROW LEVEL SECURITY")

    op.drop_constraint("fk_dummy_records_school_id_schools", "dummy_records", type_="foreignkey")
    op.drop_index("ix_dummy_records_school_id", table_name="dummy_records")
    op.drop_column("dummy_records", "school_id")

    op.drop_index("ix_user_school_roles_role", table_name="user_school_roles")
    op.drop_index("ix_user_school_roles_school_id", table_name="user_school_roles")
    op.drop_index("ix_user_school_roles_user_id", table_name="user_school_roles")
    op.drop_index("ix_user_school_roles_id", table_name="user_school_roles")
    op.drop_table("user_school_roles")

    op.drop_index("ix_schools_slug", table_name="schools")
    op.drop_index("ix_schools_id", table_name="schools")
    op.drop_table("schools")
