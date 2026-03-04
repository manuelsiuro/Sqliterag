"""Tool call validation pipeline (Phase 1.6).

Validates and repairs LLM tool calls before execution:
1. Fuzzy name matching (exact → case-insensitive → Levenshtein ≤ 2)
2. JSON argument repair (json_repair fallback)
3. Type coercion (string→int, string→bool, etc.)
4. Required field validation
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    tool_name: str
    arguments: dict
    corrections: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def validate_tool_call(
    raw_name: str,
    raw_arguments: dict | str,
    tool_map: dict,
) -> ValidationResult:
    """Run the full validation pipeline on a single tool call.

    Args:
        raw_name: Tool name as provided by the LLM.
        raw_arguments: Arguments dict (or string if LLM sent raw JSON).
        tool_map: Mapping of tool_name → Tool object (has .parameters_schema).

    Returns:
        ValidationResult with resolved name, repaired arguments, and any
        corrections/errors.
    """
    corrections: list[str] = []
    errors: list[str] = []

    # 1. Fuzzy name match
    resolved_name, name_correction = _fuzzy_match_name(raw_name, tool_map)
    if name_correction:
        corrections.append(name_correction)
    if resolved_name is None:
        errors.append(f"Unknown tool '{raw_name}'")
        return ValidationResult(
            tool_name=raw_name,
            arguments=raw_arguments if isinstance(raw_arguments, dict) else {},
            corrections=corrections,
            errors=errors,
        )

    # 2. JSON repair
    arguments, json_correction = _repair_arguments(raw_arguments)
    if json_correction:
        corrections.append(json_correction)
    if arguments is None:
        errors.append("Could not parse tool arguments as JSON")
        return ValidationResult(
            tool_name=resolved_name,
            arguments={},
            corrections=corrections,
            errors=errors,
        )

    # 3. Get tool schema for type coercion + required check
    tool = tool_map[resolved_name]
    schema = _get_schema(tool)

    # 4. Type coercion
    if schema:
        arguments, coercion_corrections = _coerce_types(arguments, schema)
        corrections.extend(coercion_corrections)

    # 5. Required field check
    if schema:
        missing_errors = _validate_required(arguments, schema)
        errors.extend(missing_errors)

    if corrections:
        logger.info(
            "Tool call '%s' corrections: %s",
            resolved_name,
            "; ".join(corrections),
        )

    return ValidationResult(
        tool_name=resolved_name,
        arguments=arguments,
        corrections=corrections,
        errors=errors,
    )


def _get_schema(tool) -> dict | None:
    """Extract the parameters schema dict from a Tool object."""
    try:
        raw = tool.parameters_schema
        if isinstance(raw, str):
            return json.loads(raw)
        if isinstance(raw, dict):
            return raw
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


# ---------------------------------------------------------------------------
# 1. Fuzzy name matching
# ---------------------------------------------------------------------------

def _fuzzy_match_name(
    name: str, candidates: dict,
) -> tuple[str | None, str | None]:
    """Resolve a tool name with three-tier matching.

    Returns (resolved_name, correction_message) or (None, None) if no match.
    """
    # Tier 1: exact match
    if name in candidates:
        return name, None

    # Tier 2: case-insensitive
    lower_map = {k.lower(): k for k in candidates}
    lower_name = name.lower()
    if lower_name in lower_map:
        resolved = lower_map[lower_name]
        return resolved, f"name '{name}' → '{resolved}' (case fix)"

    # Tier 3: Levenshtein distance ≤ 2, unambiguous best match
    best_name = None
    best_dist = 3  # threshold + 1
    ambiguous = False

    for candidate in candidates:
        d = _levenshtein(lower_name, candidate.lower())
        if d < best_dist:
            best_dist = d
            best_name = candidate
            ambiguous = False
        elif d == best_dist and candidate != best_name:
            ambiguous = True

    if best_name is not None and best_dist <= 2 and not ambiguous:
        return best_name, f"name '{name}' → '{best_name}' (fuzzy, dist={best_dist})"

    return None, None


def _levenshtein(s: str, t: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    n, m = len(s), len(t)
    if n == 0:
        return m
    if m == 0:
        return n

    # Use single-row DP for space efficiency
    prev = list(range(m + 1))
    curr = [0] * (m + 1)

    for i in range(1, n + 1):
        curr[0] = i
        for j in range(1, m + 1):
            cost = 0 if s[i - 1] == t[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,      # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev, curr = curr, prev

    return prev[m]


# ---------------------------------------------------------------------------
# 2. JSON argument repair
# ---------------------------------------------------------------------------

def _repair_arguments(raw) -> tuple[dict | None, str | None]:
    """Ensure arguments are a dict, repairing JSON if needed.

    Returns (arguments_dict, correction_message) or (None, error_msg).
    """
    if isinstance(raw, dict):
        return raw, None

    if not isinstance(raw, str):
        try:
            return dict(raw), None
        except (TypeError, ValueError):
            return None, None

    # Try standard json.loads first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed, "arguments: parsed from JSON string"
        return None, None
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback to json_repair
    try:
        import json_repair
        parsed = json_repair.loads(raw)
        if isinstance(parsed, dict):
            return parsed, "arguments: repaired malformed JSON"
        return None, None
    except ImportError:
        logger.debug("json_repair not installed, skipping repair fallback")
        return None, None
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# 3. Type coercion
# ---------------------------------------------------------------------------

_BOOL_TRUE = frozenset({"true", "1", "yes"})
_BOOL_FALSE = frozenset({"false", "0", "no"})


def _coerce_types(
    arguments: dict, schema: dict,
) -> tuple[dict, list[str]]:
    """Coerce argument values to match schema types.

    Returns (coerced_arguments, list_of_corrections).
    """
    properties = schema.get("properties", {})
    corrections: list[str] = []
    result = dict(arguments)

    for key, value in result.items():
        if key not in properties:
            continue

        prop = properties[key]
        expected = prop.get("type")
        if expected is None:
            continue

        coerced, corrected = _coerce_value(value, expected, key)
        if corrected:
            result[key] = coerced
            corrections.append(corrected)

    return result, corrections


def _coerce_value(value, expected_type: str, key: str):
    """Coerce a single value to the expected type.

    Returns (coerced_value, correction_message_or_None).
    """
    if expected_type == "integer":
        if isinstance(value, int) and not isinstance(value, bool):
            return value, None
        if isinstance(value, str):
            try:
                return int(value), f"'{key}': str→int"
            except ValueError:
                return value, None
        if isinstance(value, float):
            return int(value), f"'{key}': float→int"

    elif expected_type == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value, None
        if isinstance(value, str):
            try:
                return float(value), f"'{key}': str→number"
            except ValueError:
                return value, None

    elif expected_type == "boolean":
        if isinstance(value, bool):
            return value, None
        if isinstance(value, str):
            low = value.lower()
            if low in _BOOL_TRUE:
                return True, f"'{key}': str→bool"
            if low in _BOOL_FALSE:
                return False, f"'{key}': str→bool"
        if isinstance(value, (int, float)):
            return bool(value), f"'{key}': num→bool"

    elif expected_type == "string":
        if isinstance(value, str):
            return value, None
        return str(value), f"'{key}': {type(value).__name__}→str"

    elif expected_type == "array":
        if isinstance(value, list):
            return value, None
        if isinstance(value, str):
            # Try JSON array first
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed, f"'{key}': JSON str→array"
            except (json.JSONDecodeError, ValueError):
                pass
            # Comma-separated fallback
            return [v.strip() for v in value.split(",")], f"'{key}': csv str→array"

    return value, None


# ---------------------------------------------------------------------------
# 4. Required field validation
# ---------------------------------------------------------------------------

def _validate_required(
    arguments: dict, schema: dict,
) -> list[str]:
    """Check for missing required fields.

    Returns list of error messages for missing fields.
    """
    required = schema.get("required", [])
    missing = [f for f in required if f not in arguments]
    if missing:
        return [f"Missing required parameter(s): {', '.join(missing)}"]
    return []
