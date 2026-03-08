"""add_metrics_column_to_messages

Revision ID: f01eefb9ed2b
Revises: 79a25e0fdbea
Create Date: 2026-03-08 15:30:54.097367
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op



# revision identifiers, used by Alembic.
revision: str = 'f01eefb9ed2b'
down_revision: Union[str, None] = '79a25e0fdbea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('metrics', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'metrics')
