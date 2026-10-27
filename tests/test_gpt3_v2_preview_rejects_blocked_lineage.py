"""Fail-closed V2 preview imports cannot launder blocked V1 source lineage.

This deliberately never authenticates an original PDF or publishes a V2 scope
receipt. The known V1 signed schema and historic fingerprints stay unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from pb_source_closed_run_export import (
    SourceClosedRunConflictError,
    seal_source_closed_run,
    sealed_source_closed_run_from_dict,
)
from pb_source_scope_sidecar_v2_preview import (
    _fingerprint,
    build_v2_preview_scope_sidecar,
    verify_v2_preview_scope_sidecar,
)
from test_source_closed_run_export import quantity, trace


def _pair(
    *,
    quantity_id: str = "qty-1",
    semantic_key: str = "room:food-prep:area",
    object_id: str = "canonical-floor-1",
    evidence_id: str = "ev-room-1",
    record_id: str = "source-record-1",
):
    original = quantity(
        quantity_id=quantity_id,
        semantic_key=semantic_key,
        input_entity_ids=(object_id,),
        evidence_ids=(evidence_id,),
        metadata={
            **quantity().metadata,
            "source_snapshot_id": "snapshot-original",
            "decision_scope_id": "scope-original",
            "source_scope_record_id": record_id,
        },
    )
    source = trace(
        canonical_entity_ids=(object_id,),
        evidence_ids=(evidence_id,),
        metadata={
            "evidence_snapshot_id": "snapshot-original",
            "decision_scope_id": "scope-original",
            "source_scope_record_id": record_id,
        },
    )
    return original, source


def _seal(pairs):
    return seal_source_closed_run(
        [q for q, _ in pairs],
        project_id="project-a",
        traces_by_quantity_id={q.quantity_id: t for q, t in pairs},
    )


def _resign_unpublished_preview(sidecar):
    # This is ONLY the preview's public SHA-256 checksum, not a source signature.
    sidecar["integrity_fingerprint"] = _fingerprint({
        key: value for key, value in sidecar.items()
        if key != "integrity_fingerprint"
    })


def test_healthy_preview_roundtrip_preserves_signed_v1_exactly():
    q, t = _pair()
    sealed = _seal([(q, t)])
    original = sealed.to_dict()
    sidecar = build_v2_preview_scope_sidecar(
        sealed, [q], {q.quantity_id: t},
    )
    before = deepcopy(sidecar)
    assert verify_v2_preview_scope_sidecar(sidecar, sealed)
    assert sealed_source_closed_run_from_dict(original).to_dict() == original
    assert sealed.to_dict() == original
    assert sidecar == before
    assert sidecar["source_authenticated"] is False
    assert sidecar["publication_status"] == "UNPUBLISHED"


def test_verifier_rejects_reshaed_preview_of_validly_sealed_but_blocked_v1_row():
    q, t = _pair()
    healthy = _seal([(q, t)])
    preview = build_v2_preview_scope_sidecar(
        healthy, [q], {q.quantity_id: t},
    )

    # A contradicted source document yields a consistent V1 fingerprint but
    # deliberately sets lineage_ok=False. The preview builder rejects this,
    # while the earlier verifier trusted the resignable preview checksum.
    contradicted = replace(
        q, metadata={**q.metadata, "document_id": "foreign-document"},
    )
    blocked = _seal([(contradicted, t)])
    assert blocked.quantities[0].lineage_ok is False
    assert "document_id_mismatch" in blocked.quantities[0].lineage_reason_codes
    assert sealed_source_closed_run_from_dict(blocked.to_dict()).to_dict() == blocked.to_dict()

    with pytest.raises(SourceClosedRunConflictError, match="differs from V1"):
        build_v2_preview_scope_sidecar(
            blocked, [contradicted], {contradicted.quantity_id: t},
        )

    attack = deepcopy(preview)
    attack["sealed_run_fingerprint"] = blocked.fingerprint
    attack["scope_records"][0]["sealed_quantity_fingerprint"] = (
        blocked.quantities[0].fingerprint
    )
    _resign_unpublished_preview(attack)
    with pytest.raises(SourceClosedRunConflictError, match="blocked V1 source lineage"):
        verify_v2_preview_scope_sidecar(attack, blocked)

    assert blocked.quantities[0].lineage_ok is False
    assert preview["sealed_run_fingerprint"] == healthy.fingerprint


def test_verifier_rejects_permuted_source_scope_rows_even_when_checksum_matches():
    first = _pair()
    second = _pair(
        quantity_id="qty-2",
        semantic_key="room:other:area",
        object_id="canonical-floor-2",
        evidence_id="ev-room-2",
        record_id="source-record-2",
    )
    sealed = _seal([second, first])
    quantities = [second[0], first[0]]
    traces = {q.quantity_id: t for q, t in [first, second]}
    preview = build_v2_preview_scope_sidecar(sealed, quantities, traces)
    assert [r["quantity_id"] for r in preview["scope_records"]] == [
        "qty-1", "qty-2",
    ]

    reordered = deepcopy(preview)
    reordered["scope_records"].reverse()
    _resign_unpublished_preview(reordered)
    with pytest.raises(SourceClosedRunConflictError, match="canonical sealed quantity order"):
        verify_v2_preview_scope_sidecar(reordered, sealed)
    assert verify_v2_preview_scope_sidecar(preview, sealed)
    assert sealed.to_dict() == _seal([first, second]).to_dict()
