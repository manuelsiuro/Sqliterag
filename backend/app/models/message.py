from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.models.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))  # "user", "assistant", "system", "tool"
    content: Mapped[str] = mapped_column(Text)
    images: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON of relative file paths
    tool_calls: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON of tool_calls array
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # for role="tool" messages
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message(id={self.id!r}, role={self.role!r})>"


from app.models.conversation import Conversation  # noqa: E402, F811
