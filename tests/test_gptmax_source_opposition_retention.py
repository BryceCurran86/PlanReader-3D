"""Source opposition must never explain a lost firm host or borrowed identity."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_migration_contracts import stable_contract_id, EvidenceResolutionStatus
from pb_physical_opening_authority import _physical_opening_geometry_identity
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from scripts.gptmax_source_opposition_retention import compare_opposed_source_reports,_validate_opposition
from test_native_unstroked_fill_evidence import _source
from test_native_dimension_cap_evidence import _source as _dimension_source


def _reports(**kwargs):
    fixture, published, _, _ = _source(**kwargs)
    data = fixture._producer._store.source_bytes_by_revision[published.revision.revision_id]
    return _reports_from_bytes(data)


def _reports_from_bytes(data):
    digest = sha256(data).hexdigest()
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = source.ingest_native_pdf_bytes(document_id=f"live-source:{digest[:32]}",
        source_bytes=data, source_locator="memory://live-physical-net-wall-source.pdf", page_ids=("1",))
    physical = source.physical_opening_authority()
    for oid in published.visible_observation_ids:
        selector = ObservationSelector(published.revision.document_id, published.revision.revision_id,
            digest, published.snapshot.snapshot_id, oid)
        result = physical.prove_existence(selector)
        if result.candidate is not None:
            break
    else:
        raise AssertionError("synthetic native candidate unavailable")
    candidate = result.candidate
    records = [source.authority().resolve_visible(replace(selector, observation_id=i)).observation
        for i in candidate.source_observation_ids]
    identity = stable_contract_id("physical_opening_existence", {
        "document_id": candidate.document_id, "revision_id": candidate.revision_id,
        "source_sha256": digest, "page_id": candidate.page_id, "semantic_class": "opening",
        "source_geometry": _physical_opening_geometry_identity(candidate, records),
    }, digest_chars=32)
    # A hypothetical old unhosted claim is exactly keyed to real source lines.
    old = {"source_sha256": digest, "selected_geometry_page_ids": ["1"],
        "primitive_safety_cap": 20000,
        "opening_bindings": [{"opening_identity_id": identity, "page_id": "1",
            "representative_observation_id": oid, "status": "abstained",
            "host_wall_id": None, "record_id": None}],
        "host_frames": [{"opening_identity_id": identity, "record_id": None}]}
    after = dict(deepcopy(old), opening_bindings=[], host_frames=[])
    return data, old, after


@pytest.mark.parametrize('image', [False,True])
def test_exact_original_dimension_opposition_can_explain_only_unproven_claim(image):
    source,published,_selector,_support=_dimension_source(image=image)
    data=source._producer._store.source_bytes_by_revision[published.revision.revision_id]
    data,old,after=_reports_from_bytes(data)
    before=deepcopy((old,after))
    result=compare_opposed_source_reports(old,after,source_bytes=data)
    assert result['retention_pass']
    proof,=result['source_opposed_missing_claims']
    assert proof['opening_identity_id']==old['opening_bindings'][0]['opening_identity_id']
    assert all(a['kind']=='dimension_annotation' for a in proof['opposing_evidence_atoms'])
    assert not proof['physical_nonexistence_proven']
    assert not result['host_publication_allowed']
    assert (old,after)==before
    assert compare_opposed_source_reports(old,after,source_bytes=data)==result


@pytest.mark.parametrize('damage', ['revision','snapshot','page','polarity','firm',
    'missing_selected','duplicate_selected','foreign_component','missing_text','partial_union'])
def test_dimension_opposition_cannot_borrow_source_scope_or_partial_components(damage):
    source,_published,selector,_support=_dimension_source(image=True)
    result=source.physical_opening_authority().prove_existence(selector)
    assert result.candidate is not None and result.opposing_evidence_atoms
    atoms=list(result.opposing_evidence_atoms)
    atom=atoms[0];metadata=dict(atom.metadata)
    if damage=='revision': metadata['revision_id']='foreign'
    elif damage=='snapshot': metadata['snapshot_id']='stale'
    elif damage=='page': atom=replace(atom,page_id='2')
    elif damage=='polarity': metadata['polarity']='supporting'
    elif damage=='firm': atom=replace(atom,status=EvidenceResolutionStatus.CORROBORATED)
    elif damage=='missing_selected':
        metadata['opening_support_observation_ids']=list(metadata['opening_support_observation_ids'])[:-1]
    elif damage=='duplicate_selected':
        values=list(metadata['opening_support_observation_ids']);metadata['opening_support_observation_ids']=values+[values[0]]
    elif damage=='foreign_component':
        metadata['source_observation_ids']=list(metadata['source_observation_ids'])+['foreign']
    elif damage=='missing_text': metadata['text_observation_id']='foreign-text'
    else: atoms=atoms[:1]
    atoms[0]=replace(atom,metadata=metadata)
    damaged=replace(result,opposing_evidence_atoms=tuple(atoms))
    with pytest.raises(ValueError):
        _validate_opposition(source,selector,result.candidate,damaged)


@pytest.mark.parametrize('proof', ['host','frame'])
def test_native_dimension_opposition_does_not_allow_losing_firm_proof(proof):
    source,published,_selector,_support=_dimension_source(image=True)
    data=source._producer._store.source_bytes_by_revision[published.revision.revision_id]
    data,old,after=_reports_from_bytes(data)
    if proof=='host': old['opening_bindings'][0]['host_wall_id']='original-wall'
    else: old['host_frames'][0]['record_id']='original-frame'
    with pytest.raises(ValueError,match='cannot remove'):
        compare_opposed_source_reports(old,after,source_bytes=data)


@pytest.mark.parametrize("kwargs", [{}, {"fill": (.96, .96, .96)},
    {"dx": 21, "dy": 15}, {"scale": .5}, {"scale": 2},
    {"rotation": 90}, {"unrelated": True}])
def test_only_exact_original_fill_opposition_explains_unhosted_claim(kwargs):
    data, old, after = _reports(**kwargs)
    inputs = deepcopy((old, after))
    r = compare_opposed_source_reports(old, after, source_bytes=data)
    assert r["retention_pass"]
    assert r["source_opposition_freshly_reauthenticated"]
    assert len(r["source_opposed_missing_claims"]) == 1
    assert r["source_opposed_missing_claims"][0]["opening_identity_id"] == old["opening_bindings"][0]["opening_identity_id"]
    for flag in ("quantity_publication_permitted", "host_publication_allowed",
                 "opening_count_publication_allowed", "metric_quantity_publication_allowed",
                 "hypotheses_deletion_allowed"):
        assert r[flag] is False
    assert r["benchmark_accuracy"] is None
    assert (old, after) == inputs
    assert r == compare_opposed_source_reports(old, after, source_bytes=data)


@pytest.mark.parametrize("kwargs", [{"stroke": (0, 0, 0)}, {"fill": (0, 0, 0)},
    {"fill": (.96, 1, .96)}, {"opacity": .5}])
def test_wall_or_ambiguous_paint_cannot_explain_source_claim_loss(kwargs):
    data, old, after = _reports(**kwargs)
    with pytest.raises(ValueError, match="native fill opposition"):
        compare_opposed_source_reports(old, after, source_bytes=data)


@pytest.mark.parametrize("proof", ["host", "host_receipt", "frame"])
def test_any_original_proof_prohibits_removal_even_with_real_opposition(proof):
    data, old, after = _reports()
    if proof == "host": old["opening_bindings"][0]["host_wall_id"] = "real-wall"
    elif proof == "host_receipt": old["opening_bindings"][0]["record_id"] = "real-host-receipt"
    else: old["host_frames"][0]["record_id"] = "real-frame-receipt"
    with pytest.raises(ValueError, match="cannot remove"):
        compare_opposed_source_reports(old, after, source_bytes=data)


@pytest.mark.parametrize("damage", ["sha", "page", "cap", "bool_cap", "duplicate",
    "frame_universe", "identity", "representative", "source_bytes", "missing_representative"])
def test_foreign_or_incomplete_claims_fail_closed(damage):
    data, old, after = _reports()
    if damage == "sha": after["source_sha256"] = "0" * 64
    elif damage == "page": after["selected_geometry_page_ids"] = ["2"]
    elif damage == "cap": after["primitive_safety_cap"] = 20001
    elif damage == "bool_cap": after["primitive_safety_cap"] = True
    elif damage == "duplicate": old["opening_bindings"].append(deepcopy(old["opening_bindings"][0]))
    elif damage == "frame_universe": old["host_frames"] = []
    elif damage == "identity":
        old["opening_bindings"][0]["opening_identity_id"] = "borrowed"
        old["host_frames"][0]["opening_identity_id"] = "borrowed"
    elif damage == "representative": old["opening_bindings"][0]["representative_observation_id"] = "foreign"
    elif damage == "source_bytes": data = b"changed"
    else: del old["opening_bindings"][0]["representative_observation_id"]
    with pytest.raises(ValueError):
        compare_opposed_source_reports(old, after, source_bytes=data)


def test_exact_shared_bindings_and_firm_frame_payloads_stay_protected():
    data, old, _ = _reports()
    old["opening_bindings"][0].update(record_id="host-receipt", host_wall_id="host")
    old["host_frames"][0]["record_id"] = "frame-receipt"
    same = deepcopy(old)
    assert compare_opposed_source_reports(old, same, source_bytes=data)["retention_pass"]
    same["opening_bindings"][0]["reason_codes"] = ["silently changed"]
    with pytest.raises(ValueError, match="binding changed"):
        compare_opposed_source_reports(old, same, source_bytes=data)
    same = deepcopy(old)
    same["host_frames"][0]["record_id"] = "replacement"
    with pytest.raises(ValueError, match="frame changed"):
        compare_opposed_source_reports(old, same, source_bytes=data)


def test_additional_claim_and_malformed_page_universe_cannot_pass():
    data, old, _ = _reports()
    after = deepcopy(old)
    after["opening_bindings"][0]["opening_identity_id"] = "added"
    after["host_frames"][0]["opening_identity_id"] = "added"
    with pytest.raises(ValueError, match="additional"):
        compare_opposed_source_reports(old, after, source_bytes=data)
    for pages in ([], ["1", "1"], [True], ["01"], [["1"]]):
        old["selected_geometry_page_ids"] = pages
        with pytest.raises(ValueError, match="page universe"):
            compare_opposed_source_reports(old, deepcopy(old), source_bytes=data)
