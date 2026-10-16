"""Import-safe strict JSON reader for persisted signed evidence and customer metadata.

A production module must never import a repository ``scripts/`` utility: ``scripts`` is a namespace package that exists
only when the repository root is on ``sys.path``.  This stdlib-only module carries the same strict semantics as the
readiness parser (``scripts.report_full_plan_v2_readiness._parse_evidence_json``) so production code can depend on it
from any working directory or install layout.  A parity test pins the two implementations to identical accept/reject
behaviour and identical messages; neither reads, hashes or changes any source, signature or benchmark file.

Rejected before any value can reach source/customer verification: duplicated object keys (nested included),
``NaN`` / ``Infinity`` / ``-Infinity``, float literals that overflow to infinity, integers whose magnitude is not finite
as a float, and pathological object/array nesting.
"""
from __future__ import annotations

import json
import math

MAX_JSON_NESTING_DEPTH = 512

__all__ = ["MAX_JSON_NESTING_DEPTH", "parse_strict_evidence_json"]


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicated object keys before one may shadow source identity."""
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json_constant(token: str) -> None:
    """NaN and Infinity are not JSON numbers or admissible source evidence."""
    raise ValueError(f"non-finite JSON number: {token}")


def _finite_json_float(token: str) -> float:
    """Reject finite-looking JSON numeric literals that overflow to infinity."""
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON floating-point value")
    return value


def _finite_json_int(token: str) -> int:
    """Keep oversized JSON integers from overflowing numeric parity checks."""
    value = int(token)
    try:
        finite_as_float = math.isfinite(value)
    except OverflowError:
        finite_as_float = False
    if not finite_as_float:
        raise ValueError("out-of-range JSON integer magnitude")
    return value


def parse_strict_evidence_json(payload: str) -> object:
    """Parse one JSON document strictly; raises ``ValueError`` (``json.JSONDecodeError`` included) on any violation."""
    # Guard genuine JSON object/array nesting before parsing, ignoring bracket characters inside properly quoted and
    # escaped strings.  This is a complexity safeguard, not source/evaluator schema inference.
    depth = 0
    in_string = False
    escaped = False
    for character in payload:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_NESTING_DEPTH:
                raise ValueError("JSON nesting exceeds safe parser depth")
        elif character in "]}":
            depth -= 1
    # Preserve the native parser's validation of mismatched braces, malformed escapes and all strict key/number checks.
    try:
        return json.loads(
            payload,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_nonfinite_json_constant,
            parse_float=_finite_json_float,
            parse_int=_finite_json_int,
        )
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds safe parser depth") from exc
