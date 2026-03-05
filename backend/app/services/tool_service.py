from __future__ import annotations

import asyncio
import inspect
import json
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import Tool
from app.services.builtin_tools import BUILTIN_REGISTRY

logger = logging.getLogger(__name__)

# LLMs frequently send wrong parameter names (e.g. "class" instead of
# "char_class" because "class" is a Python reserved word).  Map them here
# so tool calls don't fail with unexpected-keyword errors.
_ARGUMENT_ALIASES: dict[str, dict[str, str]] = {
    "create_character": {"class": "char_class"},
    "roll_check": {"name": "character_name", "character": "character_name"},
    "roll_save": {"name": "character_name", "character": "character_name"},
    "attack": {"character": "attacker", "name": "attacker"},
    "talk_to_npc": {"name": "npc_name"},
    "npc_remember": {"name": "npc_name"},
    "update_npc_relationship": {"name": "npc_name"},
    "add_relationship": {"source": "source_name", "target": "target_name", "type": "relationship", "rel_type": "relationship"},
    "query_relationships": {"name": "entity_name", "type": "entity_type"},
    "get_entity_relationships": {"name": "entity_name", "type": "entity_type"},
}


class ToolService:
    async def execute_tool(
        self,
        tool: Tool,
        arguments: dict,
        *,
        session: AsyncSession | None = None,
        conversation_id: str | None = None,
        embedding_service=None,
        llm_service=None,
    ) -> str:
        try:
            if tool.execution_type == "http":
                return await self._execute_http(tool, arguments)
            elif tool.execution_type == "builtin":
                return await self._execute_builtin(
                    tool, arguments, session=session, conversation_id=conversation_id,
                    embedding_service=embedding_service,
                    llm_service=llm_service,
                )
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

    async def _execute_builtin(
        self,
        tool: Tool,
        arguments: dict,
        *,
        session: AsyncSession | None = None,
        conversation_id: str | None = None,
        embedding_service=None,
        llm_service=None,
    ) -> str:
        config = json.loads(tool.execution_config) if isinstance(tool.execution_config, str) else tool.execution_config
        func_name = config.get("function_name", "")
        func = BUILTIN_REGISTRY.get(func_name)
        if func is None:
            return f"[Unknown builtin function: {func_name}]"

        # Remap known argument aliases (e.g. "class" -> "char_class")
        aliases = _ARGUMENT_ALIASES.get(func_name)
        if aliases:
            for bad_name, good_name in aliases.items():
                if bad_name in arguments and good_name not in arguments:
                    arguments[good_name] = arguments.pop(bad_name)

        # Inject session/conversation_id for functions that accept them
        sig = inspect.signature(func)
        if "session" in sig.parameters and session is not None:
            arguments = {**arguments, "session": session}
        if "conversation_id" in sig.parameters and conversation_id is not None:
            arguments = {**arguments, "conversation_id": conversation_id}
        if "embedding_service" in sig.parameters and embedding_service is not None:
            arguments = {**arguments, "embedding_service": embedding_service}
        if "llm_service" in sig.parameters and llm_service is not None:
            arguments = {**arguments, "llm_service": llm_service}

        # Strip unknown arguments the LLM may hallucinate (e.g. "age",
        # "traits", "profession" for create_npc).  Only keep params that
        # the function actually accepts, unless it has **kwargs.
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        if not has_var_keyword:
            valid_params = set(sig.parameters)
            unknown = set(arguments) - valid_params
            if unknown:
                logger.warning(
                    "Stripping unknown args from %s: %s", func_name, unknown,
                )
                arguments = {k: v for k, v in arguments.items() if k in valid_params}

        result = func(**arguments)
        if asyncio.iscoroutine(result):
            result = await result
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
