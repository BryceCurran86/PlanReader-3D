"""Audit shared PlanReader rules for hardcoded benchmark job selectors.

This is a fail-closed *incremental regression guard*, not proof of full
repository generality. It only audits a deliberately enumerated set of
generic engine modules. Private SHA locks / drawing-specific fixtures belong
in source-admission adapters and tests, never in these common policy modules.

A known LEGACY exception is documented separately: the shared cross-view
floor/ceiling correspondence module still contains Maryborough page/room/
coordinate shortcuts (owner issue #4594). It is NOT approved as universal.
Leave it out of this regression gate until MAX/GPT2 replace the behaviour
with source-owned viewport/geometry registration and customer parity.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

_PROJECT = re.compile(
    r"(?:maryborough|acacia|q5446|3[_ -]?laurel|lot[_ -]?16)",
    re.IGNORECASE,
)
_HARDWIRED_SHA = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)

# Proven current-main generic producer paths; extend when a common producer is
# introduced. Never add source-specific adapters here as an excuse to delete
# private-original SHA authentication.
SHARED_PRODUCTION_RULES = (
    "pb_external_footprint_first_trace.py",
    "pb_physical_wall_candidate_authority.py",
    "pb_physical_opening_authority.py",
    "pb_opening_host_binding_authority.py",
    "pb_opening_host_frame_authority.py",
    "pb_live_opening_area_quantity_publication.py",
    "pb_live_floor_finish_customer_projection.py",
    "pb_live_ceiling_customer_projection.py",
    "pb_live_ceiling_area_customer_projection.py",
    "pb_live_wall_opening_authority_composition.py",
    "pb_source_floor_plan_page_scope.py",
    "pb_source_green_hatch_room_exclusion.py",
    "pb_source_internal_door_completeness_shadow.py",
    "pb_layered_wall_doorway_room_ring_shadow.py",
    "pb_source_room_trace_acceptance_runtime.py",
    "pb_new_source_trace_preview.py",
)
# Named, unresolved owner/P1 blocker; NOT a valid production exemption.
KNOWN_LEGACY_UNIVERSALISATION_BLOCKERS = (
    "pb_source_cross_view_floor_correspondence_shadow.py",
)


@dataclass(frozen=True)
class ProjectSpecificFinding:
    filename: str
    line: int
    kind: str
    literal: str


def audit_shared_source(source: str, *, filename: str) -> tuple[ProjectSpecificFinding, ...]:
    """Detect project identifiers or fixed SHA literals in executable AST.

    Docstrings are descriptive text and may mention test cases. Comments do not
    exist in AST. This catches named functions/variables and string/identity
    constants, but cannot decide whether arbitrary numeric thresholds have
    been overfit; cross-project visual/source replay remains mandatory.
    """
    tree = ast.parse(source, filename=filename)
    findings: list[ProjectSpecificFinding] = []

    def record(node: ast.AST, kind: str, value: str) -> None:
        if _PROJECT.search(value) or _HARDWIRED_SHA.fullmatch(value):
            findings.append(ProjectSpecificFinding(
                filename, getattr(node, "lineno", 1), kind, value[:120]
            ))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            record(node, "declaration", node.name)
        elif isinstance(node, ast.Name):
            record(node, "identifier", node.id)
        elif isinstance(node, ast.Attribute):
            record(node, "attribute", node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Skip only leading module/class/function docstrings; don't skip
            # ordinary expressions or string identities used by an algorithm.
            record(node, "constant", node.value)

    # Remove only true AST docstrings, not executable string predicates.
    docstring_nodes: set[ast.Constant] = set()
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if parent.body and isinstance(parent.body[0], ast.Expr):
                value = parent.body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    docstring_nodes.add(value)
    docstrings = {
        (getattr(node, "lineno", 1), "constant", node.value[:120])
        for node in docstring_nodes
    }
    findings = [
        item for item in findings
        if (item.line, item.kind, item.literal) not in docstrings
    ]
    # one physical source line can have repeated AST references
    return tuple(sorted(set(findings), key=lambda x: (x.line, x.kind, x.literal)))


def audit_paths(
    repository_root: Path,
    filenames: Iterable[str] = SHARED_PRODUCTION_RULES,
) -> tuple[ProjectSpecificFinding, ...]:
    result: list[ProjectSpecificFinding] = []
    for filename in filenames:
        path = repository_root / filename
        if not path.is_file():
            raise FileNotFoundError(f"unreviewed_shared_rule_missing:{filename}")
        result.extend(audit_shared_source(
            path.read_text(encoding="utf-8"), filename=filename,
        ))
    return tuple(result)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    results = audit_paths(root)
    for item in results:
        print(f"{item.filename}:{item.line}: {item.kind}: {item.literal}")
    print(f"audited_shared_rules={len(SHARED_PRODUCTION_RULES)}")
    print(f"unresolved_legacy_blockers={','.join(KNOWN_LEGACY_UNIVERSALISATION_BLOCKERS)}")
    return 1 if results else 0


if __name__ == "__main__":
    raise SystemExit(main())
