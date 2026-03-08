"""FrontendBridge — In-memory coordinator for frontend-executed tools.

The backend agent loop calls create_request() + await_result() to pause until
the frontend executes a command in the browser VM and POSTs the result back
via the /api/chat/tool-callback/{request_id} endpoint.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from time import monotonic

logger = logging.getLogger(__name__)


@dataclass
class PendingRequest:
    tool_name: str
    arguments: dict
    event: asyncio.Event = field(default_factory=asyncio.Event)
    result: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=monotonic)


class FrontendBridge:
    """Thread-safe bridge between the backend agent loop and frontend tool execution."""

    def __init__(self, default_timeout: float = 45.0) -> None:
        self._pending: dict[str, PendingRequest] = {}
        self._default_timeout = default_timeout

    def create_request(self, tool_name: str, arguments: dict) -> str:
        """Register a pending request. Returns a unique request_id (UUID)."""
        request_id = str(uuid.uuid4())
        self._pending[request_id] = PendingRequest(
            tool_name=tool_name,
            arguments=arguments,
        )
        logger.info("Frontend bridge: created request %s for %s", request_id, tool_name)
        return request_id

    async def await_result(self, request_id: str, timeout: float | None = None) -> str:
        """Block until the frontend submits a result, or timeout.

        Returns the result string, or an error message on timeout.
        """
        req = self._pending.get(request_id)
        if req is None:
            return "[ERROR] Unknown frontend bridge request."

        t = timeout or self._default_timeout
        try:
            await asyncio.wait_for(req.event.wait(), timeout=t)
        except asyncio.TimeoutError:
            logger.warning("Frontend bridge: request %s timed out after %.1fs", request_id, t)
            self._pending.pop(request_id, None)
            return "[TIMEOUT] Frontend did not respond within the time limit."

        result = req.error if req.error else (req.result or "")
        self._pending.pop(request_id, None)
        return result

    def submit_result(self, request_id: str, result: str | None = None, error: str | None = None) -> bool:
        """Called by the callback endpoint when the frontend sends back a result.

        Returns True if the request was found and signalled, False otherwise.
        """
        req = self._pending.get(request_id)
        if req is None:
            logger.warning("Frontend bridge: submit for unknown request %s", request_id)
            return False

        req.result = result
        req.error = error
        req.event.set()
        logger.info("Frontend bridge: result submitted for %s", request_id)
        return True

    def cleanup_stale(self, max_age: float = 120.0) -> int:
        """Remove orphaned requests older than max_age seconds. Returns count removed."""
        now = monotonic()
        stale = [rid for rid, req in self._pending.items() if now - req.created_at > max_age]
        for rid in stale:
            self._pending.pop(rid, None)
        if stale:
            logger.info("Frontend bridge: cleaned up %d stale requests", len(stale))
        return len(stale)
