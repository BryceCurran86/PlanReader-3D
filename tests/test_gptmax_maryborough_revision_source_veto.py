"""A foreign native-PDF source revision must never resolve another floor's finish.

Source-neutral regression on the REAL live correspondence call path. These
tests prove the veto only; they do not provide D15 threshold, figured metric,
physical finished-face identity or commercial authority, and make no score
claim for Maryborough or 3Laurel.
"""
from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace

import pytest

import pb_source_cross_view_floor_correspondence_shadow as bridge
from pb_migration_contracts import EvidenceResolutionStatus


def _claim(*, floor_source_sha: str, revisions: object):
    room = SimpleNamespace(
        source_room_face_record_id="same-physical-face",
        physical_room_id="physical-office",
        source_dimension_page_id="11",
        room_label="OFFICE",
    )
    floor = SimpleNamespace(
        source_room_face_record_id="same-physical-face",
        room_entity_id="physical-office",
        page_id="7",
        revision_id="requested-revision",
        source_sha256=floor_source_sha,
        document_id="source-document",
        snapshot_id="specific-snapshot",
        canonical_floor_id="verified-floor",
    )
    source = SimpleNamespace(
        _producer=SimpleNamespace(
            _store=SimpleNamespace(source_bytes_by_revision=revisions),
        ),
    )
    return (
        source,
        SimpleNamespace(records=(room,)),
        SimpleNamespace(floors=(floor,)),
    )


@pytest.mark.parametrize("variant", (
    "missing_revision",
    "wrong_owned_payload",
    "nonbyte_payload",
    "empty_store",
    "nonmapping_store",
    "mismatched_declared_sha",
))
def test_missing_or_foreign_revision_never_authenticates_live_office_finish(
    monkeypatch, variant,
):
    original = b"%PDF-1.7 source-neutral revision-A"
    digest = sha256(original).hexdigest()
    revisions = {"requested-revision": original}
    declared_sha = digest
    if variant == "missing_revision":
        revisions = {"foreign-revision": original}
    elif variant == "wrong_owned_payload":
        revisions = {
            "requested-revision": b"%PDF-1.7 different original",
            "foreign-revision": original,
        }
    elif variant == "nonbyte_payload":
        revisions = {"requested-revision": bytearray(original)}
    elif variant == "empty_store":
        revisions = {}
    elif variant == "nonmapping_store":
        revisions = [original]
    elif variant == "mismatched_declared_sha":
        declared_sha = sha256(b"unrelated source").hexdigest()

    called = []
    def unsafe_grant(**kw):
        called.append(kw)
        return SimpleNamespace(
            status=EvidenceResolutionStatus.CORROBORATED,
            commercial_projection_allowed=True,
        )
    monkeypatch.setattr(
        bridge, "authenticate_maryborough_office_cross_sheet_correspondence",
        unsafe_grant,
    )
    source, areas, floors = _claim(
        floor_source_sha=declared_sha, revisions=revisions,
    )
    result = bridge.resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=areas, canonical_floors=floors,
    )
    assert result == ()
    assert not called


def test_exact_owned_bytes_enter_existing_correspondence_resolver_only_once(
    monkeypatch,
):
    original = b"%PDF-1.7 source-neutral matching revision"
    sha = sha256(original).hexdigest()
    revisions = {
        "foreign-revision": b"wrong source cannot be first fallback",
        "requested-revision": original,
    }
    seen = []
    receipt = SimpleNamespace(
        status=EvidenceResolutionStatus.CORROBORATED,
        commercial_projection_allowed=True,
    )

    def source_owned_correspondence(**kwargs):
        seen.append(kwargs)
        return receipt

    monkeypatch.setattr(
        bridge, "authenticate_maryborough_office_cross_sheet_correspondence",
        source_owned_correspondence,
    )
    source, areas, floors = _claim(floor_source_sha=sha, revisions=revisions)
    result = bridge.resolve_cross_sheet_floor_correspondence_for_claim(
        source=source, cross_view_area=areas, canonical_floors=floors,
    )
    assert result == (receipt,)
    assert len(seen) == 1
    assert seen[0]["source_bytes"] == original
    assert seen[0]["revision_id"] == "requested-revision"
    assert seen[0]["source_sha256"] == sha
    assert seen[0]["canonical_floor_id"] == "verified-floor"


def test_source_resolver_withholds_candidate_or_conflicting_receipt(monkeypatch):
    original = b"%PDF-1.7 authentic source neutral"
    sha = sha256(original).hexdigest()
    source, areas, floors = _claim(
        floor_source_sha=sha, revisions={"requested-revision": original},
    )
    for state in (
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
        EvidenceResolutionStatus.CANDIDATE,
    ):
        monkeypatch.setattr(
            bridge, "authenticate_maryborough_office_cross_sheet_correspondence",
            lambda **kwargs: SimpleNamespace(
                status=state, commercial_projection_allowed=True,
            ),
        )
        assert bridge.resolve_cross_sheet_floor_correspondence_for_claim(
            source=source, cross_view_area=areas, canonical_floors=floors,
        ) == ()
