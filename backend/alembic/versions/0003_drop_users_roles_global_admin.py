"""drop global user roles

Revision ID: 0003_drop_user_roles
Revises: 0002_schools_multitenant_rls
Create Date: 2026-02-25 14:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_drop_user_roles"
down_revision = "0002_schools_multitenant_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "roles")

    op.execute("DROP POLICY IF EXISTS user_school_roles_visibility ON user_school_roles")
    op.execute(
        """
        CREATE POLICY user_school_roles_visibility
        ON user_school_roles
        FOR ALL
        USING (
            current_setting('app.current_user_id', true) IS NOT NULL
            AND user_id = current_setting('app.current_user_id', true)::int
        )
        WITH CHECK (
            current_setting('app.current_user_id', true) IS NOT NULL
            AND user_id = current_setting('app.current_user_id', true)::int
        )
        """
    )


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("roles", sa.ARRAY(sa.String(length=20)), nullable=False, server_default=sa.text("'{}'")),
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
