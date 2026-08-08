"""create contract processing tables

Revision ID: 0001_initial
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("submitted_by_subject", sa.String(length=255), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_name", sa.String(length=300), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_batch_id", "documents", ["batch_id"])
    op.create_table(
        "findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("variable_name", sa.String(length=100), nullable=False),
        sa.Column("extracted_value", sa.String(length=500), nullable=False),
        sa.Column("review_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("reviewer_name", sa.String(length=100), server_default="", nullable=False),
        sa.Column("reviewer_subject", sa.String(length=255), server_default="", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "variable_name", name="one_finding_per_variable"),
    )
    op.create_index("ix_findings_document_id", "findings", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_findings_document_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_documents_batch_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("batches")
