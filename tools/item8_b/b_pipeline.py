"""Study B: read-only structure enumeration and per-structure relation rows. Shadow measurement only.

Uses the same producer, the same six-line rule (`PhysicalOpeningAuthority._visible_structural_candidates`) and the same S2/S2b
audit as the S3 census (tools/item8_s3/s3_census.py). It decides nothing and its outputs are local files."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pb_face_ink_paint_relation_shadow import FaceInkPaintRelationAudit  # noqa: E402
from pb_physical_opening_authority import _line_geometry  # noqa: E402
from pb_source_observation_authority import ObservationSelector  # noqa: E402
from pb_source_visibility_authority import NATIVE_PDF_VISIBLE_SEGMENT, SourceVisibilityProducer  # noqa: E402

from tools.item8_b.b_core import bbox_of_lines  # noqa: E402


@dataclass
class PageStructures:
    pdf_sha256: str
    producer: SourceVisibilityProducer
    published: object
    physical: object
    structures: list          # CandidateSemanticOpening, in candidate-id order
    extents: dict             # candidate_id -> (x0, y0, x1, y1) in the producer's (unrotated page) coordinates
    selector_for: object      # callable(observation_id) -> ObservationSelector
    lines: dict               # candidate_id -> [(x0, y0, x1, y1), ...] member lines, same coordinates as `extents` (display only)


def enumerate_page(label: str, pdf: Path, page_no: int) -> PageStructures:
    raw = pdf.read_bytes()
    sha = sha256(raw).hexdigest()
    producer = SourceVisibilityProducer(producer_method="item8-b-readonly", producer_version="1")
    published = producer.ingest_native_pdf_bytes(
        document_id=f"b:{label}:{sha[:16]}", source_bytes=raw, source_locator="memory://b.pdf", page_ids=(page_no,))
    rows = producer.authority().authenticated_visible_observations(published, bind_page_id=str(page_no))
    native = [(oid, rec) for oid, rec in rows if rec.observation_kind == NATIVE_PDF_VISIBLE_SEGMENT]
    if not native:
        raise RuntimeError("no_native_visible_segments")

    def selector(observation_id):
        return ObservationSelector(published.revision.document_id, published.revision.revision_id,
                                   published.revision.source_sha256, published.snapshot.snapshot_id, observation_id)

    physical = producer.physical_opening_authority()
    source_result = physical._resolve_visible_cached(selector(native[0][0]))
    records, _failures = physical._visible_snapshot_records(source_result)
    by_id = {str(r.observation_id): r for r in records}
    structures = sorted(physical._visible_structural_candidates(source_result.observation, tuple(records)),
                        key=lambda c: c.candidate_id)
    extents = {}
    member_lines = {}
    for structure in structures:
        lines = [g for g in (_line_geometry(by_id[i]) for i in structure.source_observation_ids if i in by_id) if g]
        box = bbox_of_lines(lines)
        if box is not None:
            extents[structure.candidate_id] = box
            member_lines[structure.candidate_id] = lines
    return PageStructures(sha, producer, published, physical, structures, extents, selector, member_lines)


def relation_rows(page: PageStructures, candidate_ids) -> list[dict]:
    """Per-structure rows in the S3 census row schema, for the named structures only. Ids are not written into the rows."""
    audit = FaceInkPaintRelationAudit(page.physical, page.producer, enabled=True)
    wanted = set(candidate_ids)
    out = []
    for structure in page.structures:
        if structure.candidate_id not in wanted:
            continue
        members = tuple(sorted(structure.source_observation_ids))
        sel = page.selector_for(members[0])
        inventory = page.physical.seeded_face_ink_inventory(sel, members)
        entry = next((s for s in inventory.structures if s.candidate_id == structure.candidate_id), None)
        if entry is None:
            out.append(dict(anomaly="structure_not_reproduced_from_its_own_members"))
            continue
        shadow = audit.audit(sel, members, strip_ink_ids=entry.interior_ink_ids)
        row = dict(members=len(members), status=entry.status, shared_support=len(entry.shared_member_ids),
                   face_ink=[], interior=[], shadow_status=shadow.status.value)
        for r in (r for r in shadow.relations if r.structure_id == structure.candidate_id):
            item = dict(order=r.paint_order_among_face_members, d_M=r.nearest_face_member_sequence_distance,
                        d_I=r.nearest_strip_ink_sequence_distance, same_style=bool(r.same_style_as_face_member_ids),
                        fill_edge=bool(r.unstroked_fill_boundary),
                        transparent=bool(r.stroke_is_transparent or r.stroke_is_partially_transparent),
                        available=r.paint_fact_available)
            if r.kind == "face_ink":
                item.update(locality=r.locality, extent_class=r.extent_class)
                row["face_ink"].append(item)
            else:
                row["interior"].append(item)
        out.append(row)
    return out
