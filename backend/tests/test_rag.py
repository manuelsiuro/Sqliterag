from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_documents_empty(client: AsyncClient):
    resp = await client.get("/api/documents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_delete_nonexistent_document(client: AsyncClient):
    resp = await client.delete("/api/documents/nonexistent-id")
    assert resp.status_code == 404
