"""Read-only overlay of the structural room-region shadow on an original PDF page.

Computes, on the page's own native vector linework, (1) the structural wall ink, (2) the attached partition ink, (3) the typed opening
gaps and (4) the enclosed free-space regions they bound, with the room-name candidates and outlined-lettering runs that stand in each
region, and draws them: wall faces looking onto the page exterior (heavy red), partition and internal faces (red / blue), typed
opening-gap chords (cyan), parallel-ladder and lettering negatives (orange / purple), region fills with their index, native room-name
candidates (green boxes) and glyph runs (grey boxes). It writes a JSON summary. It never writes to the PDF or the repository checkout and
publishes no authority: regions are evidence, the label texts are source-native text whose trust is not established here, and optional
OCR readings (``--ocr-candidates``) are candidate-only.

Share-safe by default. The drawing is made on a white sheet (no render of the page, so no title block, client name, address or note text),
only room names the existing room-name vocabulary accepts are kept, and OCR readings are reduced to the vocabulary match, its confidence
and position. ``--private-detail`` adds the faded page render and every OCR line: for local review of a private original only, never to
be committed or posted.

Usage: python -m tools.diag_structural_room_region_overlay --pdf FILE --page 3 --png OUT.png --json OUT.json [--ocr-candidates]
                                                          [--private-detail]
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import fitz

from pb_migration_contracts import stable_contract_id
from pb_structural_partition_ink_shadow import (
    NOT_PARTITION_INK,
    PARTITION_INK_CANDIDATE,
    classify_attached_partition_ink,
)
from pb_structural_room_region_shadow import RegionLabelInput, StructuralRoomRegionReport, derive_structural_room_regions
from pb_structural_wall_ink_shadow import (
    NOT_WALL_INK,
    WALL_NETWORK_INK_CANDIDATE,
    classify_structural_wall_ink,
)
from pb_vector_geometry_v130 import extract_native_page

PALETTE = [(255, 0, 0), (0, 120, 255), (0, 170, 60), (230, 140, 0), (160, 0, 200), (0, 180, 180), (200, 0, 120), (90, 90, 0)]


def room_name_candidates(page: "fitz.Page") -> List[RegionLabelInput]:
    """Whole native text lines that the existing room-label vocabulary reads as a room name. Trust is not established here."""
    from pb_source_room_label_authority import _normalized_room_line

    lines: Dict[Tuple[int, int], List[Tuple[int, Tuple[float, float, float, float], str]]] = {}
    for x0, y0, x1, y1, text, block, line, word in page.get_text("words"):
        lines.setdefault((int(block), int(line)), []).append((int(word), (x0, y0, x1, y1), str(text)))
    out: List[RegionLabelInput] = []
    for (block, line), words in sorted(lines.items()):
        words.sort(key=lambda w: (w[0], w[1][1], w[1][0]))
        text = " ".join(w[2] for w in words)
        normalized = _normalized_room_line(text)
        if normalized is None:
            continue
        bbox = (min(w[1][0] for w in words), min(w[1][1] for w in words), max(w[1][2] for w in words), max(w[1][3] for w in words))
        word_ids = tuple(f"w{block}.{line}.{w[0]}" for w in words)
        out.append(RegionLabelInput(stable_contract_id("native_line", {"b": block, "l": line, "text": normalized,
                                                                      "bbox": [round(v, 2) for v in bbox]}),
                                    normalized, bbox, "not_supplied", word_ids))
    return out


def _ocr_candidates(page: "fitz.Page", report: StructuralRoomRegionReport, dpi: int = 200,
                    backend: Any = None) -> Dict[str, List[Dict[str, Any]]]:
    """Candidate-only OCR readings of the page inside each region (never authority). ``backend`` defaults to RapidOCR."""
    from PIL import Image
    from shapely.geometry import Point, Polygon

    from pb_portable_raster_ocr_authority import RapidOCRBackend
    from pb_source_room_label_authority import _normalized_room_line

    backend = RapidOCRBackend() if backend is None else backend
    if not backend.is_available():
        return {}
    found: Dict[str, List[Dict[str, Any]]] = {}
    for region in report.regions:
        x0, y0, x1, y1 = region.bbox
        clip = fitz.Rect(x0, y0, x1, y1) * page.rotation_matrix
        pix = page.get_pixmap(dpi=dpi, clip=clip, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        poly = Polygon(region.polygon)
        rows = []
        for line in backend.extract_lines(image, dpi=dpi):
            bx0, by0, bx1, by1 = line.bbox_pt or (0.0, 0.0, 0.0, 0.0)
            # bbox_pt is relative to the clip in rotated view points; map the centre back to the native frame
            centre_view = fitz.Point(clip.x0 + (bx0 + bx1) / 2, clip.y0 + (by0 + by1) / 2)
            centre = centre_view * ~page.rotation_matrix
            if poly.contains(Point(centre.x, centre.y)):
                rows.append({"text": line.text, "confidence": line.confidence, "centre": [round(centre.x, 2), round(centre.y, 2)],
                             "room_name_vocabulary_match": _normalized_room_line(line.text), "candidate_only": True})
        found[region.region_id] = rows
    return found


def run(pdf: Path, page_number: int, png: Path | None, summary_path: Path | None, dpi: int = 100,
        ocr_candidates: bool = False, ocr_backend: Any = None, private_detail: bool = False) -> dict:
    document = fitz.open(str(pdf))
    page = document[page_number - 1]
    segments = extract_native_page(page)["segments"]
    width, height = page.rect.width, page.rect.height
    ink = classify_structural_wall_ink(segments, page_width=width, page_height=height)
    partition = classify_attached_partition_ink(segments, ink, page_width=width, page_height=height)
    labels = room_name_candidates(page)
    regions = derive_structural_room_regions(segments, ink, partition, labels=labels)
    ocr = _ocr_candidates(page, regions, backend=ocr_backend) if ocr_candidates else {}
    if not private_detail:
        # share-safe: keep only readings the room-name vocabulary accepts, without the raw OCR text
        ocr = {rid: [{k: v for k, v in row.items() if k != "text"} for row in rows if row["room_name_vocabulary_match"] is not None]
               for rid, rows in ocr.items()}
    ink_counts = Counter(d.classification for d in ink.decisions)
    summary = {
        "page": page_number,
        "segments": len(segments),
        "structural": {"classification_counts": dict(ink_counts), "opening_gap_candidates": len(ink.opening_gaps),
                       "glyph_sized_runs": len(ink.glyph_runs)},
        "partition": {"decision_counts": dict(Counter(d.classification for d in partition.decisions)),
                      "opening_gap_candidates_with_partitions": len(partition.opening_gaps)},
        "regions": {
            "closure_half_width_pt": regions.closure_half_width_pt,
            "listed": len(regions.regions),
            "discarded_fragments": regions.discarded_fragment_count,
            "exterior_adjacent_primitives": len(regions.exterior_adjacent_primitive_ids),
            "interior_only_primitives": len(regions.interior_only_primitive_ids),
            "within_wall_body_primitives": len(regions.within_wall_body_primitive_ids),
            "typed_opening_chords": len(regions.chord_ids),
            "reason_codes": list(regions.reason_codes),
        },
        "region_rows": [
            {
                "index": k, "region_id": r.region_id, "area_pt2": r.area_pt2, "gross_area_pt2": r.gross_area_pt2,
                "inradius_pt": r.inradius_pt, "bbox": list(r.bbox), "hole_count": r.hole_count,
                "boundary_tier_counts": list(r.boundary_tier_counts), "boundary_evidence_kinds": dict(r.boundary_evidence_kinds),
                "closure_chord_count": len(r.closure_chord_ids),
                "multi_label": r.multi_label, "glyph_run_count": len(r.glyph_runs), "polygon": [list(p) for p in r.polygon],
                "native_room_name_candidates": [
                    {"text": lab.text, "trust": lab.trust, "centre": list(lab.centre), "bbox_crosses_boundary": lab.bbox_crosses_boundary}
                    for lab in r.labels],
                "ocr_candidate_lines": ocr.get(r.region_id, []),
            }
            for k, r in enumerate(regions.regions)
        ],
        "native_room_name_candidates_on_page": len(labels),
        "share_safe": not private_detail,
        "shadow_only": regions.shadow_only,
        "live_effect": regions.live_effect,
        "room_authority_granted": regions.room_authority_granted,
        "scale_authority_granted": regions.scale_authority_granted,
    }
    if summary_path is not None:
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    if png is not None:
        _draw(page, segments, ink, partition, regions, labels, ocr, png, dpi, private_detail)
    return summary


def _draw(page, segments, ink, partition, regions, labels, ocr, png: Path, dpi: int, private_detail: bool = False) -> None:
    import numpy as np
    from PIL import Image, ImageDraw

    zoom = dpi / 72
    to_view = page.rotation_matrix
    if private_detail:
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        faded = 255 - (255 - np.asarray(image).astype("float32")) * 0.30
        image = Image.fromarray(faded.astype("uint8")).convert("RGBA")
    else:
        image = Image.new("RGBA", (int(page.rect.width * zoom) + 1, int(page.rect.height * zoom) + 1), (255, 255, 255, 255))
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    def view(x: float, y: float) -> Tuple[float, float]:
        p = fitz.Point(x, y) * to_view
        return (p.x * zoom, p.y * zoom)

    for k, region in enumerate(regions.regions):
        colour = PALETTE[k % len(PALETTE)]
        ring = [view(x, y) for x, y in region.polygon]
        draw.polygon(ring, fill=colour + (60,), outline=colour + (255,))
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        names = "/".join(lab.text for lab in region.labels)[:28]
        draw.text((cx - 10, cy - 6), f"#{k} {names}", fill=colour + (255,))
        for row in ocr.get(region.region_id, []):
            if row["room_name_vocabulary_match"] is None:
                continue                                                    # only readings the room-name vocabulary accepts
            ox, oy = view(*row["centre"])
            draw.text((ox - 14, oy + 4), "? " + str(row["room_name_vocabulary_match"])[:18], fill=(230, 110, 0, 255))
    exterior = set(regions.exterior_adjacent_primitive_ids)
    ink_by_id = {d.source_primitive_id: d for d in ink.decisions}
    part_by_id = {d.source_primitive_id: d for d in partition.decisions}
    for segment in segments:
        sid = str(segment.get("id"))
        d = ink_by_id.get(sid)
        q = part_by_id.get(sid)
        if d is not None and d.classification == WALL_NETWORK_INK_CANDIDATE:
            colour, width = ((200, 0, 0, 255), 3) if sid in exterior else ((220, 60, 60, 255), 2)
        elif q is not None and q.classification == PARTITION_INK_CANDIDATE:
            colour, width = (0, 90, 255, 255), 2
        elif q is not None and q.classification == NOT_PARTITION_INK:
            colour, width = (230, 140, 0, 160), 1
        elif d is not None and d.classification == NOT_WALL_INK and "repeated_small_path_run" in d.reason_codes:
            colour, width = (150, 0, 200, 90), 1
        else:
            continue
        draw.line([view(segment["x1"], segment["y1"]), view(segment["x2"], segment["y2"])], fill=colour, width=width)
    for gap in partition.opening_gaps or ink.opening_gaps:
        draw.line([view(*gap.end_a), view(*gap.end_b)], fill=(0, 190, 190, 255), width=3)
    for lab in labels:
        x0, y0, x1, y1 = lab.bbox
        draw.polygon([view(x0, y0), view(x1, y0), view(x1, y1), view(x0, y1)], outline=(0, 140, 0, 255))
    for run_ in ink.glyph_runs:
        x0, y0, x1, y1 = run_.bbox
        draw.polygon([view(x0, y0), view(x1, y0), view(x1, y1), view(x0, y1)], outline=(130, 130, 130, 120))
    Image.alpha_composite(image, layer).convert("RGB").save(str(png))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True, help="1-based page number")
    parser.add_argument("--png", type=Path)
    parser.add_argument("--json", type=Path, dest="summary")
    parser.add_argument("--dpi", type=int, default=100)
    parser.add_argument("--ocr-candidates", action="store_true",
                        help="Also read each region with RapidOCR when installed; candidate-only, never authority.")
    parser.add_argument("--private-detail", action="store_true",
                        help="Also draw on a faded render of the page and keep every OCR line. Local review of a private original only: "
                             "the output can show a title block, names and notes, so never commit or post it.")
    args = parser.parse_args()
    for target in (args.png, args.summary):
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
    summary = run(args.pdf, args.page, args.png, args.summary, args.dpi, args.ocr_candidates, private_detail=args.private_detail)
    print(json.dumps({k: v for k, v in summary.items() if k != "region_rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
