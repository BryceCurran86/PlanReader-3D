"""Three source-proven openings may share both of the middle opening's piers."""
from collections import Counter
from dataclasses import asdict, replace
from unittest.mock import patch

import cv2
import fitz
import numpy as np
import pytest

import pb_opening_host_binding_authority as host
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_door_swing_g17_contract import _png


def _three_opening_pdf(*, rotation=0, scale=1, dx=0, dy=0, unrelated=False):
    image = np.full((440, 1800), 255, np.uint8)
    for lo, hi in ((230, 440), (600, 800), (960, 1160), (1320, 1520)):
        cv2.rectangle(image, (lo + dx, 150 + dy), (hi + dx, 164 + dy), 0, -1)
    for x in (440, 800, 1160):
        cv2.line(image, (x + dx, 164 + dy), (x + dx, 324 + dy), 0, 1)
        cv2.ellipse(image, (x + dx, 164 + dy), (160, 160), 0, 0, 90, 0, 1)
    if unrelated:
        cv2.rectangle(image, (30, 30), (110, 42), 0, -1)
    image = np.ascontiguousarray(np.rot90(image, rotation))
    with fitz.open() as document:
        width, height = (180, 410) if rotation % 2 else (410, 180)
        page = document.new_page(width=width * scale, height=height * scale)
        page.insert_image(page.rect, stream=_png(image), keep_proportion=False)
        return document.tobytes(garbage=4, deflate=True)


def _real_hosts(**pose):
    source = SourceVisibilityProducer(
        producer_method="shared-pier-source-test", producer_version="1",
        raster_paired_outer_faces_shadow=True,
    )
    published = source.ingest_native_pdf_bytes(
        document_id="shared-pier-source-test", source_bytes=_three_opening_pdf(**pose),
        source_locator="memory://shared-pier-source.pdf", page_ids=(1,),
    )
    captured = []
    drop = host.OpeningHostBindingProducer.drop_borrowed_mixed_scope_hosts

    def observe(producer):
        captured.append(producer)
        return drop(producer)

    with patch.object(host.OpeningHostBindingProducer, "drop_borrowed_mixed_scope_hosts", observe):
        composition = compose_live_wall_opening_authority(
            source_visibility_producer=source, revision_id=published.revision.revision_id,
            page_ids=("1",), include_unmeasured_ink_closed_flanks_shadow=True,
            source_fragment_roles_shadow=True,
        )
    producer = captured[0]
    results = dict(producer.published_results())
    assert len(results) == 3
    assert all(result.status is Status.CORROBORATED for result in results.values())
    counts = Counter(member for result in results.values()
                     for member in result.record.member_wall_candidate_ids)
    middle = [key for key, result in results.items()
              if all(counts[member] == 2 for member in result.record.member_wall_candidate_ids)]
    assert len(middle) == 1
    key = middle[0]
    # Isolate the mixed-source exclusivity policy over real issued source,
    # physical and host records. No invented aperture, member, selector or
    # partition verdict is used. The original private test covers the genuine
    # mixed ordinary/supplemental path.
    results[key] = replace(results[key], reason_codes=tuple(dict.fromkeys((
        *results[key].reason_codes, host.OPENING_LOCAL_SUPPLEMENTAL_SOURCE_BAND_HOST_RESOLVED,
    ))))
    return source, composition, producer, results, key


@pytest.fixture(scope="module")
def original_hosts():
    return _real_hosts()


@pytest.fixture
def shared_hosts(original_hosts, monkeypatch):
    source, composition, producer, results, middle = original_hosts
    monkeypatch.setattr(producer, "_results", dict(results))
    return source, composition, producer, results, middle


def test_source_proven_middle_opening_keeps_host_without_bypassing_frame_gate(shared_hosts):
    source, composition, producer, results, middle = shared_hosts
    previous = results[middle]
    # The conservative count-only helper still refuses unauthenticated input.
    assert host._exclusive_mixed_scope_host_results(results)[middle].record is None
    source_before = source.published_snapshot_for_revision(composition.revision_id)
    producer.drop_borrowed_mixed_scope_hosts()
    assert producer.published_results()[middle] == previous
    binding_selector = composition.binding_selectors[middle[-1]]
    binding_authority = producer.authority()
    assert binding_authority.resolve(binding_selector) == previous
    frame = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=producer._opening,
        host_binding_authority=binding_authority,
        physical_wall_candidate_authority=composition.physical_wall_candidate_authority,
        supplemental_wall_candidate_authority=composition.supplemental_physical_wall_candidate_authority,
        source_fragment_roles_shadow=True, raster_split_frame_shadow=True,
    ).publish(opening_selector=producer._opening_selectors[middle], host_binding_selector=binding_selector)
    before = next(trace for trace in composition.host_frames if trace.opening_identity_id == middle[-1])
    assert frame.status is before.status
    assert frame.reason_codes == before.reason_codes
    assert (frame.evidence.record_id if frame.evidence else None) == before.record_id
    assert (frame.evidence.whole_wall_frame_id if frame.evidence else None) == before.whole_wall_frame_id
    # This is source-space frame proof; no metric dimensions or quantity are
    # supplied by a physical partition or by this synthetic drawing.
    from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
    from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source, wall_opening_composition=composition,
    )
    assert publish_live_opening_area_quantities(voids) == ()
    assert source.published_snapshot_for_revision(composition.revision_id) is source_before


def test_default_policy_retains_conservative_shared_member_veto(shared_hosts, monkeypatch):
    _, _, producer, _, middle = shared_hosts
    monkeypatch.setattr(producer, "_source_fragment_roles_shadow", False)
    producer.drop_borrowed_mixed_scope_hosts()
    result = producer.published_results()[middle]
    assert result.record is None
    assert host.OPENING_LOCAL_SUPPLEMENTAL_SHARED_HOST_MEMBER in result.reason_codes


@pytest.mark.parametrize("damage", ["missing", "foreign_sha", "foreign_snapshot", "wrong_opening"])
def test_unavailable_or_foreign_accepted_selector_cannot_save_shared_host(
    shared_hosts, monkeypatch, damage,
):
    _, _, producer, _, middle = shared_hosts
    selectors = dict(producer._opening_selectors)
    selector = selectors[middle]
    if damage == "missing":
        del selectors[middle]
    elif damage == "wrong_opening":
        selectors[middle] = next(value for key, value in selectors.items() if key != middle)
    else:
        field = "source_sha256" if damage == "foreign_sha" else "snapshot_id"
        selectors[middle] = replace(selector, **{field: "f" * 64})
    monkeypatch.setattr(producer, "_opening_selectors", selectors)
    producer.drop_borrowed_mixed_scope_hosts()
    assert producer.published_results()[middle].record is None


@pytest.mark.parametrize("damage", ["unverified", "overlap", "same_record", "foreign_scope", "wrong_peer", "exception"])
def test_every_shared_peer_requires_current_matching_partition_proof(shared_hosts, monkeypatch, damage):
    _, _, producer, _, middle = shared_hosts
    physical = producer._opening
    partition = physical.partition_receipt

    def damaged(left, right):
        if damage == "exception":
            raise RuntimeError("source reproof unavailable")
        receipt = partition(left, right)
        if damage == "overlap":
            return replace(receipt, status=Status.CONFLICT, partition="overlapping_extent")
        if damage == "same_record":
            return replace(receipt, partition="same_record")
        if damage == "foreign_scope":
            return replace(receipt, page_id="foreign")
        if damage == "wrong_peer":
            return replace(receipt, right_record_id="foreign")
        return receipt

    monkeypatch.setattr(physical, "partition_receipt", damaged)
    # Even a caller-shaped agreeing receipt is insufficient if recomputation
    # refuses it. The remaining cases fail before or at matching reproof.
    monkeypatch.setattr(physical, "verify_partition_receipt", lambda *args: damage != "unverified")
    producer.drop_borrowed_mixed_scope_hosts()
    assert producer.published_results()[middle].record is None


def test_one_missing_peer_selector_cannot_be_omitted_from_proof(shared_hosts, monkeypatch):
    _, _, producer, _, middle = shared_hosts
    selectors = dict(producer._opening_selectors)
    del selectors[next(key for key in selectors if key != middle)]
    monkeypatch.setattr(producer, "_opening_selectors", selectors)
    producer.drop_borrowed_mixed_scope_hosts()
    assert producer.published_results()[middle].record is None


def test_repeated_authority_reproves_and_revokes_a_now_unavailable_partition(shared_hosts, monkeypatch):
    _, composition, producer, results, middle = shared_hosts
    assert producer.authority().resolve(composition.binding_selectors[middle[-1]]) == results[middle]
    monkeypatch.setattr(producer._opening, "verify_partition_receipt", lambda *args: False)
    assert producer.authority().resolve(composition.binding_selectors[middle[-1]]).record is None


def test_source_and_input_order_do_not_elect_a_winner(shared_hosts, monkeypatch):
    _, _, producer, results, middle = shared_hosts
    before = {key: asdict(result) for key, result in results.items()}
    monkeypatch.setattr(producer, "_results", dict(reversed(tuple(results.items()))))
    producer.drop_borrowed_mixed_scope_hosts()
    assert producer.published_results()[middle] == results[middle]
    assert {key: asdict(result) for key, result in results.items()} == before


@pytest.mark.parametrize("pose", [{"rotation": 1}, {"scale": 2}, {"dx": 35, "dy": 20}, {"unrelated": True}])
def test_shared_pier_partition_survives_source_transform_and_unrelated_content(pose):
    _, _, producer, results, middle = _real_hosts(**pose)
    producer._results = dict(results)
    producer.drop_borrowed_mixed_scope_hosts()
    assert producer.published_results()[middle] == results[middle]
