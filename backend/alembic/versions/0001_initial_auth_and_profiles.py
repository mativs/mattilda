"""initial auth and profiles

Revision ID: 0001_initial_auth
Revises:
Create Date: 2026-02-25 08:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial_auth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()

    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("roles", sa.ARRAY(sa.String(length=20)), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    user_profiles = sa.Table(
        "user_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    dummy_records = sa.Table(
        "dummy_records",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    users.create(bind, checkfirst=True)
    user_profiles.create(bind, checkfirst=True)
    dummy_records.create(bind, checkfirst=True)

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_id ON users (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_profiles_id ON user_profiles (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_profiles_user_id ON user_profiles (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_dummy_records_id ON dummy_records (id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_dummy_records_id")
    op.execute("DROP TABLE IF EXISTS dummy_records")

    op.execute("DROP INDEX IF EXISTS ix_user_profiles_id")
    op.execute("DROP INDEX IF EXISTS ix_user_profiles_user_id")
    op.execute("DROP TABLE IF EXISTS user_profiles")

    op.execute("DROP INDEX IF EXISTS ix_users_id")
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("DROP TABLE IF EXISTS users")

