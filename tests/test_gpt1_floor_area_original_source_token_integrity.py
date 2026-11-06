"""Original FIRM room area source labels are not display strings.

Negative-only tests at the REAL canonical-floor and canonical-room issuers.
Source-shaped fixtures are synthetic and do not authenticate owner PDFs.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_floor_area_quantity_publication import (
    publish_live_floor_area_quantities,
    publish_live_canonical_room_area_quantities,
)
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with,
    _claim_with_canonical_room,
    _source_area,
)


class PrintedToken:
    """A caller's string-coercible object is never an original source token."""

    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text


@pytest.mark.parametrize(("field", "bad"), [
    ("source_sha256", " " + "a" * 64 + " "),
    ("source_sha256", PrintedToken("a" * 64)),
    ("revision_id", " rev-1 "),
    ("revision_id", PrintedToken("rev-1")),
    ("viewport_id", " vp-1 "),
    ("viewport_id", PrintedToken("vp-1")),
    ("document_id", " doc-1 "),
    ("document_id", PrintedToken("doc-1")),
    ("room_snapshot_id", " snap-1 "),
    ("room_snapshot_id", PrintedToken("snap-1")),
    ("source_room_face_record_id", " face-1 "),
    ("source_room_face_record_id", PrintedToken("face-1")),
])
def test_copied_source_metadata_alias_cannot_reissue_firm_floor_or_room(
    field, bad,
):
    source = _source_area()
    changes = {**dict(source.metadata), field: bad}
    forged = replace(source, metadata=changes)
    claim = _claim_with_canonical_room(forged)
    before = dict(forged.metadata)
    assert publish_live_floor_area_quantities(claim) == ()
    assert publish_live_canonical_room_area_quantities(claim) == ()
    assert forged.metadata == before
    assert len(publish_live_floor_area_quantities(_claim_with(source))) == 1


def test_all_zero_copied_original_digest_never_seals_canonical_area():
    source = _source_area()
    zero = "0" * 64
    copied = replace(source, metadata={**dict(source.metadata), "source_sha256": zero})
    claim = _claim_with_canonical_room(copied)
    claim = replace(
        claim,
        canonical_floors=(
            replace(claim.canonical_floors[0], source_sha256=zero),
        ),
        canonical_rooms=(
            replace(claim.canonical_rooms[0], source_sha256=zero),
        ),
    )
    assert publish_live_floor_area_quantities(claim) == ()
    assert publish_live_canonical_room_area_quantities(claim) == ()


def test_jointly_padded_revision_source_and_floor_are_not_a_source_identity():
    source = _source_area()
    padded = replace(source, metadata={
        **dict(source.metadata), "revision_id": " rev-1 ",
    })
    claim = _claim_with_canonical_room(padded)
    claim = replace(
        claim,
        canonical_floors=(replace(claim.canonical_floors[0], revision_id=" rev-1 "),),
        canonical_rooms=(replace(claim.canonical_rooms[0], revision_id=" rev-1 "),),
    )
    assert publish_live_floor_area_quantities(claim) == ()
    assert publish_live_canonical_room_area_quantities(claim) == ()


def test_original_valid_owned_source_reissue_and_hex_case_fold_are_preserved():
    src = _source_area()
    owned = replace(src, metadata={
        **dict(src.metadata),
        "document_id": "doc-1",
        "room_snapshot_id": "snap-1",
        "source_room_face_record_id": "face-1",
    })
    claim = _claim_with_canonical_room(owned)
    floor_results = publish_live_floor_area_quantities(claim)
    room_results = publish_live_canonical_room_area_quantities(claim)
    assert len(floor_results) == len(room_results) == 1
    assert floor_results[0].value == room_results[0].value == 8.64
    assert floor_results[0].metadata["upstream_room_area_quantity_id"] == src.quantity_id
    assert publish_live_floor_area_quantities(claim) == floor_results
    assert publish_live_canonical_room_area_quantities(claim) == room_results

    upper = replace(owned, metadata={
        **dict(owned.metadata), "source_sha256": "A" * 64,
    })
    upper_claim = _claim_with_canonical_room(upper)
    assert len(publish_live_floor_area_quantities(upper_claim)) == 1
    assert len(publish_live_canonical_room_area_quantities(upper_claim)) == 1


def test_exact_source_identifiers_remain_order_independent_with_provisional_replay():
    original = _source_area()
    provisional = replace(
        original,
        status="provisional",
        abstained=True,
        value=None,
        evidence_ids=("candidate-only",),
        blocking_reasons=("not_firm",),
    )
    expected = publish_live_floor_area_quantities(_claim_with(original))
    assert len(expected) == 1
    for order in ((original, provisional), (provisional, original)):
        assert publish_live_floor_area_quantities(_claim_with(*order)) == expected


def test_optional_empty_room_receipts_and_missing_canonical_room_viewport_stay_compatible():
    source = _source_area()
    optional_absent = replace(source, metadata={
        **dict(source.metadata),
        "room_snapshot_id": "",
        "source_room_face_record_id": "",
    })
    claim = _claim_with_canonical_room(optional_absent)
    claim = replace(
        claim,
        canonical_rooms=(replace(claim.canonical_rooms[0], viewport_id=None),),
    )
    assert len(publish_live_floor_area_quantities(claim)) == 1
    assert len(publish_live_canonical_room_area_quantities(claim)) == 1


class EmptyEqualityAlias:
    """An untrusted object can masquerade as the historical empty sentinel."""

    def __eq__(self, other):
        return other is None or other == ""

    def __str__(self):
        return ""

    def __repr__(self):
        return "EmptyEqualityAlias()"


@pytest.mark.parametrize("field", (
    "room_snapshot_id", "source_room_face_record_id",
))
@pytest.mark.parametrize("alias", (
    EmptyEqualityAlias(), False, 0,
))
def test_optional_source_receipt_equality_alias_cannot_be_absent(field, alias):
    """An object's __eq__ must not bypass original source ownership."""
    source = _source_area()
    forged = replace(source, metadata={
        **dict(source.metadata), field: alias,
    })
    claim = _claim_with_canonical_room(forged)
    assert publish_live_floor_area_quantities(claim) == ()
    assert publish_live_canonical_room_area_quantities(claim) == ()
    assert len(publish_live_floor_area_quantities(_claim_with(source))) == 1


@pytest.mark.parametrize("sentinel", (None, ""))
def test_native_optional_source_receipt_sentinels_preserve_legacy_floor(sentinel):
    source = _source_area()
    optional_absent = replace(source, metadata={
        **dict(source.metadata),
        "room_snapshot_id": sentinel,
        "source_room_face_record_id": sentinel,
    })
    claim = _claim_with_canonical_room(optional_absent)
    assert len(publish_live_floor_area_quantities(claim)) == 1
    assert len(publish_live_canonical_room_area_quantities(claim)) == 1
