"""Source-addressed F.07 drawing extent; no room, metric or finish authority.

Sheet metadata supplies a role only after independent source geometry proves
one bounded drawing component. Native frames and raster physical supports are
different extent proofs. Neither image placement nor a sheet crop is a view.
This opt-in reader never augments the source snapshot or changes live F.07.
"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import fitz

import pb_viewport_segmentation as f07
from pb_drawing_evidence_binding import DrawingViewClassifier, DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_native_dimension_cap_evidence import compile_native_dimension_cap_components
from pb_native_page_frame import NativePageFrameUnresolved
from pb_raster_text_corroboration_authority import (
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_room_label_authority import _normalized_room_line
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)
from pb_vector_geometry_v130 import extract_native_page

_PLAN_ROLES = {
    DrawingViewType.FLOOR_PLAN.value,
    DrawingViewType.FLOOR_FINISH_PLAN.value,
}
_MAX_ALTERNATIVES = 20000


def _envelope(boxes):
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _line_box(line):
    return (
        min(line[0], line[2]),
        min(line[1], line[3]),
        max(line[0], line[2]),
        max(line[1], line[3]),
    )


def _connected_families(rows, related):
    """Retain every member, with no ranked frame/plane election."""
    families = []
    for row in rows:
        matched = [
            i
            for i, family in enumerate(families)
            if any(related(row, member) for member in family)
        ]
        merged = [row]
        for i in reversed(matched):
            merged.extend(families.pop(i))
        families.append(merged)
    return families


def _boxes_touch(a, b):
    x = min(a[2], b[2]) - max(a[0], b[0])
    y = min(a[3], b[3]) - max(a[1], b[1])
    return x >= 0 and y >= 0 and (x > 0 or y > 0)


def _trusted_line_labels(page, words, *, require_trusted=True):
    """Whole native room lines, backed by every original word receipt."""
    labels = []
    by_line = {}
    for word in words:
        by_line.setdefault((word.block_no, word.line_no), []).append(word)
    for (bi, li), rows in sorted(by_line.items()):
        rows = sorted(rows, key=lambda w: w.word_no)
        text = " ".join(w.text for w in rows)
        if (
            not require_trusted or all(w.trusted for w in rows)
        ) and _normalized_room_line(text):
            labels.append(
                (
                    _envelope([w.bbox for w in rows]),
                    tuple(sorted(w.observation_id for w in rows)),
                    text,
                )
            )
    return tuple(labels)


def _sheet_role(page, words, anchors, *, require_trusted=True):
    analysis = f07._title_authority.analyse_cells(
        f07._title_authority.page_cells(page),
        page.rect.width,
        page.rect.height,
        0,
        "native",
    )
    # An explicit *different* drawing role is a conflict, not an omitted rival.
    roles = [
        c
        for c in analysis.candidates
        if c.kind == "label" and c.label_strength == "title_explicit" and not c.rejected
    ]
    if len(roles) != 1 or any(a.view_type in f07._PLAN_VIEW_TYPES for a in anchors):
        return None
    role = roles[0]
    kind = DrawingViewClassifier.classify_text(role.text).value
    if kind not in _PLAN_ROLES or not f07._TITLE_SHAPE_RE.fullmatch(role.text):
        return None
    title = f07._to_native_bbox(
        page,
        (
            role.box[0] * page.rect.width,
            role.box[1] * page.rect.height,
            role.box[2] * page.rect.width,
            role.box[3] * page.rect.height,
        ),
    )
    if title is None:
        return None
    # MuPDF quarter-turn matrices round native coordinates to float32. This
    # match-only slack never expands the word's producer-owned OCR target.
    owned = [w for w in words if f07._bbox_contains(title, w.bbox, margin=1e-3)]
    if not owned or (require_trusted and not all(w.trusted for w in owned)):
        return None
    # Exact source words must cover the independently bound field value.
    normalize = lambda t: " ".join(str(t).upper().split()).split()
    from collections import Counter

    if Counter(token for w in owned for token in normalize(w.text)) != Counter(
        normalize(role.text)
    ):
        return None
    # Prove the field label as well as its value. A hidden/forged field label
    # cannot turn otherwise visible native text into an explicit sheet role.
    field_cells = [
        c
        for c in f07._title_authority.page_cells(page)
        if (parsed := f07._title_authority.parse_label(c)) is not None
        and parsed.strength == "title_explicit"
        and role.reason.startswith(f"value of '{c.text}' (")
    ]
    if len(field_cells) != 1:
        return None
    cell = field_cells[0]
    field_box = f07._to_native_bbox(page, (cell.x0, cell.y0, cell.x1, cell.y1))
    field_words = (
        [w for w in words if f07._bbox_contains(field_box, w.bbox, margin=1e-3)]
        if field_box
        else []
    )
    if (
        not field_words
        or (require_trusted and not all(w.trusted for w in field_words))
        or Counter(token for w in field_words for token in normalize(w.text))
        != Counter(normalize(cell.text))
    ):
        return None
    return (
        role.text,
        kind,
        title,
        tuple(sorted({w.observation_id for w in (*owned, *field_words)})),
    )


def _dimension_words(page, words):
    directions = {
        (bi, li): tuple(line.get("dir", (0.0, 0.0)))
        for bi, block in enumerate(
            page.get_text("dict", flags=fitz.TEXTFLAGS_WORDS)["blocks"]
        )
        for li, line in enumerate(block.get("lines", []))
    }
    return [
        {
            "id": w.observation_id,
            "text": w.text,
            "bbox": w.bbox,
            "axis": directions.get((w.block_no, w.line_no), (0.0, 0.0)),
        }
        for w in words
    ]


def _source_stroked_segments(page, rows, page_id):
    native = {s["id"]: s for s in extract_native_page(page).get("segments", ())}
    drawings = f07._page_drawings(page)
    segments = {}
    for oid, record in rows:
        if (
            record.page_id != page_id
            or record.observation_kind != NATIVE_PDF_VISIBLE_SEGMENT
        ):
            continue
        raw = native.get(record.source_primitive_ref.removeprefix("visible:segment:"))
        if raw is None or tuple(record.geometry) != tuple(
            raw[k] for k in ("x1", "y1", "x2", "y2")
        ):
            raise RuntimeError("source_plan_view_native_paint_lineage_changed")
        paint = drawings[raw["path_index"]]
        # Fill boundaries, transparent strokes and white masks are not
        # dimension ink. Visibility of a source path alone is insufficient.
        if (
            raw.get("stroke_present") is True
            and raw.get("width_present") is True
            and float(raw["width"]) > 0
            and "s" in str(paint.get("type", ""))
            and paint.get("stroke_opacity") == 1.0
            and any(float(c) < 1.0 for c in raw["stroke"])
        ):
            segments[oid] = tuple(record.geometry)
    return segments


def _corroborate_source_words(
    source, published, words, selected_ids, *, proof_audit=None
):
    """Nomination never trusts text; exact two-render source proof does.

    Clip-only recovery is isolated to this opt-in view proof. Existing native
    text receipts, commercial consumers and default corroboration are unchanged.
    No caller pixels, word text, OCR backend, crop or confidence threshold.
    """
    raster = RasterTextCorroborationProducer.for_physical_plan_view_shadow(source)
    recovered = []
    for w in words:
        if w.observation_id in selected_ids and not w.trusted:
            result = raster.publish(
                RasterTextCorroborationSelector(
                    published.revision.document_id,
                    published.revision.revision_id,
                    published.revision.source_sha256,
                    published.snapshot.snapshot_id,
                    w.observation_id,
                )
            )
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.record is not None
                and result.corroborated_text == w.text
            ):
                w = replace(
                    w,
                    trusted=True,
                    reason_codes=(*w.reason_codes, "raster_text_corroborated"),
                )
                if proof_audit is not None:
                    from dataclasses import asdict

                    proof_audit.append(
                        {
                            "source_observation_id": w.observation_id,
                            "raster_text_record": asdict(result.record),
                            "source_glyph_reading_cover_proofs": raster.glyph_reading_cover_proofs(
                                RasterTextCorroborationSelector(
                                    published.revision.document_id,
                                    published.revision.revision_id,
                                    published.revision.source_sha256,
                                    published.snapshot.snapshot_id,
                                    w.observation_id,
                                )
                            ),
                        }
                    )
        recovered.append(w)
    return tuple(recovered)


def _source_dimension_facts(components, segments, excluded):
    """Strict native cap/tick facts, not bare numbers or measured spans.

    Reuse the existing source compiler's exact collinear components, same-side
    witnesses, opposite tick halves and trusted directed numeric word. It
    supplies geometry only; annotation opposition remains candidate evidence.
    """
    facts = {}
    for axes, word_id, support in components:
        if not set(support) <= segments.keys():
            continue
        lines = [segments[i] for i in axes]
        horizontal = all(
            abs(l[1] - l[3]) <= 1e-6 and abs(l[0] - l[2]) > 1e-6 for l in lines
        )
        vertical = all(
            abs(l[0] - l[2]) <= 1e-6 and abs(l[1] - l[3]) > 1e-6 for l in lines
        )
        if horizontal == vertical:
            continue
        box = _envelope([_line_box(segments[i]) for i in support])
        if any(_boxes_touch(box, b) for b in excluded):
            continue
        axis_box = _envelope([_line_box(l) for l in lines])
        key = ("horizontal" if horizontal else "vertical", axis_box)
        # Repeated words/caps on the same exact contiguous source axis do
        # not create new planes. Keep ALL their source alternatives together;
        # this is geometry equivalence, never a strongest-word election.
        entry = facts.setdefault(key, ([], set(), set()))
        entry[0].append(box)
        entry[1].update(support)
        entry[2].add(word_id)
    return tuple(
        sorted(
            (axis, axis_box, _envelope(boxes), tuple(sorted(ids)), tuple(sorted(words)))
            for (axis, axis_box), (boxes, ids, words) in facts.items()
        )
    )


def _native_frame_extent(frames, labels, facts):
    families = _connected_families(sorted(frames), _boxes_touch)
    # Incomplete second room-bearing frames remain competitors.
    plausible = []
    for family in families:
        inside = [r for r in labels if any(f07._bbox_contains(b, r[0]) for b in family)]
        if len(inside) >= 2:
            plausible.append((family, inside))
    if len(plausible) != 1:
        return None
    family, inside = plausible[0]
    box = _envelope(family)
    supporting = [r for r in facts if f07._bbox_contains(box, r[2])]
    if {r[0] for r in supporting} != {"horizontal", "vertical"}:
        return None
    return (
        box,
        inside,
        supporting,
        {
            "extent_method": "native_frame_family",
            "source_frame_bboxes": tuple(sorted(family)),
        },
    )


def _raster_plane_extent(labels, facts, physical):
    """All orthogonal source plane projections; no overall/longest selection.

    Native dimension components supply two coordinate intervals. A projected
    plane must contain room structure and producer-proved physical raster
    supports. Components connect only through shared source labels/supports;
    bbox overlap alone cannot join unrelated drawings. Partial competitors
    are retained. This is a bounded component, not whole-page completeness.
    """
    horizontal = [r for r in facts if r[0] == "horizontal"]
    vertical = [r for r in facts if r[0] == "vertical"]
    if len(horizontal) * len(vertical) > _MAX_ALTERNATIVES:
        return None
    planes = []
    for h in horizontal:
        for v in vertical:
            box = (h[1][0], v[1][1], h[1][2], v[1][3])
            room_ids = frozenset(
                i for i, r in enumerate(labels) if f07._bbox_contains(box, r[0])
            )
            if len(room_ids) < 2:
                continue
            physical_ids = frozenset(
                i
                for i, r in enumerate(physical)
                if f07._bbox_contains(box, r["support_bbox_pdf_pts"])
            )
            planes.append((box, room_ids, physical_ids, h, v))
    families = _connected_families(
        planes, lambda a, b: bool(a[1] & b[1] or a[2] & b[2])
    )
    # No selection among plausible second planes, even if one lacks G17 proof.
    if len(families) != 1:
        return None
    family = families[0]
    physical_ids = set().union(*(r[2] for r in family))
    if len(physical_ids) < 2:
        return None
    room_ids = set().union(*(r[1] for r in family))
    supporting = sorted({r[i] for r in family for i in (3, 4)})
    boxes = [r[0] for r in family] + [r[2] for r in supporting]
    boxes += [physical[i]["support_bbox_pdf_pts"] for i in physical_ids]
    return (
        _envelope(boxes),
        [labels[i] for i in sorted(room_ids)],
        supporting,
        {
            "extent_method": "raster_physical_orthogonal_source_planes",
            "source_plane_bboxes": tuple(sorted({r[0] for r in family})),
            "isolated_raster_support_receipts": tuple(
                physical[i] for i in sorted(physical_ids)
            ),
        },
    )


def _raster_physical_supports(source, published, page_id):
    visibility = source.authority()
    selector = ObservationSelector(
        published.revision.document_id,
        published.revision.revision_id,
        published.revision.source_sha256,
        published.snapshot.snapshot_id,
        "address",
    )
    ids = published.raster_opening_primitive_observation_ids
    if len(ids) > _MAX_ALTERNATIVES:
        return ()
    # Full producer inventory is authenticated before any memoized G17 proof.
    observations = {}
    for oid in ids:
        result = visibility.resolve_raster_opening_primitive(
            replace(selector, observation_id=oid)
        )
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.observation is None
        ):
            raise RuntimeError("source_plan_view_raster_integrity_failure")
        if result.observation.page_id == page_id:
            observations[oid] = result.observation
    authority = source.physical_opening_authority()
    physical = {}
    for oid in sorted(observations):
        proof = authority.prove_existence(replace(selector, observation_id=oid))
        if (
            proof.status is not EvidenceResolutionStatus.CORROBORATED
            or proof.existence_record is None
        ):
            continue
        record = proof.existence_record
        if record.record_id in physical:
            continue
        support_ids = tuple(
            sorted(
                i
                for i in record.source_observation_ids
                if i in observations
                and observations[i].observation_kind
                in ("raster_wall_band_face", "raster_wall_band_end")
            )
        )
        if len(support_ids) < 2:
            continue
        physical[record.record_id] = {
            "physical_opening_id": record.record_id,
            "source_observation_ids": support_ids,
            "support_bbox_pdf_pts": _envelope(
                [_line_box(observations[i].geometry) for i in support_ids]
            ),
        }
    return tuple(physical[i] for i in sorted(physical))


def source_owned_plan_viewports(
    source, *, revision_id, page_id, physical_plan_view_shadow=False
):
    """Only actual source producers and their current immutable page are inputs."""
    if type(source) is not SourceVisibilityProducer:
        raise TypeError("actual SourceVisibilityProducer required")
    if type(physical_plan_view_shadow) is not bool:
        raise TypeError("physical_plan_view_shadow must be bool")
    if (
        type(page_id) is not str
        or not page_id.isdecimal()
        or str(int(page_id)) != page_id
        or int(page_id) < 1
    ):
        raise ValueError("source_plan_view_page_invalid")
    published = source.published_snapshot_for_revision(revision_id)
    if (
        published is None
        or source._producer.current_revision_id(published.revision.document_id)
        != revision_id
    ):
        raise ValueError("source_plan_view_revision_unavailable_or_stale")
    if (
        int(page_id) not in published.coverage.decoded_pages
        or int(page_id) in published.coverage.failed_pages
    ):
        raise ValueError("source_plan_view_page_not_decoded")
    data = source._producer._store.source_bytes_by_revision.get(revision_id)
    if not data or sha256(data).hexdigest() != published.revision.source_sha256:
        raise RuntimeError("source_plan_view_immutable_bytes_unavailable")
    with fitz.open(stream=data, filetype="pdf") as pdf:
        page = pdf[int(page_id) - 1]
        ordinary = f07.segment_page_viewports(page, page_number=int(page_id))
        if not physical_plan_view_shadow or any(
            v.view_type in _PLAN_ROLES
            and v.bounding_box is not None
            and (v.status == "resolved" or f07.is_authoritative_derived_viewport(v))
            for v in ordinary
        ):
            return ordinary
        from pb_source_material_semantic_authority import _trusted_words_by_page

        original_words = _trusted_words_by_page(source, published).get(page_id, ())
        anchors = f07.extract_view_title_anchors(page)
        nominated_role = _sheet_role(
            page, original_words, anchors, require_trusted=False
        )
        if nominated_role is None:
            return ordinary
        nominated_labels = _trusted_line_labels(
            page, original_words, require_trusted=False
        )
        if len(nominated_labels) < 2:
            return ordinary
        try:
            calibration = f07.calibrate_viewport_layout(page)
        except NativePageFrameUnresolved:
            return ordinary
        frames = f07.extract_vector_frames(page, calibration)
        owned = [
            f07._to_native_bbox(page, b) for b in f07._title_field_owned_regions(page)
        ]
        excluded = [b for b in owned if b is not None]
        excluded += [
            b
            for b in frames
            if any(f07._bbox_contains(b, m) for m in excluded)
            or f07._frame_looks_like_table(
                b, page, calibration, allow_line_grid_only=False
            )
            or any(f07._bbox_contains(b, a.bbox) for a in anchors)
        ]
        usable = [
            b
            for b in frames
            if b not in excluded and not any(_boxes_touch(b, x) for x in owned if x)
        ]
        if len(usable) > _MAX_ALTERNATIVES:
            return ordinary
        # Exact original text/geometry receipt proofs before and after the
        # transaction. Cache hits never bypass either independent source check.
        with source._native_dimension_source_proof_batch(
            published, page_id=page_id
        ) as rows:
            segments = _source_stroked_segments(page, rows, page_id)
            nominations = compile_native_dimension_cap_components(
                segments=segments, words=_dimension_words(page, original_words)
            )
            nominated_facts = _source_dimension_facts(nominations, segments, excluded)
            if usable:
                nominated_extent = _native_frame_extent(
                    usable, nominated_labels, nominated_facts
                )
                if nominated_extent is None:
                    return ordinary
                nominated_rooms, nominated_dimensions = nominated_extent[1:3]
            else:
                nominated_rooms, nominated_dimensions = (
                    nominated_labels,
                    nominated_facts,
                )
            selected_ids = set(nominated_role[3]) | {
                i for r in nominated_rooms for i in r[1]
            }
            selected_ids.update(i for r in nominated_dimensions for i in r[4])
            text_proofs = []
            words = _corroborate_source_words(
                source, published, original_words, selected_ids, proof_audit=text_proofs
            )
            role = _sheet_role(page, words, anchors)
            labels = _trusted_line_labels(page, words)
            if role is None or len(labels) < 2:
                return ordinary
            trusted_ids = {w.observation_id for w in words if w.trusted}
            facts = _source_dimension_facts(
                [r for r in nominations if r[1] in trusted_ids], segments, excluded
            )
            # Untrusted room-shaped lines retain competitor status. Dropping
            # a rival because its text did not authenticate would elect a view.
            extent = _native_frame_extent(usable, nominated_labels, facts)
            if (
                extent is None
                and not usable
                and published.raster_opening_primitive_observation_ids
            ):
                extent = _raster_plane_extent(
                    nominated_labels,
                    facts,
                    _raster_physical_supports(source, published, page_id),
                )
        if extent is None:
            return ordinary
        if _trusted_words_by_page(source, published).get(page_id, ()) != original_words:
            raise RuntimeError("source_plan_view_text_receipts_changed")
        box, room_rows, dimensions, geometry_proof = extent
        # The entire raw room-shaped census already retained competing
        # extents above. Untrusted words inside the proved component do not
        # own a room and are not silently promoted to label authority.
        room_rows = [r for r in room_rows if set(r[1]) <= trusted_ids]
        if len(room_rows) < 2:
            return ordinary
        # A derived box cannot swallow metadata or a local competing view.
        if any(_boxes_touch(box, b) for b in owned if b is not None) or any(
            _boxes_touch(box, a.bbox) for a in anchors
        ):
            return ordinary
        label, kind, title, title_ids = role
        payload = {
            "document_id": published.revision.document_id,
            "revision_id": revision_id,
            "source_sha256": published.revision.source_sha256,
            "page_id": page_id,
            "view_type": kind,
            "bbox_pdf_pts": box,
        }
        candidate = f07.SegmentedViewport(
            view_id=stable_contract_id("source_plan_view", payload, digest_chars=24),
            page_number=int(page_id),
            view_type=kind,
            label=label,
            title_bbox=title,
            bounding_box=box,
            status="derived",
            boundary_source="title_partition",
            confidence=0.0,
            notes=[
                "bounded source drawing component; whole-sheet, room, metric and finish authorities remain separate"
            ],
            provenance={
                "partition_mode": f07._SOURCE_OWNED_PHYSICAL_PLAN_MODE,
                "source_owned_plan_view_proven": True,
                "explicit_sheet_title_bound": True,
                "unique_source_component": True,
                "orthogonal_source_witnesses": True,
                "title_bbox": title,
                "source_title_observation_ids": title_ids,
                "source_text_corroboration_receipts": tuple(text_proofs),
                "source_room_label_observation_ids": tuple(
                    sorted({i for r in room_rows for i in r[1]})
                ),
                "source_room_label_bboxes": tuple(sorted(r[0] for r in room_rows)),
                "source_geometry_observation_ids": tuple(
                    sorted({i for r in dimensions for i in r[3]})
                ),
                "source_dimension_text_observation_ids": tuple(
                    sorted({i for r in dimensions for i in r[4]})
                ),
                "whole_sheet_plan_universe_proven": False,
                "metric_authority_granted": False,
                "snapshot_id": published.snapshot.snapshot_id,
                **payload,
                **geometry_proof,
            },
        )
        if not f07.validate_non_overlapping_viewports([*ordinary, candidate]):
            return ordinary
        if source.published_snapshot_for_revision(revision_id) != published:
            raise RuntimeError("source_plan_view_snapshot_changed")
        return f07._stamp_segment_page_viewports_product([*ordinary, candidate])
