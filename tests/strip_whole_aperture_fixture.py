"""Synthetic records for the callout strip -> whole-aperture correspondence tests (nothing is read from any project file)."""
from __future__ import annotations

from dataclasses import replace

import pb_callout_strip_whole_aperture_correspondence_shadow as shadow
from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_whole_opening_aperture_authority import (
    GLAZING_SUBDIVISION_DISCRIMINATED,
    HOST_WALL_CONTINUITY_PROVEN,
    INTERNAL_GLAZING_SUBDIVISION_GAP,
    STRUCTURAL_JAMB_HEAVY,
    STRUCTURAL_TERMINAL_JAMB_PROVEN,
    WHOLE_OPENING_APERTURE_CORROBORATED,
    GlazingSubdivisionDiscriminationRecord,
    WholeOpeningApertureRecord,
)

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT
CORR = EvidenceResolutionStatus.CORROBORATED

OWN = shadow.ApertureOwnership("doc-1", "rev-1", "snap-1", "a" * 64, "7")
Q = 0.24
PROVEN = (WHOLE_OPENING_APERTURE_CORROBORATED, STRUCTURAL_TERMINAL_JAMB_PROVEN, HOST_WALL_CONTINUITY_PROVEN)
INK = ("g1", "g2", "t1")


def record(span, band=(200.0, 200.72), *, axis="H", rid=None, status=CAND, reasons=PROVEN, role=STRUCTURAL_JAMB_HEAVY,
           lo=("jamb-lo",), hi=("jamb-hi",), host=("wall-a", "wall-b"), glazing=(), subs=(), own=OWN):
    return WholeOpeningApertureRecord(
        record_id=rid or f"ap-{axis}-{span[0]}-{span[1]}", document_id=own.document_id, revision_id=own.revision_id,
        source_sha256=own.source_sha256, snapshot_id=own.snapshot_id, page_id=own.page_id, viewport_id=None, axis=axis,
        aperture_span_along=tuple(span), wall_band_across=tuple(band), terminal_jamb_lo_ids=tuple(lo),
        terminal_jamb_hi_ids=tuple(hi), host_face_ids=tuple(host), glazing_strip_ids=tuple(glazing),
        discriminated_subdivision_ids=tuple(subs), status=status, structural_role=role, reason_codes=tuple(reasons))


def sub(span, *, sid=None, axis="H", internal=True, status=CORR, own=OWN, band=(200.0, 200.72)):
    return GlazingSubdivisionDiscriminationRecord(
        record_id=sid or f"sub-{axis}-{span[0]}-{span[1]}", document_id=own.document_id, revision_id=own.revision_id,
        source_sha256=own.source_sha256, snapshot_id=own.snapshot_id, page_id=own.page_id, viewport_id=None, axis=axis,
        is_internal_subdivision=internal, subdivision_span_along=tuple(span),
        subdivision_depth_across=band[1] - band[0], member_observation_ids=("post-a", "post-b"), status=status,
        reason_codes=(INTERNAL_GLAZING_SUBDIVISION_GAP, GLAZING_SUBDIVISION_DISCRIMINATED))


def nomination(frame=(100.0, 304.0), band=(197.0, 203.0), *, axis="H", ink=INK, strip_id="strip-1",
               claims=None, extent_complete=True, viewport="vp-1"):
    claims = (shadow.CalloutClaim("W1", "tag-1", "corr-1"),) if claims is None else claims
    return shadow.StripNomination(strip_id, axis, tuple(band), tuple(frame), extent_complete, tuple(ink), viewport,
                                  tuple(claims))


def inventory(ink=INK, *, extra=(), complete=True, boxes=(), unadmitted=(), admitted_ink=(), reasons=()):
    """`boxes` are stroked unadmitted ink of unreadable paint order (they always block); `unadmitted` and
    `admitted_ink` are InkItem records with a paint order."""
    items = tuple(shadow.InkItem(tuple(b), None, True) for b in boxes) + tuple(unadmitted)
    return shadow.StrokeInventory(complete, frozenset(tuple(ink) + tuple(extra)), tuple(admitted_ink), items,
                                  (("stroked", len(tuple(ink)) + len(tuple(extra))),), tuple(reasons))


def evaluate(nominations, records, subs=(), inv=None, *, own=OWN, quantum=Q, **kw):
    nominations = [nominations] if isinstance(nominations, shadow.StripNomination) else list(nominations)
    return shadow.evaluate_whole_aperture_correspondence(
        own, nominations, list(records), list(subs), inv or inventory(), coordinate_quantum_pt=quantum, **kw)


def one(nominations, records, subs=(), inv=None, **kw):
    out = evaluate(nominations, records, subs, inv, **kw)
    assert len(out.correspondences) == 1
    return out.correspondences[0]


def clean_window():
    """A three-panel window: one whole-extent record, two discriminated posts, and the three runs the posts cut."""
    posts = [sub((160.0, 162.0)), sub((230.0, 232.0))]
    whole = record((100.0, 304.0), subs=[p.record_id for p in posts])
    return whole, posts


def signature(out):
    return tuple(
        (c.strip_id, c.status, c.reason_codes, len(c.equal_record_ids), len(c.unvetoed_rival_record_ids),
         len(c.vetoed_rival_record_ids), c.linkage_basis,
         tuple((r.relation, r.authority_status, bool(r.vetoed_by_subdivision_ids)) for r in c.relations))
        for c in sorted(out.correspondences, key=lambda c: c.strip_id))


# ---- coordinate transforms of a whole scenario (records carry along/across, boxes carry page x/y) ----------------
def _map_pair(pair, scale, shift):
    return (pair[0] * scale + shift, pair[1] * scale + shift)


def transform(scenario, *, scale=1.0, along=0.0, across=0.0, swap_axes=False):
    noms, records, subs, inv = scenario
    flip = {"H": "V", "V": "H"}
    source_axis = noms[0].axis

    def axis(a):
        return flip[a] if swap_axes else a

    def box(b):
        a, c = ((b[0], b[2]), (b[1], b[3])) if source_axis == "H" else ((b[1], b[3]), (b[0], b[2]))
        a, c = _map_pair(a, scale, along), _map_pair(c, scale, across)
        return (a[0], c[0], a[1], c[1]) if axis(source_axis) == "H" else (c[0], a[0], c[1], a[1])

    new_noms = [replace(n, axis=axis(n.axis), band=_map_pair(n.band, scale, across),
                        frame_along=_map_pair(n.frame_along, scale, along)) for n in noms]
    new_records = [replace(r, axis=axis(r.axis), aperture_span_along=_map_pair(r.aperture_span_along, scale, along),
                           wall_band_across=_map_pair(r.wall_band_across, scale, across)) for r in records]
    new_subs = [replace(s, axis=axis(s.axis), subdivision_span_along=_map_pair(s.subdivision_span_along, scale, along))
                for s in subs]
    new_inv = replace(inv, unadmitted_ink=tuple(replace(i, box=box(i.box)) for i in inv.unadmitted_ink),
                      admitted_ink=tuple(replace(i, box=box(i.box)) for i in inv.admitted_ink))
    return new_noms, new_records, new_subs, new_inv
