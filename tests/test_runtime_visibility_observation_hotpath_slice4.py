"""Runtime Slice 4 regressions: exact-parity fast defensive cloning & authority resolve."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import fitz
import pytest

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus
from pb_source_observation_authority import (
    LINEAGE_UNAVAILABLE,
    OBSERVATION_UNAVAILABLE,
    PRODUCER_INTEGRITY_FAILURE,
    ObservationSelector,
    SourceObservationProducer,
    _clone_observation,
    _clone_result,
    _clone_revision,
    _clone_snapshot,
)
from pb_source_visibility_authority import _clone_evidence_atoms


def _make_sample_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400.0, height=300.0)
    for idx in range(5):
        s = page.new_shape()
        s.draw_line(fitz.Point(20.0, 20.0 + idx * 15.0), fitz.Point(220.0, 20.0 + idx * 15.0))
        s.finish(color=(0, 0, 0), width=0.5, closePath=False)
        s.commit()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_clone_evidence_atoms_matches_deepcopy_and_isolates_nested_mutations() -> None:
    assert _clone_evidence_atoms(()) == ()

    nested_meta = {
        "revision_id": "rev-1",
        "tuple_scalars": ("a", "b", 1, True, None),
        "nested_list": [1, {"k": "v"}],
        "nested_dict": {"inner": [10, 20]},
        "nested_set": {"x", "y"},
        "nested_tuple_mutable": (["m"], {"n": 2}),
    }
    atom = EvidenceAtom(
        evidence_id="ev_slice4_1",
        document_id="doc1",
        page_id="1",
        kind="dimension",
        method="native_dimension_cap_source_topology",
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("native_dimension_cap_tick_text_topology",),
        metadata=nested_meta,
    )
    orig = (atom,)
    cloned = _clone_evidence_atoms(orig)
    deep = deepcopy(orig)

    assert cloned == deep == orig
    assert cloned[0] is not orig[0]
    assert cloned[0].metadata is not orig[0].metadata

    # Mutating every mutable container in the clone MUST NOT affect the original
    cloned[0].metadata["revision_id"] = "tampered"
    cloned[0].metadata["nested_list"][1]["k"] = "tampered"
    cloned[0].metadata["nested_dict"]["inner"].append(999)
    cloned[0].metadata["nested_set"].add("z")
    cloned[0].metadata["nested_tuple_mutable"][0].append("bad")
    cloned[0].metadata["nested_tuple_mutable"][1]["n"] = -1

    assert orig[0].metadata["revision_id"] == "rev-1"
    assert orig[0].metadata["nested_list"] == [1, {"k": "v"}]
    assert orig[0].metadata["nested_dict"] == {"inner": [10, 20]}
    assert orig[0].metadata["nested_set"] == {"x", "y"}
    assert orig[0].metadata["nested_tuple_mutable"] == (["m"], {"n": 2})


def test_shallow_cloner_excludes_stray_attrs_and_rejects_unknown_fields() -> None:
    prod = SourceObservationProducer(producer_method="slice4_test", producer_version="1.0")
    pub = prod.ingest_native_pdf_bytes(
        document_id="doc_stray",
        source_bytes=_make_sample_pdf(),
        source_locator="synthetic.pdf",
    )
    rev = _clone_revision(pub.revision)
    object.__setattr__(rev, "stray_injected_field", "must_not_leak")
    rev_copy = _clone_revision(rev)
    assert rev_copy == pub.revision
    assert rev_copy is not rev
    assert not hasattr(rev_copy, "stray_injected_field")

    with pytest.raises(TypeError):
        _clone_revision(rev, nonexistent_field="x")
    with pytest.raises(TypeError):
        _clone_snapshot(pub.snapshot, nonexistent_field="x")

    auth = prod.authority()
    oid = pub.snapshot.observation_ids[0]
    sel = ObservationSelector(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,
        snapshot_id=pub.snapshot.snapshot_id,
        observation_id=oid,
    )
    res1 = auth.resolve(sel)
    assert res1.status is EvidenceResolutionStatus.CORROBORATED
    assert res1.observation is not None
    assert _clone_observation(res1.observation) == replace(res1.observation)
    assert _clone_result(res1) == replace(res1)
    with pytest.raises(TypeError):
        _clone_observation(res1.observation, nonexistent_field="x")
    with pytest.raises(TypeError):
        _clone_result(res1, nonexistent_field="x")


def test_resolve_defensive_clone_isolation_layered_get_and_lineage_checks() -> None:
    prod = SourceObservationProducer(producer_method="slice4_test", producer_version="1.0")
    pub = prod.ingest_native_pdf_bytes(
        document_id="doc_iso",
        source_bytes=_make_sample_pdf(),
        source_locator="synthetic.pdf",
    )
    auth = prod.authority()
    oid = pub.snapshot.observation_ids[0]
    sel = ObservationSelector(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,
        snapshot_id=pub.snapshot.snapshot_id,
        observation_id=oid,
    )

    # First read + cached read + flattened read must all return fresh isolated clones
    first = auth.resolve(sel)
    second = auth.resolve(sel)
    prod._store.observations.ensure_flat(pub.snapshot.snapshot_id)
    prod._store.record_fingerprints.ensure_flat(pub.snapshot.snapshot_id)
    third = auth.resolve(sel)

    assert first == second == third
    assert first is not second and second is not third
    assert first.observation is not second.observation
    assert first.source_revision is not second.source_revision
    assert first.snapshot is not second.snapshot

    # Defensive tamper via object.__setattr__ on returned values MUST NOT poison cache
    object.__setattr__(second.observation, "raw_text", "POISONED")
    object.__setattr__(second.source_revision, "source_locator", "POISONED")
    object.__setattr__(second, "proposition", "POISONED")
    fourth = auth.resolve(sel)
    assert fourth.observation.raw_text == first.observation.raw_text
    assert fourth.source_revision.source_locator == first.source_revision.source_locator
    assert fourth.proposition == first.proposition

    # _LayeredObservations.get and get_pair parity for missing keys
    assert prod._store.observations.get(("missing_snap", oid)) is None
    assert prod._store.observations.get((pub.snapshot.snapshot_id, "missing_obs"), "SENTINEL") == "SENTINEL"
    assert prod._store.observations.get("not_a_pair", "SENTINEL") == "SENTINEL"  # type: ignore[arg-type]
    assert prod._store.observations.get_pair(pub.snapshot.snapshot_id, oid) is not None

    # Derived observation with parent lineage resolves cleanly and fails closed if parent deleted
    derived_snap = prod.publish_derived_observations(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        base_snapshot_id=pub.snapshot.snapshot_id,
        observations=[
            {
                "page_id": "1",
                "source_partition_id": "derived_part",
                "observation_kind": "derived_segment",
                "source_primitive_ref": "derived_ref_1",
                "origin_kind": "derived_from_native",
                "parent_observation_ids": (oid,),
                "raw_text": "",
                "geometry": (0.0, 0.0, 10.0, 0.0),
            }
        ],
    )
    derived_id = next(i for i in derived_snap.observation_ids if i not in set(pub.snapshot.observation_ids))
    d_sel = ObservationSelector(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,
        snapshot_id=derived_snap.snapshot_id,
        observation_id=derived_id,
    )
    d_res = auth.resolve(d_sel)
    assert d_res.status is EvidenceResolutionStatus.CORROBORATED
    assert d_res.observation is not None and d_res.observation.snapshot_id == derived_snap.snapshot_id

    # Deleting parent in derived snapshot breaks lineage fail-closed
    del prod._store.observations[(derived_snap.snapshot_id, oid)]
    broken = auth.resolve(d_sel)
    assert broken.status is EvidenceResolutionStatus.ABSTAINED
    assert LINEAGE_UNAVAILABLE in broken.reason_codes

    # Missing observation still abstains cleanly
    missing = auth.resolve(replace(sel, observation_id="does_not_exist"))
    assert missing.status is EvidenceResolutionStatus.ABSTAINED
    assert OBSERVATION_UNAVAILABLE in missing.reason_codes

    # Tampered source bytes still fail closed with PRODUCER_INTEGRITY_FAILURE
    prod._store.source_bytes_by_revision[pub.revision.revision_id] = b"tampered-bytes"
    tampered = auth.resolve(sel)
    assert tampered.status is EvidenceResolutionStatus.CONFLICT
    assert PRODUCER_INTEGRITY_FAILURE in tampered.reason_codes
