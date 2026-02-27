"""refactor charge enums and origin linkage

Revision ID: 0010_charge_process_refactor
Revises: 0009_payments
Create Date: 2026-02-26 19:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0010_charge_process_refactor"
down_revision = "0009_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("charges", sa.Column("debt_created_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE charges SET debt_created_at = created_at WHERE debt_created_at IS NULL")
    op.alter_column("charges", "debt_created_at", nullable=False)
    op.create_index("ix_charges_debt_created_at", "charges", ["debt_created_at"], unique=False)

    op.add_column("charges", sa.Column("origin_charge_id", sa.Integer(), nullable=True))
    op.create_index("ix_charges_origin_charge_id", "charges", ["origin_charge_id"], unique=False)
    op.create_foreign_key(
        "fk_charges_origin_charge_id",
        "charges",
        "charges",
        ["origin_charge_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("CREATE TYPE charge_status_new AS ENUM ('paid', 'unpaid', 'cancelled')")
    op.execute("CREATE TYPE charge_type_new AS ENUM ('fee', 'interest', 'penalty')")

    op.execute(
        """
        ALTER TABLE charges
        ALTER COLUMN status DROP DEFAULT,
        ALTER COLUMN status TYPE charge_status_new
        USING (
            CASE
                WHEN status::text = 'billed' THEN 'paid'
                WHEN status::text = 'unbilled' THEN 'unpaid'
                ELSE status::text
            END
        )::charge_status_new
        """
    )
    op.execute("ALTER TABLE charges ALTER COLUMN status SET DEFAULT 'unpaid'::charge_status_new")

    op.execute(
        """
        ALTER TABLE charges
        ALTER COLUMN charge_type TYPE charge_type_new
        USING (
            CASE
                WHEN charge_type::text = 'balance_forward' THEN 'penalty'
                ELSE charge_type::text
            END
        )::charge_type_new
        """
    )
    op.execute(
        """
        ALTER TABLE invoice_items
        ALTER COLUMN charge_type TYPE charge_type_new
        USING (
            CASE
                WHEN charge_type::text = 'balance_forward' THEN 'penalty'
                ELSE charge_type::text
            END
        )::charge_type_new
        """
    )

    op.execute("DROP TYPE charge_status")
    op.execute("ALTER TYPE charge_status_new RENAME TO charge_status")
    op.execute("DROP TYPE charge_type")
    op.execute("ALTER TYPE charge_type_new RENAME TO charge_type")

    op.drop_constraint("fk_charges_origin_invoice_id", "charges", type_="foreignkey")
    op.drop_index("ix_charges_origin_invoice_id", table_name="charges")
    op.drop_column("charges", "origin_invoice_id")


def downgrade() -> None:
    op.add_column("charges", sa.Column("origin_invoice_id", sa.Integer(), nullable=True))
    op.create_index("ix_charges_origin_invoice_id", "charges", ["origin_invoice_id"], unique=False)
    op.create_foreign_key(
        "fk_charges_origin_invoice_id",
        "charges",
        "invoices",
        ["origin_invoice_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("CREATE TYPE charge_status_old AS ENUM ('unbilled', 'billed', 'cancelled')")
    op.execute("CREATE TYPE charge_type_old AS ENUM ('fee', 'interest', 'penalty', 'balance_forward')")

    op.execute(
        """
        ALTER TABLE charges
        ALTER COLUMN status DROP DEFAULT,
        ALTER COLUMN status TYPE charge_status_old
        USING (
            CASE
                WHEN status::text = 'paid' THEN 'billed'
                WHEN status::text = 'unpaid' THEN 'unbilled'
                ELSE status::text
            END
        )::charge_status_old
        """
    )
    op.execute("ALTER TABLE charges ALTER COLUMN status SET DEFAULT 'unbilled'::charge_status_old")

    op.execute(
        """
        ALTER TABLE charges
        ALTER COLUMN charge_type TYPE charge_type_old
        USING charge_type::text::charge_type_old
        """
    )
    op.execute(
        """
        ALTER TABLE invoice_items
        ALTER COLUMN charge_type TYPE charge_type_old
        USING charge_type::text::charge_type_old
        """
    )

    op.execute("DROP TYPE charge_status")
    op.execute("ALTER TYPE charge_status_old RENAME TO charge_status")
    op.execute("DROP TYPE charge_type")
    op.execute("ALTER TYPE charge_type_old RENAME TO charge_type")

    op.drop_constraint("fk_charges_origin_charge_id", "charges", type_="foreignkey")
    op.drop_index("ix_charges_origin_charge_id", table_name="charges")
    op.drop_column("charges", "origin_charge_id")

    op.drop_index("ix_charges_debt_created_at", table_name="charges")
    op.drop_column("charges", "debt_created_at")
