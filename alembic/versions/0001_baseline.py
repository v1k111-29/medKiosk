"""Baseline: the v2 schema previously created by raw sqlite3 init_db().

Pre-Alembic databases are stamped at this revision on startup
(see app.core.database.run_migrations) and then upgraded.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("gender", sa.Text()),
        sa.Column("age", sa.Integer()),
        sa.Column("phone", sa.Text()),
        sa.Column("blood_group", sa.Text()),
        sa.Column("city", sa.Text()),
        sa.Column("embedding", sa.LargeBinary()),
        sa.Column("consent_given", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=NOW),
        sa.Column("visit_count", sa.Integer(), server_default=sa.text("1")),
    )
    op.create_table(
        "vitals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("height", sa.Float()),
        sa.Column("weight", sa.Float()),
        sa.Column("bp_sys", sa.Integer()),
        sa.Column("bp_dia", sa.Integer()),
        sa.Column("spo2", sa.Float()),
        sa.Column("diabetes", sa.Boolean(), server_default=sa.false()),
        sa.Column("hypertension", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=NOW),
    )
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("dept_id", sa.Text(), nullable=False),
        sa.Column("dept_name", sa.Text(), nullable=False),
        sa.Column("qualification", sa.Text()),
        sa.Column("available", sa.Boolean(), server_default=sa.true()),
        sa.Column("room", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=NOW),
    )
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("dept_id", sa.Text(), nullable=False),
        sa.Column("dept_name", sa.Text(), nullable=False),
        sa.Column("room", sa.Text()),
        sa.Column("symptoms", sa.Text()),
        sa.Column("service", sa.Text(), server_default=sa.text("'symptoms'")),
        sa.Column("status", sa.Text(), server_default=sa.text("'waiting'")),
        sa.Column("wait_mins", sa.Integer(), server_default=sa.text("15")),
        sa.Column("created_at", sa.DateTime(), server_default=NOW),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id")),
        sa.Column("doctor_name", sa.Text()),
    )
    op.create_table(
        "face_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
        sa.Column("angle_hint", sa.Text()),
        sa.Column("quality", sa.Float()),
        sa.Column("created_at", sa.DateTime(), server_default=NOW),
    )
    op.create_index("idx_face_emb_patient", "face_embeddings", ["patient_id"])


def downgrade() -> None:
    op.drop_index("idx_face_emb_patient", table_name="face_embeddings")
    op.drop_table("face_embeddings")
    op.drop_table("appointments")
    op.drop_table("doctors")
    op.drop_table("vitals")
    op.drop_table("patients")
