"""Shadow DPC consumes FIRM wall lengths and corroborated wall roles."""
from __future__ import annotations

import ast
from pathlib import Path

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_dpc_quantity import DpcScope, build_dpc_quantity, resolve_dpc_specification_scope
from pb_wall_boundary_role_authority import WallBoundaryRole, WallBoundaryRoleEvidence
from pb_wall_length_quantity import WALL_LENGTH_FAMILY

SHA = "c" * 64
REPO = Path(__file__).resolve().parents[1]


def _context(**overrides) -> ProviderContext:
    kwargs = dict(
        run_id="run",
        workspace_id="ws",
        project_id="project",
        document_id="doc",
        source_sha256=SHA,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(0,),
        owned_viewport_ids=("vp",),
        evidence_snapshot_id="evsnap",
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp", 1),),
    )
    kwargs.update(overrides)
    return ProviderContext(**kwargs)


def _document(ids=("ev",)) -> DocumentEvidence:
    return DocumentEvidence(
        document_id="doc",
        source_sha256=SHA,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=ids,
    )


def _viewport(viewport_id="vp") -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id="doc",
        page_id="page-1",
        bbox=(0.0, 0.0, 1000.0, 1000.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )


def _length(wall_id: str, value: float, *, abstained: bool = False) -> QuantityEvidence:
    if abstained:
        return QuantityEvidence(
            quantity_id=stable_contract_id("qty", {"w": wall_id, "a": True}),
            family=WALL_LENGTH_FAMILY,
            semantic_key=f"wall_length:{wall_id}",
            value=None,
            unit="m",
            input_entity_ids=(wall_id,),
            formula="test",
            formula_version="1.1.0",
            evidence_ids=("ev",),
            authority="unresolved",
            status=AuthorityStatus.BLOCKED.value,
            abstained=True,
            blocking_reasons=("scale_not_firm",),
        )
    return QuantityEvidence(
        quantity_id=stable_contract_id("qty", {"w": wall_id, "v": value}),
        family=WALL_LENGTH_FAMILY,
        semantic_key=f"wall_length:{wall_id}",
        value=value,
        unit="m",
        input_entity_ids=(wall_id,),
        formula="test",
        formula_version="1.1.0",
        evidence_ids=("ev",),
        authority="pdf_scaled",
        status=AuthorityStatus.FIRM.value,
        confidence=0.9,
    )


def _role(wall_id: str, role: WallBoundaryRole, *, status=EvidenceResolutionStatus.CORROBORATED, viewport_id="vp") -> WallBoundaryRoleEvidence:
    return WallBoundaryRoleEvidence(
        wall_candidate_id=wall_id,
        viewport_id=viewport_id,
        left_face_id="L",
        right_face_id="R",
        role=role,
        status=status,
        supporting_evidence_ids=("ev",),
        conflicting_evidence_ids=(),
        reason_codes=("test",),
        evidence_id=f"role-{wall_id}",
    )


def _dpc(lengths, roles, text, **kwargs):
    return build_dpc_quantity(
        wall_lengths=lengths,
        roles=roles,
        page_text=text,
        context=kwargs.get("context", _context()),
        document=kwargs.get("document", _document()),
        viewport=kwargs.get("viewport", _viewport()),
        page_no=kwargs.get("page_no", 1),
    )


def test_all_walls_scope_sums_external_and_internal() -> None:
    qty = _dpc(
        (_length("w-ext", 10.0), _length("w-int", 4.0)),
        (_role("w-ext", WallBoundaryRole.EXTERNAL), _role("w-int", WallBoundaryRole.INTERNAL_PARTITION)),
        "DPC to be of bituminous felt provided under all walls on ground floor.",
    )
    assert qty.abstained is False
    assert qty.value == 14.0
    assert qty.metadata["dpc_scope"] == DpcScope.ALL_WALLS.value


def test_external_only_excludes_internal_partition() -> None:
    qty = _dpc(
        (_length("w-ext", 10.0), _length("w-int", 4.0)),
        (_role("w-ext", WallBoundaryRole.EXTERNAL), _role("w-int", WallBoundaryRole.INTERNAL_PARTITION)),
        "DPC to be laid to external walls only.",
    )
    assert qty.abstained is False
    assert qty.value == 10.0
    assert "w-int" not in qty.input_entity_ids


def test_internal_only_excludes_external() -> None:
    qty = _dpc(
        (_length("w-ext", 10.0), _length("w-int", 4.0)),
        (_role("w-ext", WallBoundaryRole.EXTERNAL), _role("w-int", WallBoundaryRole.INTERNAL_PARTITION)),
        "Damp proof course to internal partitions only.",
    )
    assert qty.abstained is False
    assert qty.value == 4.0


def test_ambiguous_scope_abstains() -> None:
    qty = _dpc(
        (_length("w-ext", 10.0),),
        (_role("w-ext", WallBoundaryRole.EXTERNAL),),
        "Provide DPC as specified.",
    )
    assert qty.abstained
    assert "dpc_scope_not_explicit" in qty.blocking_reasons


def test_conflicting_scope_notes_abstain() -> None:
    qty = _dpc(
        (_length("w-ext", 10.0),),
        (_role("w-ext", WallBoundaryRole.EXTERNAL),),
        "DPC to external walls only.\nDPC to internal partitions only.",
    )
    assert qty.abstained
    assert qty.metadata["dpc_scope"] in (DpcScope.CONFLICT.value, DpcScope.AMBIGUOUS.value)


def test_missing_scale_length_is_not_invented() -> None:
    qty = _dpc(
        (_length("w-ext", 10.0, abstained=True),),
        (_role("w-ext", WallBoundaryRole.EXTERNAL),),
        "DPC to external walls.",
    )
    assert qty.abstained
    assert "no_firm_in_scope_wall_lengths" in qty.blocking_reasons


def test_duplicate_wall_length_identity_abstains() -> None:
    bad = QuantityEvidence(
        quantity_id="dup",
        family=WALL_LENGTH_FAMILY,
        semantic_key="wall_length:dup",
        value=3.0,
        unit="m",
        input_entity_ids=("w-a", "w-b"),
        formula="test",
        formula_version="1",
        evidence_ids=("ev",),
        authority="pdf_scaled",
        status=AuthorityStatus.FIRM.value,
    )
    qty = _dpc(
        (bad,),
        (_role("w-a", WallBoundaryRole.EXTERNAL), _role("w-b", WallBoundaryRole.EXTERNAL)),
        "DPC to external walls.",
    )
    assert qty.abstained
    assert "wall_length_identity_not_unique" in qty.blocking_reasons


def test_wrong_viewport_role_cannot_leak() -> None:
    qty = _dpc(
        (_length("w-ext", 10.0),),
        (_role("w-ext", WallBoundaryRole.EXTERNAL, viewport_id="other-vp"),),
        "DPC to external walls.",
    )
    assert qty.abstained
    assert "dpc_role_viewport_mismatch" in qty.blocking_reasons


def test_spec_from_unrelated_document_cannot_apply() -> None:
    qty = _dpc(
        (_length("w-ext", 10.0),),
        (_role("w-ext", WallBoundaryRole.EXTERNAL),),
        "DPC to external walls.",
        document=DocumentEvidence(
            document_id="other-doc",
            source_sha256=SHA,
            page_count=1,
            page_ids=("page-1",),
            evidence_ids=("ev",),
        ),
    )
    assert qty.abstained
    assert "dpc_document_mismatch" in qty.blocking_reasons


def test_unknown_role_on_firm_length_abstains() -> None:
    qty = _dpc(
        (_length("w-ext", 10.0),),
        (_role("w-ext", WallBoundaryRole.UNKNOWN),),
        "DPC to external walls.",
    )
    assert qty.abstained
    assert "firm_wall_length_role_not_external_or_internal" in qty.blocking_reasons


def test_no_specification_abstains() -> None:
    assert resolve_dpc_specification_scope("plaster to walls")[0] == DpcScope.ABSENT
    qty = _dpc(
        (_length("w-ext", 10.0),),
        (_role("w-ext", WallBoundaryRole.EXTERNAL),),
        "plaster to walls",
    )
    assert qty.abstained


def test_extractor_does_not_import_shadow_dpc() -> None:
    tree = ast.parse((REPO / "pb_planreader_pdf_extractor.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert "pb_dpc_quantity" not in names
    assert "pb_wall_boundary_role_authority" not in names
    assert "pb_wall_length_quantity" not in names
