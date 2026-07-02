"""Initial migration: create all four tables + deferred balance trigger.

Revision ID: 001
Revises:
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── payment_intents ─────────────────────────────────────────────────
    op.create_table(
        "payment_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "idempotency_key", sa.Text(), unique=True, nullable=False, index=True
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="created",
            index=True,
        ),
        sa.Column("psp_reference", sa.Text(), nullable=True),
        sa.Column("payment_method", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── ledger_entries ──────────────────────────────────────────────────
    op.create_table(
        "ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "intent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payment_intents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "batch_id", postgresql.UUID(as_uuid=True), nullable=False, index=True
        ),
        sa.Column("side", sa.String(6), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Deferred balance constraint trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_ledger_batch_balance()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            debit_sum  INTEGER;
            credit_sum INTEGER;
        BEGIN
            SELECT COALESCE(SUM(amount) FILTER (WHERE side = 'debit'), 0),
                   COALESCE(SUM(amount) FILTER (WHERE side = 'credit'), 0)
            INTO debit_sum, credit_sum
            FROM ledger_entries
            WHERE batch_id = NEW.batch_id;
            IF debit_sum != credit_sum THEN
                RAISE EXCEPTION 'Unbalanced ledger batch %: debits=% credits=%',
                    NEW.batch_id, debit_sum, credit_sum;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ledger_batch_balance_trigger
        AFTER INSERT ON ledger_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION check_ledger_batch_balance();
        """
    )

    # ── webhook_events ──────────────────────────────────────────────────
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("psp", sa.String(20), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── outbox ──────────────────────────────────────────────────────────
    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(30), nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), nullable=True, index=True
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ledger_batch_balance_trigger ON ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS check_ledger_batch_balance()")
    op.drop_table("outbox")
    op.drop_table("webhook_events")
    op.drop_table("ledger_entries")
    op.drop_table("payment_intents")
