"""create students and association tables

Revision ID: 0005_students_assoc
Revises: 0004_soft_delete_main
Create Date: 2026-02-25 16:10:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_students_assoc"
down_revision = "0004_soft_delete_main"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_students_id", "students", ["id"], unique=False)
    op.create_index("ix_students_external_id", "students", ["external_id"], unique=True)
    op.create_index("ix_students_deleted_at", "students", ["deleted_at"], unique=False)

    op.create_table(
        "user_students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "student_id", name="uq_user_student"),
    )
    op.create_index("ix_user_students_id", "user_students", ["id"], unique=False)
    op.create_index("ix_user_students_user_id", "user_students", ["user_id"], unique=False)
    op.create_index("ix_user_students_student_id", "user_students", ["student_id"], unique=False)

    op.create_table(
        "student_schools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("student_id", "school_id", name="uq_student_school"),
    )
    op.create_index("ix_student_schools_id", "student_schools", ["id"], unique=False)
    op.create_index("ix_student_schools_student_id", "student_schools", ["student_id"], unique=False)
    op.create_index("ix_student_schools_school_id", "student_schools", ["school_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_student_schools_school_id", table_name="student_schools")
    op.drop_index("ix_student_schools_student_id", table_name="student_schools")
    op.drop_index("ix_student_schools_id", table_name="student_schools")
    op.drop_table("student_schools")

    op.drop_index("ix_user_students_student_id", table_name="user_students")
    op.drop_index("ix_user_students_user_id", table_name="user_students")
    op.drop_index("ix_user_students_id", table_name="user_students")
    op.drop_table("user_students")

    op.drop_index("ix_students_deleted_at", table_name="students")
    op.drop_index("ix_students_external_id", table_name="students")
    op.drop_index("ix_students_id", table_name="students")
    op.drop_table("students")
