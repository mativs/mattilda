"""add soft delete columns to users and schools

Revision ID: 0004_soft_delete_main
Revises: 0003_drop_user_roles
Create Date: 2026-02-25 16:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_soft_delete_main"
down_revision = "0003_drop_user_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("schools", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"], unique=False)
    op.create_index("ix_schools_deleted_at", "schools", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_schools_deleted_at", table_name="schools")
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("schools", "deleted_at")
    op.drop_column("users", "deleted_at")
