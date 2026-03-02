from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_requires_existing_conversation(client: AsyncClient):
    resp = await client.post(
        "/api/chat/nonexistent-id",
        json={"message": "hello"},
    )
    assert resp.status_code == 404
