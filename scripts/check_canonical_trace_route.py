"""Dependency-free CI guard: original PlanReader trace UI and approved runner must stay canonical."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _parse(root: Path, relative_path: str) -> ast.Module:
    return ast.parse((root / relative_path).read_text(encoding="utf-8-sig"))


def _function(module: ast.Module, name: str) -> ast.FunctionDef:
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(functions) != 1:
        raise AssertionError(f"CANONICAL_TRACE_ROUTE_BLOCKED: expected one {name}")
    return functions[0]


def _calls(node: ast.AST) -> set[str]:
    return {
        n.func.id if isinstance(n.func, ast.Name) else n.func.attr
        for n in ast.walk(node) if isinstance(n, ast.Call)
        and isinstance(n.func, (ast.Name, ast.Attribute))
    }


def verify_route_contract(root: Path = ROOT) -> None:
    app = _function(_parse(root, "pb_planreader_3d_app.py"), "plan_mapper_page")
    if "source_native_trace_preview" not in _calls(app):
        raise AssertionError("CANONICAL_TRACE_ROUTE_BLOCKED: original app stopped using native trace preview")
    if {"auto_detect_building_envelope", "auto_detect_envelope_shapes"} & _calls(app):
        raise AssertionError("CANONICAL_TRACE_ROUTE_BLOCKED: old envelope fallback reintroduced to drawing UI")

    preview = _function(_parse(root, "pb_new_source_trace_preview.py"), "source_native_trace_preview")
    if "attempt_source_native_outer_wall_first" not in _calls(preview):
        raise AssertionError("CANONICAL_TRACE_ROUTE_BLOCKED: original native outside-wall producer not called")
    if "build_layered_wall_doorway_room_rings" not in _calls(preview):
        raise AssertionError("CANONICAL_TRACE_ROUTE_BLOCKED: native doorway/room producer not called")
    if {"auto_detect_building_envelope", "auto_detect_envelope_shapes"} & _calls(preview):
        raise AssertionError("CANONICAL_TRACE_ROUTE_BLOCKED: old auto envelope used by native preview")

    runner = _parse(root, "tools/run_canonical_source_native_preview.py")
    if not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "pb_new_source_trace_preview"
        and any(alias.name == "source_native_trace_preview" for alias in node.names)
        for node in ast.walk(runner)
    ):
        raise AssertionError("CANONICAL_TRACE_ROUTE_BLOCKED: approved preview runner rerouted")
    execute = _function(runner, "run_preview")
    if "source_native_trace_preview" not in _calls(execute):
        raise AssertionError("CANONICAL_TRACE_ROUTE_BLOCKED: approved preview runner does not execute native preview")


if __name__ == "__main__":
    verify_route_contract()
    print("CANONICAL_TRACE_ROUTE_OK: original UI and exact-head runner preserve source-native engine")
