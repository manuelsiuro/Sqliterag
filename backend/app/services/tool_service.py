from __future__ import annotations

import json
import logging

import httpx

from app.models.tool import Tool

logger = logging.getLogger(__name__)


class ToolService:
    async def execute_tool(self, tool: Tool, arguments: dict) -> str:
        try:
            if tool.execution_type == "http":
                return await self._execute_http(tool, arguments)
            return self._execute_mock(tool, arguments)
        except Exception as e:
            logger.exception("Tool execution failed for %s", tool.name)
            return f"[Error executing {tool.name}: {e}]"

    async def _execute_http(self, tool: Tool, arguments: dict) -> str:
        config = json.loads(tool.execution_config) if isinstance(tool.execution_config, str) else tool.execution_config
        url_template = config.get("url", "")
        method = config.get("method", "GET").upper()
        headers = config.get("headers", {})

        url = url_template.format(**arguments)

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "POST":
                resp = await client.post(url, headers=headers, json=arguments)
            else:
                resp = await client.request(method, url, headers=headers)

            resp.raise_for_status()
            result = resp.text
            # Truncate to 4000 chars
            if len(result) > 4000:
                result = result[:4000] + "... [truncated]"
            return result

    def _execute_mock(self, tool: Tool, arguments: dict) -> str:
        args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        return f"[Mock result for {tool.name}({args_str})]"

    def build_ollama_tools(self, tools: list[Tool]) -> list[dict]:
        result = []
        for tool in tools:
            schema = json.loads(tool.parameters_schema) if isinstance(tool.parameters_schema, str) else tool.parameters_schema
            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": schema,
                },
            })
        return result
