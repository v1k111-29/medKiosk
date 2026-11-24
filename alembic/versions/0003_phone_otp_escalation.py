"""Phone OTP identification table and appointment escalation reasons.

Revision ID: 0003_phone_otp_escalation
Revises: 0002_v3_queue_auth
Create Date: 2026-11-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_phone_otp_escalation"
down_revision: Union[str, None] = "0002_v3_queue_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "phone_otps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phone", sa.String(16), nullable=False),
        sa.Column("otp_hash", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("consumed_at", sa.DateTime()),
    )
    op.create_index("ix_phone_otps_phone_created", "phone_otps", ["phone", "created_at"])

    with op.batch_alter_table("appointments") as b:
        b.add_column(sa.Column("escalation_reasons", sa.Text()))


def downgrade() -> None:
    with op.batch_alter_table("appointments") as b:
        b.drop_column("escalation_reasons")
    op.drop_index("ix_phone_otps_phone_created", table_name="phone_otps")
    op.drop_table("phone_otps")
