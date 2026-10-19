"""Positive, conflict and metamorphic checks for source-only opening parents."""
from types import SimpleNamespace as NS
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer, SourceVisibilityAuthority
from pb_gpt2_raster_opening_parent_source_shadow import (
    recover_original_raster_opening_parent_lines_shadow,
)

_SHA = "1" * 64


def _visible(parent, observation, **changes):
    values = dict(
        document_id="doc", revision_id="rev", source_sha256=_SHA,
        snapshot_id="snap", page_id="3", viewport_id=None,
        observation_kind="raster_wall_band_end",
        origin_kind="producer_raster_opening_primitive_visibility",
        source_primitive_ref=(
            "visible:raster_opening_primitive:sha:2.0.0:raster_wall_band_end:1"
        ),
        derivation_parent_ids=(parent,), raw_text="",
        geometry=(100., 200., 130., 200.), observation_id=observation,
    )
    values.update(changes)
    return NS(**values)


def _source(monkeypatch, records):
    src = object.__new__(SourceVisibilityProducer)
    # Mirror the ACTUAL source architecture: producer publishes, authority
    # facade resolves. Never monkeypatch nonexistent Producer reader methods.
    authority = object.__new__(SourceVisibilityAuthority)
    monkeypatch.setattr(SourceVisibilityProducer, "authority", lambda self: authority)
    published = NS(
        revision=NS(document_id="doc", revision_id="rev", source_sha256=_SHA),
        snapshot=NS(snapshot_id="snap"),
    )
    monkeypatch.setattr(
        SourceVisibilityProducer, "published_snapshot_for_revision",
        lambda self, revision: published,
    )
    monkeypatch.setattr(
        SourceVisibilityAuthority,
        "raster_opening_primitive_observation_ids_for_snapshot",
        lambda self, snapshot: frozenset(records),
    )
    monkeypatch.setattr(
        SourceVisibilityAuthority, "resolve_raster_opening_primitive",
        lambda self, selector: NS(
            status=EvidenceResolutionStatus.CORROBORATED,
            observation=records[selector.observation_id],
        ),
    )
    return src


def _run(source, parents=("parent-A",)):
    return recover_original_raster_opening_parent_lines_shadow(
        source, revision_id="rev", snapshot_id="snap", page_id="3",
        required_parent_ids=parents,
    )


def test_two_source_owned_parents_order_invariant_and_no_host_or_quantity(monkeypatch):
    records = {"vB": _visible("parent-B", "vB"), "vA": _visible("parent-A", "vA")}
    source = _source(monkeypatch, records)
    a, b = _run(source, ("parent-B", "parent-A")), _run(source, ("parent-A", "parent-B"))
    assert a == b and a.status == "SOURCE_ONLY_CANDIDATE"
    assert tuple(x.parent_observation_id for x in a.lines) == ("parent-A", "parent-B")
    assert not a.unresolved_parent_ids
    assert a.shadow_only and not a.structural_host_granted
    assert not a.whole_wall_frame_granted and not a.metric_quantity_granted
    assert all(not x.host_binding_granted and not x.w4_wall_identity_granted for x in a.lines)
    assert records["vA"].geometry == (100., 200., 130., 200.)


def test_missing_parent_preserves_positive_and_abstains_missing(monkeypatch):
    source = _source(monkeypatch, {"v": _visible("parent-A", "v")})
    output = _run(source, ("parent-A", "parent-B"))
    assert output.status == "PARTIAL_ABSTAIN"
    assert len(output.lines) == 1 and output.unresolved_parent_ids == ("parent-B",)


def test_multiple_visible_claimants_same_parent_conflict(monkeypatch):
    source = _source(monkeypatch, {
        "v1": _visible("parent-A", "v1"),
        "v2": _visible("parent-A", "v2"),
    })
    output = _run(source)
    assert output.lines == () and output.unresolved_parent_ids == ("parent-A",)


@pytest.mark.parametrize("change", [
    {"page_id": "7"}, {"source_sha256": "2" * 64},
    {"origin_kind": "producer_raster_visibility"},
    {"observation_kind": "raster_pdf_visible_segment"},
    {"source_primitive_ref": "visible:raster_segment:impostor"},
    {"viewport_id": "foreign"}, {"raw_text": "1000"},
    {"geometry": (100., 200., 100., 200.)},
    {"geometry": (float("nan"), 200., 130., 200.)},
    {"derivation_parent_ids": ("different",)},
])
def test_foreign_source_kind_or_invalid_geometry_stays_abstained(monkeypatch, change):
    source = _source(monkeypatch, {"v": _visible("parent-A", "v", **change)})
    output = _run(source)
    assert not output.lines and output.unresolved_parent_ids == ("parent-A",)


def test_not_rekeying_unsupported_parent_as_existing_line(monkeypatch):
    source = _source(monkeypatch, {"v": _visible("parent-A", "v")})
    assert _run(source, ("foreign-parent",)).lines == ()


def test_duplicate_input_parent_is_not_laundered(monkeypatch):
    source = _source(monkeypatch, {"v": _visible("parent-A", "v")})
    with pytest.raises(ValueError):
        _run(source, ("parent-A", "parent-A"))


def test_stale_snapshot_fails_closed(monkeypatch):
    source = _source(monkeypatch, {})
    with pytest.raises(ValueError):
        recover_original_raster_opening_parent_lines_shadow(
            source, revision_id="rev", snapshot_id="other",
            page_id="3", required_parent_ids=("parent-A",),
        )

def test_selected_visible_observation_identity_must_match_producer_receipt(monkeypatch):
    source = _source(monkeypatch, {
        "v": _visible("parent-A", "foreign-visible-id"),
    })
    result = _run(source)
    assert result.lines == ()
    assert result.unresolved_parent_ids == ("parent-A",)

def test_conflicted_source_inventory_never_certifies_remaining_parent(monkeypatch):
    rows = {
        "valid": _visible("parent-A", "valid"),
        "unverified": _visible("other-parent", "unverified"),
    }
    source = _source(monkeypatch, rows)
    def resolving(self, selector):
        if selector.observation_id == "unverified":
            return NS(status=EvidenceResolutionStatus.CONFLICT, observation=None)
        return NS(status=EvidenceResolutionStatus.CORROBORATED,
                  observation=rows[selector.observation_id])
    monkeypatch.setattr(SourceVisibilityAuthority, "resolve_raster_opening_primitive",
                        resolving)
    result = _run(source)
    assert result.status == "PARTIAL_ABSTAIN"
    assert result.lines == ()
    assert result.unresolved_parent_ids == ("parent-A",)
    assert result.reason_codes == ("original_raster_opening_source_inventory_conflict",)
