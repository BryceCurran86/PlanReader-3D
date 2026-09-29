#!/usr/bin/env python3
"""TEST-ONLY exact-source structural-member registration probe.

This script is intentionally diagnostic. Raw compact shapes, nearby text,
axis-like lines and callouts are observations to inspect, not proof that a
structural member exists.

The #1047 registration producer receives only the narrow subset whose member
role text is physically bound inside the same primitive bbox. Every source
view is still marked incomplete, so this probe can never publish a quantity.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

import fitz

from pb_cross_sheet_callout_evidence import find_callout_references
from pb_migration_contracts import EvidenceResolutionStatus
from pb_page_title_authority import analyse_page, resolve_document
from pb_structural_member_authority import StructuralMemberSelector
from pb_structural_member_registration_producer import (
    AuthenticatedStructuralMemberObservation,
    AuthenticatedStructuralMemberView,
    StructuralRegistrationAnchor,
    StructuralRegistrationAnchorKind,
    build_structural_member_registration_authority,
)

SOURCE_SHA256 = "84dec737ede7adfa32b02c6732d4289a6a2d25f7ae50cf07209428f1b4e0c94b"

_MEMBER_RE = re.compile(
    r"\b(?:masonry\s+piers?|piers?|pillars?|columns?|posts?|"
    r"CHS|SHS|RHS|stanchions?)\b",
    re.I,
)
_INSTANCE_MARK_RE = re.compile(
    r"^(?:P|PIER|C|COL|POST|CHS|SHS|RHS)[-_ ]?\d{1,3}[A-Z]?$",
    re.I,
)
_AXIS_TOKEN_RE = re.compile(r"^(?:[A-Z]{1,2}|\d{1,3})$")


def _bbox_tuple(rect: Any) -> tuple[float, float, float, float]:
    return tuple(round(float(v), 3) for v in (rect.x0, rect.y0, rect.x1, rect.y1))


def _center(box: Iterable[float]) -> tuple[float, float]:
    x0, y0, x1, y1 = (float(v) for v in box)
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _intersects(a: Iterable[float], b: Iterable[float]) -> bool:
    ax0, ay0, ax1, ay1 = (float(v) for v in a)
    bx0, by0, bx1, by1 = (float(v) for v in b)
    return min(ax1, bx1) >= max(ax0, bx0) and min(ay1, by1) >= max(ay0, by0)


def _distance(a: Iterable[float], b: Iterable[float]) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    return math.hypot(ax - bx, ay - by)


def _words(page: Any) -> list[dict[str, Any]]:
    out = []
    for index, word in enumerate(page.get_text("words") or ()):
        if len(word) < 5:
            continue
        text = str(word[4]).strip()
        if not text:
            continue
        out.append(
            {
                "id": f"word:{index}",
                "text": text,
                "bbox": [round(float(v), 3) for v in word[:4]],
            }
        )
    return out


def _member_text_blocks(page: Any) -> list[dict[str, Any]]:
    rows = []
    for index, block in enumerate(page.get_text("blocks") or ()):
        text = " ".join(str(block[4]).split()).strip()
        if not text or _MEMBER_RE.search(text) is None:
            continue
        rows.append(
            {
                "id": f"block:{index}",
                "text": text,
                "bbox": [round(float(v), 3) for v in block[:4]],
            }
        )
    return rows


def _compact_closed_shapes(page: Any, page_no: int) -> list[dict[str, Any]]:
    """Inventory compact closed source drawings without assigning semantics."""
    short_side = max(1.0, min(float(page.rect.width), float(page.rect.height)))
    max_side = short_side * 0.06
    rows = []
    for drawing_index, drawing in enumerate(page.get_drawings() or ()):
        rect = drawing.get("rect")
        if rect is None:
            continue
        width = float(rect.width)
        height = float(rect.height)
        if width <= 0 or height <= 0 or max(width, height) > max_side:
            continue
        kinds = tuple(str(item[0]) for item in (drawing.get("items") or ()))
        direct_rect = kinds == ("re",)
        closed_lines = False
        if len(kinds) >= 3 and all(kind == "l" for kind in kinds):
            items = list(drawing.get("items") or ())
            try:
                first = items[0][1]
                last = items[-1][2]
                closed_lines = math.hypot(
                    float(first.x) - float(last.x),
                    float(first.y) - float(last.y),
                ) <= 0.05
            except Exception:
                closed_lines = False
        if not (direct_rect or closed_lines):
            continue
        aspect = max(width, height) / max(min(width, height), 1e-9)
        bbox = _bbox_tuple(rect)
        cx, cy = _center(bbox)
        rows.append(
            {
                "primitive_id": f"page:{page_no}:drawing:{drawing_index}",
                "bbox": list(bbox),
                "width_pt": round(width, 4),
                "height_pt": round(height, 4),
                "aspect": round(aspect, 4),
                "fill": drawing.get("fill"),
                "stroke": drawing.get("color"),
                "stroke_width": drawing.get("width"),
                "layer": drawing.get("layer"),
                "kinds": list(kinds),
                "title_block_band_candidate": bool(
                    cx >= float(page.rect.width) * 0.82
                    or cy >= float(page.rect.height) * 0.86
                ),
            }
        )
    return sorted(rows, key=lambda row: (row["bbox"][1], row["bbox"][0], row["primitive_id"]))


def _axis_like_lines(page: Any, page_no: int) -> list[dict[str, Any]]:
    """Report long near-horizontal/vertical lines; never promote them to grid axes."""
    threshold = max(float(page.rect.width), float(page.rect.height)) * 0.16
    rows = []
    for drawing_index, drawing in enumerate(page.get_drawings() or ()):
        for item_index, item in enumerate(drawing.get("items") or ()):
            if not item or str(item[0]) != "l" or len(item) < 3:
                continue
            a, b = item[1], item[2]
            try:
                x1, y1, x2, y2 = float(a.x), float(a.y), float(b.x), float(b.y)
            except Exception:
                continue
            length = math.hypot(x2 - x1, y2 - y1)
            if length < threshold:
                continue
            angle = abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 180.0
            axis_aligned = min(angle, abs(angle - 90.0), abs(angle - 180.0)) <= 1.5
            if not axis_aligned:
                continue
            rows.append(
                {
                    "primitive_id": f"page:{page_no}:drawing:{drawing_index}:item:{item_index}",
                    "bbox": [
                        round(min(x1, x2), 3),
                        round(min(y1, y2), 3),
                        round(max(x1, x2), 3),
                        round(max(y1, y2), 3),
                    ],
                    "length_pt": round(length, 3),
                    "angle_deg": round(angle, 3),
                    "layer": drawing.get("layer"),
                    "dashes": drawing.get("dashes"),
                }
            )
    return rows


def _shape_evidence(
    shape: dict[str, Any],
    words: list[dict[str, Any]],
    member_blocks: list[dict[str, Any]],
    callouts: list[Any],
) -> dict[str, Any]:
    bbox = shape["bbox"]
    bound_member_blocks = [
        block for block in member_blocks if _intersects(bbox, block["bbox"])
    ]
    bound_instance_marks = [
        word
        for word in words
        if _intersects(bbox, word["bbox"])
        and _INSTANCE_MARK_RE.fullmatch(word["text"].strip()) is not None
    ]
    nearby_member_blocks = sorted(
        (
            {**block, "distance_pt": round(_distance(bbox, block["bbox"]), 3)}
            for block in member_blocks
            if _distance(bbox, block["bbox"]) <= 90.0
        ),
        key=lambda row: (row["distance_pt"], row["id"]),
    )[:8]
    nearby_axis_tokens = sorted(
        (
            {**word, "distance_pt": round(_distance(bbox, word["bbox"]), 3)}
            for word in words
            if _AXIS_TOKEN_RE.fullmatch(word["text"].strip()) is not None
            and _distance(bbox, word["bbox"]) <= 55.0
        ),
        key=lambda row: (row["distance_pt"], row["id"]),
    )[:12]
    nearby_callouts = []
    for callout in callouts:
        if _distance(bbox, callout.callout_bbox) <= 120.0:
            nearby_callouts.append(
                {
                    "mark": callout.mark,
                    "referenced_sheet_code": callout.referenced_sheet_code,
                    "bbox": list(callout.callout_bbox),
                    "distance_pt": round(_distance(bbox, callout.callout_bbox), 3),
                }
            )
    return {
        **shape,
        "bound_member_role_blocks": bound_member_blocks,
        "bound_instance_marks": bound_instance_marks,
        "nearby_member_role_blocks": nearby_member_blocks,
        "nearby_axis_tokens": nearby_axis_tokens,
        "nearby_cross_sheet_callouts": sorted(
            nearby_callouts,
            key=lambda row: (
                row["distance_pt"],
                row["referenced_sheet_code"],
                row["mark"],
            ),
        ),
    }


def _strict_observations(
    *,
    page_no: int,
    sheet_number: str,
    shapes: list[dict[str, Any]],
) -> list[AuthenticatedStructuralMemberObservation]:
    """Create only directly bound role+instance observations.

    Proximity-only role text, generic square geometry, axis tokens and callouts
    are intentionally insufficient.
    """
    out = []
    for shape in shapes:
        role_blocks = shape["bound_member_role_blocks"]
        marks = shape["bound_instance_marks"]
        if not role_blocks or len(marks) != 1:
            continue
        mark = marks[0]
        role_evidence = tuple(
            sorted(f"page:{page_no}:{row['id']}:{row['text']}" for row in role_blocks)
        )
        mark_evidence = f"page:{page_no}:{mark['id']}:{mark['text']}"
        namespace = sheet_number or f"page:{page_no}:source-instance-mark"
        anchor = StructuralRegistrationAnchor(
            kind=StructuralRegistrationAnchorKind.SOURCE_INSTANCE_MARK,
            namespace_id=namespace,
            value_id=mark["text"].strip(),
            source_evidence_ids=(mark_evidence,),
        )
        out.append(
            AuthenticatedStructuralMemberObservation(
                member_kind="masonry_pier",
                page_id=str(page_no),
                view_id=f"page:{page_no}",
                view_type="source_drawing",
                source_evidence_ids=(shape["primitive_id"], *role_evidence, mark_evidence),
                source_primitive_ids=(shape["primitive_id"],),
                member_proposition_evidence_ids=role_evidence,
                registration_anchors=(anchor,),
                geometry_signature="diagnostic_compact_closed_shape",
            )
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--start", type=int, default=219)
    parser.add_argument("--end", type=int, default=238)
    parser.add_argument("--expected-sha256", default=SOURCE_SHA256)
    args = parser.parse_args()

    import hashlib

    source_bytes = args.pdf.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != args.expected_sha256:
        raise SystemExit(
            f"source SHA mismatch: expected {args.expected_sha256}, got {actual_sha}"
        )

    doc = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        start = max(1, args.start)
        end = min(int(args.end), doc.page_count)
        page_numbers = list(range(start, end + 1))
        analyses = [analyse_page(doc[page_no - 1], page_no) for page_no in page_numbers]
        titles = resolve_document(analyses)
        title_by_page = {title.page_no: title for title in titles}

        pages = []
        strict_source_observations = []
        source_views = []
        for page_no in page_numbers:
            page = doc[page_no - 1]
            title = title_by_page[page_no]
            words = _words(page)
            member_blocks = _member_text_blocks(page)
            callouts = find_callout_references(page, page_num=page_no)
            shapes = [
                _shape_evidence(shape, words, member_blocks, callouts)
                for shape in _compact_closed_shapes(page, page_no)
            ]
            strict = _strict_observations(
                page_no=page_no,
                sheet_number=title.sheet_number,
                shapes=shapes,
            )
            strict_source_observations.extend(strict)

            source_views.append(
                AuthenticatedStructuralMemberView(
                    page_id=str(page_no),
                    view_id=f"page:{page_no}",
                    view_type="source_drawing",
                    complete=False,
                    source_evidence_ids=(f"murera:{actual_sha}:page:{page_no}",),
                    reason_codes=("diagnostic_member_universe_completeness_unproven",),
                )
            )

            pages.append(
                {
                    "page": page_no,
                    "page_rect": [
                        round(float(page.rect.width), 3),
                        round(float(page.rect.height), 3),
                    ],
                    "drawing_title": title.title,
                    "title_confidence": title.confidence,
                    "sheet_number": title.sheet_number,
                    "sheet_number_source": title.sheet_number_source,
                    "member_text_blocks": member_blocks,
                    "cross_sheet_callouts": [
                        {
                            "mark": item.mark,
                            "referenced_sheet_code": item.referenced_sheet_code,
                            "bbox": list(item.callout_bbox),
                        }
                        for item in callouts
                    ],
                    "compact_closed_shape_count": len(shapes),
                    "compact_closed_shapes": shapes,
                    "axis_like_line_count": len(_axis_like_lines(page, page_no)),
                    "axis_like_lines": _axis_like_lines(page, page_no)[:160],
                    "strict_member_observation_count": len(strict),
                }
            )

        selector = StructuralMemberSelector(
            document_id="murera-official-source",
            revision_id=f"sha256:{actual_sha}",
            source_sha256=actual_sha,
            snapshot_id=f"source-probe:{actual_sha[:16]}",
            decision_scope_id=f"murera:pages:{start}-{end}:diagnostic",
            member_kind="masonry_pier",
        )
        registration = build_structural_member_registration_authority(
            selector=selector,
            source_observations=tuple(strict_source_observations),
            source_views=tuple(source_views),
        )

        result = {
            "diagnostic_only": True,
            "do_not_merge": True,
            "source_sha256": actual_sha,
            "page_range": [start, end],
            "rules": {
                "raw_shape_is_member_proof": False,
                "nearby_text_is_member_proof": False,
                "axis_token_is_grid_anchor": False,
                "callout_is_member_proof": False,
                "strict_observation_requires": (
                    "member-role text physically intersecting the primitive bbox "
                    "AND exactly one role-shaped source instance mark physically "
                    "intersecting the same primitive bbox"
                ),
                "view_completeness": "always false in this diagnostic",
            },
            "pages": pages,
            "strict_source_observation_count": len(strict_source_observations),
            "authority_attempt": {
                "status": registration.resolution.status.value,
                "quantity": registration.resolution.quantity,
                "reason_codes": list(registration.resolution.reason_codes),
                "observation_count": len(registration.observations),
                "relation_count": len(registration.relations),
                "view_scopes": [
                    {
                        "page_id": row.page_id,
                        "view_id": row.view_id,
                        "view_type": row.view_type,
                        "complete": row.complete,
                        "reason_codes": list(row.reason_codes),
                    }
                    for row in registration.view_scopes
                ],
            },
        }
        print(json.dumps(result, indent=2, sort_keys=True, default=str))

        # This is an architectural invariant of the test-only probe.
        if registration.resolution.status is EvidenceResolutionStatus.CORROBORATED:
            raise SystemExit("diagnostic unexpectedly corroborated a quantity")
        if registration.resolution.quantity is not None:
            raise SystemExit("diagnostic unexpectedly published a quantity")
    finally:
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
