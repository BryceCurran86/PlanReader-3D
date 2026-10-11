"""V2-preview sidecars preserve exact scope receipts, never certify PDF authority."""
from dataclasses import replace
import copy
import pytest

from pb_source_closed_run_export import (
    SourceClosedRunConflictError,seal_source_closed_run,
)
from pb_source_scope_sidecar_v2_preview import (
    SCOPE_SIDECAR_SCHEMA,SCOPE_NOT_AUTHENTICATED,
    build_v2_preview_scope_sidecar,verify_v2_preview_scope_sidecar,_fingerprint,
)
from test_source_closed_run_export import quantity,trace


def _pair(qid="qty-1",snapshot="snap-a",scope="scope-a",record="source-record-a"):
    q=quantity(quantity_id=qid,metadata={
        **quantity().metadata,
        "evidence_snapshot_id":snapshot,
        "decision_scope_id":scope,
        "source_scope_record_id":record,
    })
    t=trace(metadata={
        "source_snapshot_id":snapshot,
        "decision_scope_id":scope,
        "source_scope_record_id":record,
    })
    return q,t


def _run(qs):
    return seal_source_closed_run([q for q,t in qs],project_id="project-a",
                                  traces_by_quantity_id={q.quantity_id:t for q,t in qs})


def test_source_scope_sidecar_binds_v1_quantity_and_run_without_changing_fingerprints():
    q,t=_pair()
    sealed=_run([(q,t)])
    original_fp=sealed.fingerprint
    sidecar=build_v2_preview_scope_sidecar(sealed,[q],{q.quantity_id:t})
    assert sidecar["schema_version"]==SCOPE_SIDECAR_SCHEMA
    assert sidecar["publication_status"]=="UNPUBLISHED"
    assert sidecar["source_authenticated"] is False
    assert sidecar["sealed_run_fingerprint"]==original_fp
    assert sidecar["scope_records"][0]["source_record_authentication"]==SCOPE_NOT_AUTHENTICATED
    assert sidecar["scope_records"][0]["source_snapshot_id"]=="snap-a"
    assert sidecar["scope_records"][0]["decision_scope_id"]=="scope-a"
    assert verify_v2_preview_scope_sidecar(sidecar,sealed) is True
    assert sealed.fingerprint==original_fp


@pytest.mark.parametrize("qmeta_override",[
    {"evidence_snapshot_id":""},
    {"evidence_snapshot_id":"snap-other"},
    {"decision_scope_id":"scope-other"},
    {"source_scope_record_id":"wrong-record"},
    {"snapshot_id":"snap-conflicting-alias"},
])
def test_malformed_or_disagreeing_producer_scope_cannot_build_sidecar(qmeta_override):
    q,t=_pair()
    q=replace(q,metadata={**q.metadata,**qmeta_override})
    sealed=_run([(q,t)])
    with pytest.raises(SourceClosedRunConflictError):
        build_v2_preview_scope_sidecar(sealed,[q],{q.quantity_id:t})


def test_missing_original_source_scope_identity_is_not_inferred_from_pdf_sha():
    q=quantity()
    t=trace()
    sealed=_run([(q,t)])
    with pytest.raises(SourceClosedRunConflictError,match="producer receipt missing"):
        build_v2_preview_scope_sidecar(sealed,[q],{q.quantity_id:t})


def test_scope_sidecar_cannot_reuse_one_producer_record_for_two_quantities():
    q1,t1=_pair()
    q2=quantity(quantity_id="qty-2",semantic_key="room:second:area",
                input_entity_ids=("canonical-floor-2",),evidence_ids=("ev-room-2",),
                metadata={**quantity().metadata,
                "evidence_snapshot_id":"snap-a","decision_scope_id":"scope-a",
                "source_scope_record_id":"source-record-a"})
    t2=trace(canonical_entity_ids=("canonical-floor-2",),evidence_ids=("ev-room-2",),
             metadata={"source_snapshot_id":"snap-a","decision_scope_id":"scope-a",
                       "source_scope_record_id":"source-record-a"})
    sealed=_run([(q1,t1),(q2,t2)])
    with pytest.raises(SourceClosedRunConflictError,match="reused"):
        build_v2_preview_scope_sidecar(
            sealed,[q1,q2],{q1.quantity_id:t1,q2.quantity_id:t2},
        )


def test_tampered_scope_id_breaks_sidecar_integrity():
    q,t=_pair()
    sealed=_run([(q,t)])
    original=build_v2_preview_scope_sidecar(sealed,[q],{q.quantity_id:t})
    corrupted=copy.deepcopy(original)
    corrupted["scope_records"][0]["decision_scope_id"]="scope-forged"
    with pytest.raises(SourceClosedRunConflictError,match="integrity fingerprint mismatch"):
        verify_v2_preview_scope_sidecar(corrupted,sealed)


def test_sidecar_cannot_attach_to_another_valid_sealed_source_revision():
    q,t=_pair()
    sealed=_run([(q,t)])
    original=build_v2_preview_scope_sidecar(sealed,[q],{q.quantity_id:t})
    q2=replace(q,quantity_id="qty-revision-two",semantic_key="room:revised:area")
    newer=_run([(q2,t)])
    with pytest.raises(SourceClosedRunConflictError,match="not bound to exact V1"):
        verify_v2_preview_scope_sidecar(original,newer)


def test_resigned_self_attested_metadata_never_becomes_original_source_proof():
    q,t=_pair()
    sealed=_run([(q,t)])
    payload=build_v2_preview_scope_sidecar(sealed,[q],{q.quantity_id:t})
    altered=copy.deepcopy(payload)
    altered["scope_records"][0]["decision_scope_id"]="unverified-claim"
    body={k:v for k,v in altered.items() if k!="integrity_fingerprint"}
    altered["integrity_fingerprint"]=_fingerprint(body)
    assert verify_v2_preview_scope_sidecar(altered,sealed) is True
    # The sidecar only establishes integrity/linkage, NOT upstream ownership.
    assert altered["source_authenticated"] is False
    assert altered["scope_records"][0]["source_record_authentication"]==SCOPE_NOT_AUTHENTICATED


def test_missing_canonical_quantity_receipt_is_not_promoted_by_scope_metadata():
    q,t=_pair()
    sealed=_run([(q,t)])
    fake=replace(q,value=999.0)
    with pytest.raises(SourceClosedRunConflictError,match="differs from V1"):
        build_v2_preview_scope_sidecar(sealed,[fake],{fake.quantity_id:t})
