"""Original Maryborough WC/shower D09 source-authenticated painted head wall.

The A500 elevation's source-painted D09 wall ABOVE the door is independently
authenticated from original visible PDF segment receipts; NOT from the 300mm
KICKPLATE annotation on the separate A600 door elevation. Evidence attaches
to D09 only. The other two doors require their own physical/typical witness.
No actual ceiling area or benchmark quantity is issued.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

from pb_migration_contracts import stable_contract_id
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_maryborough_wc_door_ceiling_gap import (
    authenticate_original_maryborough_wc_door_ceiling_gaps,
)

_D09_PATH = 17143
_EDGE_RE = re.compile(r"visible:segment:d17143i0e([0123])$")


@dataclass(frozen=True)
class OriginalWcD09DoorHeaderEvidence:
    record_id: str
    source_sha256: str
    revision_id: str
    snapshot_id: str
    source_elevation_page_id: str
    door_tag: str
    door_schedule_gap_record_id: str
    elevation_door_word_id: str
    elevation_ceiling_height_word_id: str
    visible_black_header_observation_ids: tuple[str, ...]
    visible_black_header_bbox_pdf_pts: tuple[float, float, float, float]
    door_leaf_height_mm: int
    rcp_ceiling_height_mm: int
    status: str = "AUTHENTIC_SOURCE_D09_WALL_HEAD_PAINTED_ON_ELEVATION"
    other_wc_headers_authenticated: bool = False
    complete_physical_ceiling_zone_authenticated: bool = False
    customer_quantity_allowed: bool = False
    benchmark_credit: bool = False


@dataclass(frozen=True)
class OriginalWcD09DoorHeaderResult:
    status: str
    reason_codes: tuple[str, ...]
    record: OriginalWcD09DoorHeaderEvidence | None = None
    customer_quantity_allowed: bool = False
    benchmark_credit: bool = False


def authenticate_original_maryborough_d09_painted_header(
    *, source: SourceVisibilityProducer, revision_id: str,
) -> OriginalWcD09DoorHeaderResult:
    def blocked(reason: str) -> OriginalWcD09DoorHeaderResult:
        return OriginalWcD09DoorHeaderResult("ABSTAIN",(reason,))
    if type(source) is not SourceVisibilityProducer or type(revision_id) is not str:
        return blocked("original_wc_d09_header_selector_invalid")
    gaps=authenticate_original_maryborough_wc_door_ceiling_gaps(
        source=source,revision_id=revision_id,
    )
    if gaps.status!="SOURCE_SCHEDULED_DOOR_HEIGHT_BELOW_RCP_HEADER_UNPROVEN" or len(gaps.records)!=3:
        return blocked("original_wc_d09_door_schedule_and_rcp_unavailable")
    g=[r for r in gaps.records if r.door_tag=="D09"]
    if len(g)!=1:return blocked("original_wc_d09_door_tag_identity_not_unique")
    door=g[0]
    published=source.published_snapshot_for_revision(revision_id)
    if (
        published is None or published.revision.revision_id!=revision_id
        or published.revision.source_sha256!=door.source_sha256
        or published.snapshot.snapshot_id!=door.snapshot_id
        or "24" not in set(map(str,published.coverage.decoded_pages))
    ):
        return blocked("original_wc_d09_elevation_revision_unavailable")
    try:
        from pb_source_material_semantic_authority import _trusted_words_by_page
        words=tuple(_trusted_words_by_page(source,published).get("24",()))
    except (TypeError,RuntimeError,ValueError):
        return blocked("original_wc_d09_elevation_text_trust_unavailable")
    labels=[
        w for w in words
        if w.trusted and w.text.strip().upper()=="D09"
        and 810<w.bbox[0]<840 and 1330<w.bbox[1]<1400
    ]
    heights=[
        w for w in words
        if w.trusted and w.text.strip()=="2400"
        and 790<w.bbox[0]<830 and 1380<w.bbox[1]<1430
    ]
    if len(labels)!=1 or len(heights)!=1:
        return blocked("original_wc_d09_elevation_label_or_height_not_unique")
    try:
        visible=source.authority().authenticated_visible_observations(
            published,bind_page_id="24",
        )
    except (RuntimeError,ValueError,TypeError):
        return blocked("original_wc_d09_painted_header_visibility_unavailable")
    candidates={}
    for observation_id,observation in visible:
        match=_EDGE_RE.fullmatch(str(getattr(observation,"source_primitive_ref","")))
        if match is not None:
            edge=int(match.group(1))
            if edge in candidates:
                return blocked("original_wc_d09_duplicate_header_edge_receipt")
            candidates[edge]=observation_id
    if set(candidates)!={0,1,2,3}:
        return blocked("original_wc_d09_visible_four_edge_painted_header_unavailable")
    ids=tuple(candidates[edge] for edge in range(4))
    selector=ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=revision_id,source_sha256=door.source_sha256,
        snapshot_id=door.snapshot_id,observation_id=ids[0],
    )
    try:
        paint=source.native_paint_facts(selector,observation_ids=ids)
    except (RuntimeError,ValueError,TypeError):
        return blocked("original_wc_d09_header_native_paint_integrity_unavailable")
    if len(paint)!=4 or {f.edge_index for f in paint}!={0,1,2,3}:
        return blocked("original_wc_d09_header_painted_rectangle_incomplete")
    for p in paint:
        if (
            p.path_index!=_D09_PATH or p.kind!="rect_edge"
            or p.paint_type!="f" or p.stroke_color is not None
            or p.fill!=(0.0,0.0,0.0) or p.fill_opacity!=1.0
            or not p.clip_known
        ):
            return blocked("original_wc_d09_elevation_header_not_black_visible_wall")
    points=tuple(v for row in paint for v in (
        (row.geometry[0],row.geometry[1]),
        (row.geometry[2],row.geometry[3]),
    ))
    if any(not math.isfinite(v) for point in points for v in point):
        return blocked("original_wc_d09_header_geometry_not_finite")
    xs,ys=zip(*points)
    bbox=(min(xs),min(ys),max(xs),max(ys))
    if bbox[2]<=bbox[0] or bbox[3]<=bbox[1]:
        return blocked("original_wc_d09_header_geometry_degenerate")
    # The D09 elevation label, the 2400 level and the painted upper wall
    # must be in one original-source drawing band. This prevents using the
    # black header of some other inset/elevation to heal an invented wall.
    label=labels[0];height=heights[0]
    if not (
        abs(label.bbox[1]-bbox[1])<20
        and abs(height.bbox[1]-bbox[3])<60
        and 0<label.bbox[0]-bbox[2]<160
        and door.door_leaf_height_mm==2040
        and door.ceiling_height_mm==2400
    ):
        return blocked("original_wc_d09_header_elevation_identity_conflict")
    payload=dict(
        source_sha256=door.source_sha256,revision_id=revision_id,
        snapshot_id=door.snapshot_id,source_elevation_page_id="24",
        door_tag=door.door_tag,
        door_schedule_gap_record_id=door.record_id,
        elevation_door_word_id=label.observation_id,
        elevation_ceiling_height_word_id=height.observation_id,
        visible_black_header_observation_ids=tuple(sorted(ids)),
        visible_black_header_bbox_pdf_pts=bbox,
        door_leaf_height_mm=door.door_leaf_height_mm,
        rcp_ceiling_height_mm=door.ceiling_height_mm,
    )
    return OriginalWcD09DoorHeaderResult(
        status="ORIGINAL_D09_ELEVATION_PAINTED_HEADER_AUTHENTIC",
        reason_codes=("d09_original_visible_black_wall_above_scheduled_door",),
        record=OriginalWcD09DoorHeaderEvidence(
            record_id=stable_contract_id("original_mary_d09_elevation_header",payload,digest_chars=32),
            **payload,
        ),
    )
