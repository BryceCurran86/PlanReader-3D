"""Read-only source-native schedule-versus-plan mark census.

PyMuPDF native word boxes are UNROTATED; page.rotation_matrix converts them
to rendered sheet coordinates. Native source receipts do not grant a room
polygon, a floor finish area, ceiling area, or cross-sheet correspondence.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path

import fitz


class ScheduleSourceConflict(ValueError):
    """Reject conflicting or absent original source table evidence."""


def _words(page: fitz.Page) -> list[dict]:
    result = []
    for word in page.get_text("words", flags=fitz.TEXTFLAGS_WORDS):
        if not isinstance(word[4], str) or not word[4].strip():
            continue
        native = fitz.Rect(word[:4])
        rendered = native * page.rotation_matrix
        result.append({
            "text": word[4],
            # PyMuPDF source address is extractor-version scoped; not a
            # production canonical ID or a cross-revision ownership join.
            "address": [int(word[5]), int(word[6]), int(word[7])],
            "native_bbox": [round(z, 6) for z in native],
            "rendered_bbox": [round(z, 6) for z in rendered],
            "xc": (rendered.x0 + rendered.x1) / 2,
            "yc": (rendered.y0 + rendered.y1) / 2,
        })
    return result


def _ordered_line_matches(words: list[dict], terms: tuple[str, ...]) -> list[dict]:
    lines: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for word in words:
        lines[tuple(word["address"][:2])].append(word)
    matches = []
    for (block, line), parts in lines.items():
        parts.sort(key=lambda x: x["xc"])
        if tuple(p["text"].upper() for p in parts) == terms:
            matches.append({
                "block": block, "line": line,
                "y": sum(p["yc"] for p in parts) / len(parts),
                "parts": parts,
            })
    return matches


def _select_header(words: list[dict], heading: dict,
                   columns: tuple[str, ...]) -> list[dict]:
    """Refuse mixing field headers from two distinct simultaneous tables."""
    matches = []
    for mark in words:
        if mark["text"].upper() != columns[0] or mark["yc"] <= heading["y"]:
            continue
        same_row = [
            w for w in words if abs(w["yc"] - mark["yc"]) < 1.5
            and w["address"][0] == mark["address"][0]
        ]
        ordered = sorted(same_row, key=lambda z: z["xc"])
        selected = [
            next((w for w in ordered if w["text"].upper() == name), None)
            for name in columns
        ]
        if (all(selected)
                and len({tuple(w["address"]) for w in selected}) == len(columns)
                and [w["xc"] for w in selected] ==
                sorted(w["xc"] for w in selected)):
            matches.append(selected)
    if len(matches) != 1:
        raise ScheduleSourceConflict("unique source schedule-column header unavailable")
    return matches[0]


def audit_page_schedule(page: fitz.Page, *, heading: tuple[str, ...],
                        columns: tuple[str, ...], marks: tuple[str, ...]) -> dict:
    """Return source-only row evidence, excluding it from other source marks."""
    if (not all(type(x) is str and x for x in heading + columns + marks)
            or len(set(marks)) != len(marks) or len(columns) < 3):
        raise ValueError("explicit, nonduplicate source terms required")
    words = _words(page)
    headings = _ordered_line_matches(words, tuple(x.upper() for x in heading))
    if len(headings) != 1:
        raise ScheduleSourceConflict("unique native source schedule heading unavailable")
    head = headings[0]
    header = _select_header(words, head, tuple(x.upper() for x in columns))
    if header[0]["yc"] <= head["y"]:
        raise ScheduleSourceConflict("source table header precedes heading")
    centers = [w["xc"] for w in header]
    thresholds = [(a + b) / 2 for a, b in zip(centers, centers[1:])]
    groups: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        groups[w["address"][0]].append(w)
    rows, row_marks = {}, set()
    for code in marks:
        candidates = []
        for w in words:
            if w["text"].upper() != code or w["yc"] <= header[0]["yc"]:
                continue
            if not (centers[0] - (thresholds[0] - centers[0])
                    <= w["xc"] < thresholds[0]):
                continue
            parts = [
                z for z in groups[w["address"][0]]
                if abs(z["yc"] - w["yc"]) < 1.5
            ]
            if (not parts or any(z["xc"] < centers[0] - (
                    thresholds[0] - centers[0]) for z in parts)):
                continue
            cells = [[] for _ in columns]
            for z in sorted(parts, key=lambda item: item["xc"]):
                col = sum(z["xc"] >= threshold for threshold in thresholds)
                cells[col].append(z)
            if (len(cells[0]) == 1 and cells[0][0] is w
                    and all(cells[j] for j in range(1, len(cells)))):
                candidates.append((w, cells))
        if len(candidates) != 1:
            raise ScheduleSourceConflict(
                f"unique original source schedule row unavailable: {code}"
            )
        mark, cells = candidates[0]
        row_marks.add(tuple(mark["address"]))
        rows[code] = {
            "source_address": mark["address"],
            "source_bbox_native": mark["native_bbox"],
            "source_bbox_rendered": mark["rendered_bbox"],
            "cells": {
                name.lower(): " ".join(part["text"] for part in cell)
                for name, cell in zip(columns, cells)
            },
            "cell_source_addresses": {
                name.lower(): [part["address"] for part in cell]
                for name, cell in zip(columns, cells)
            },
            "status": "source_native_schedule_row_candidate",
            "grants_physical_floor_or_ceiling_area": False,
        }
    occurrences = {}
    for code in marks:
        occurrences[code] = [
            {
                "source_address": w["address"],
                "source_bbox_native": w["native_bbox"],
                "source_bbox_rendered": w["rendered_bbox"],
                "status": "unbound_native_plan_or_annotation_mark",
                "physical_room_or_zone_id": None,
            }
            for w in words if w["text"].upper() == code
            and tuple(w["address"]) not in row_marks
        ]
    return {
        "page_rotation": page.rotation,
        "page_rect_rendered": list(page.rect),
        "heading_source_addresses": [p["address"] for p in head["parts"]],
        "header_source_addresses": [p["address"] for p in header],
        "source_table_rows": rows,
        "unbound_non_schedule_marks": occurrences,
        "schedule_rows_are_not_physical_occurrences": True,
        "floor_and_ceiling_quantity_publication_granted": False,
        "cross_sheet_correspondence_granted": False,
    }


def audit_pdf_bytes(source: bytes, *, expected_sha256: str | None = None,
                    page_specs: tuple = ()) -> dict:
    if not isinstance(source, bytes) or not source:
        raise ValueError("original PDF bytes required")
    digest = sha256(source).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ScheduleSourceConflict("original PDF SHA-256 mismatch")
    pages = [spec[0] for spec in page_specs]
    if len(pages) != len(set(pages)):
        raise ScheduleSourceConflict("invalid or repeated physical source page")
    with fitz.open(stream=source, filetype="pdf") as doc:
        output = {}
        for number, heading, columns, codes in page_specs:
            if type(number) is not int or not 1 <= number <= len(doc):
                raise ScheduleSourceConflict("invalid or repeated physical source page")
            output[number] = audit_page_schedule(
                doc[number - 1], heading=tuple(heading),
                columns=tuple(columns), marks=tuple(codes)
            )
        return {
            "source_sha256": digest, "page_count": len(doc),
            "source_pages": output, "source_private_bytes_exported": False,
            "geometry_or_quantity_promoted": False,
        }


# Diagnostic caller scope, never producer or measurement prediction input.
MARY_SCHEDULE_SPECS = (
    (11, ("INTERNAL", "FINISHES", "SCHEDULE"),
     ("MARK", "MANUFACTURER", "DESCRIPTION", "COMMENTS"),
     ("FT2", "FT3")),
    (9, ("CEILING", "FINISHES", "SCHEDULE"),
     ("MARK", "MANUFACTURER", "DESCRIPTION"),
     ("IPF1", "CLD3")),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_pdf_bytes(
        args.source_pdf.read_bytes(),
        expected_sha256=args.expected_sha256, page_specs=MARY_SCHEDULE_SPECS
    )
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n")
    else:
        print(payload)


if __name__ == "__main__":
    main()
