"""v3: departments, token counters, users, queue/SMS columns, consent and extra vitals.

Revision ID: 0002_v3_queue_auth
Revises: 0001_baseline
Create Date: 2026-11-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_v3_queue_auth"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("name_ta", sa.Text(), nullable=False),
        sa.Column("room", sa.Text(), nullable=False),
        sa.Column("token_prefix", sa.String(8), nullable=False),
        sa.Column("avg_wait_mins", sa.Integer(), nullable=False),
        sa.Column("color", sa.Text()),
        sa.Column("icon", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "token_counters",
        sa.Column("dept_id", sa.String(32), primary_key=True),
        sa.Column("queue_date", sa.Date(), primary_key=True),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=NOW),
    )

    with op.batch_alter_table("patients") as b:
        b.add_column(sa.Column("face_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("consent_at", sa.DateTime()))
        b.add_column(sa.Column("consent_version", sa.Text()))

    # v2 kiosks required ticking the consent box before /register and always stored
    # consent_given=1, so existing patients with a stored face keep face matching.
    op.execute(
        "UPDATE patients SET face_consent = consent_given, consent_version = 'v2-legacy' "
        "WHERE consent_given IS NOT NULL AND embedding IS NOT NULL"
    )

    with op.batch_alter_table("vitals") as b:
        b.add_column(sa.Column("pulse", sa.Integer()))
        b.add_column(sa.Column("temperature", sa.Float()))
        b.add_column(sa.Column("resp_rate", sa.Integer()))
        b.add_column(sa.Column("glucose", sa.Float()))

    with op.batch_alter_table("appointments") as b:
        b.add_column(sa.Column("token_number", sa.Integer()))
        b.add_column(sa.Column("queue_date", sa.Date()))
        b.add_column(sa.Column("urgency", sa.String(16), nullable=False, server_default=sa.text("'normal'")))
        b.add_column(sa.Column("called_at", sa.DateTime()))
        b.add_column(sa.Column("started_at", sa.DateTime()))
        b.add_column(sa.Column("completed_at", sa.DateTime()))
        b.add_column(sa.Column("handled_by", sa.Integer()))
        b.add_column(sa.Column("sms_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(
            sa.Column("sms_status", sa.String(16), nullable=False, server_default=sa.text("'not_requested'"))
        )
        b.create_foreign_key("fk_appointments_handled_by", "users", ["handled_by"], ["id"])
        b.create_unique_constraint("uq_appointments_dept_date_token", ["dept_id", "queue_date", "token_number"])
        b.create_index("ix_appointments_queue", ["queue_date", "dept_id", "status"])


def downgrade() -> None:
    with op.batch_alter_table("appointments") as b:
        b.drop_index("ix_appointments_queue")
        b.drop_constraint("uq_appointments_dept_date_token", type_="unique")
        b.drop_constraint("fk_appointments_handled_by", type_="foreignkey")
        for col in ("sms_status", "sms_opt_in", "handled_by", "completed_at", "started_at",
                    "called_at", "urgency", "queue_date", "token_number"):
            b.drop_column(col)
    with op.batch_alter_table("vitals") as b:
        for col in ("glucose", "resp_rate", "temperature", "pulse"):
            b.drop_column(col)
    with op.batch_alter_table("patients") as b:
        for col in ("consent_version", "consent_at", "face_consent"):
            b.drop_column(col)
    op.drop_table("users")
    op.drop_table("token_counters")
    op.drop_table("departments")
