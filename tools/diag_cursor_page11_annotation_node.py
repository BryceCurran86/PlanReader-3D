"""Show whether a proven annotation cycle still enters the page-11 wall snap.

Uses the original PDF bytes, the production motif filter, and the production
wall-graph function. Does not publish rooms or change snap tolerance.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz

from pb_annotation_cycle_shadow import classify_exact_annotation_cycles
from pb_physical_wall_candidate_authority import (
    MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
    _filter_repeated_non_physical_drafting_primitives,
)
from pb_vector_geometry_v130 import extract_native_page
from pb_wall_room_topology_stage_a import (
    build_wall_graph_for_viewport,
    filter_structural_segments,
)

PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
EXPECTED_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
GREY = ("d1288i0", "d1308i0")
MARK = "d26362i0"
CROSSING = (576.47998046875, 646.4000244140625)


def _words(page) -> list[dict]:
    return [
        {"text": word[4], "x0": word[0], "y0": word[1], "x1": word[2], "y1": word[3]}
        for word in page.get_text("words")
    ]


def _node_near(graph, point):
    best = None
    for node in graph["nodes"]:
        distance = ((node["x"] - point[0]) ** 2 + (node["y"] - point[1]) ** 2) ** 0.5
        if best is None or distance < best[0]:
            best = (distance, node)
    return best


def _report(page_number: int, page) -> None:
    native = extract_native_page(page)
    structural, _excluded = filter_structural_segments(native["segments"])
    width, height = float(page.rect.width), float(page.rect.height)
    filtered = _filter_repeated_non_physical_drafting_primitives(
        structural, page_width=width, page_height=height,
    )
    classified = classify_exact_annotation_cycles(
        structural, _words(page),
        page_span=min(width, height),
        viewport_bbox=(0.0, 0.0, width, height),
    )
    withheld = set(classified["quarantined_primitive_ids"])
    filtered_ids = {str(segment.get("id") or "") for segment in filtered}
    still_in_graph = sorted(withheld & filtered_ids)
    print(
        "PAGE", page_number,
        "structural", len(structural),
        "after_motif", len(filtered),
        "cap", MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "under_cap", len(filtered) <= MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "proven_cycles", sum(
            1 for row in classified["cycles"]
            if row["status"] == "source_proven_annotation_cycle"
        ),
        "quarantined", len(withheld),
        "still_in_wall_input", len(still_in_graph),
        flush=True,
    )
    if page_number != 11:
        return
    print("MARK_QUARANTINED", MARK in withheld, flush=True)
    mark_cycle = next(
        row for row in classified["cycles"]
        if MARK in row["primitive_ids"] and row["status"] == "source_proven_annotation_cycle"
    )
    local_ids = set(mark_cycle["primitive_ids"]) | set(GREY)
    local = [segment for segment in structural if str(segment.get("id")) in local_ids]
    kept = [segment for segment in local if str(segment.get("id")) not in withheld]
    for label, rows in (("baseline", local), ("withheld", kept)):
        graph = build_wall_graph_for_viewport(rows)
        distance, node = _node_near(graph, CROSSING)
        print(
            label,
            "segments", len(rows),
            "x", round(node["x"], 9),
            "y", round(node["y"], 9),
            "samples", node["samples"],
            "degree", len(graph["adjacency"][node["id"]]),
            "distance_to_grey_crossing", round(distance, 9),
            flush=True,
        )
    page_baseline = build_wall_graph_for_viewport(filtered)
    distance, node = _node_near(page_baseline, CROSSING)
    print(
        "page_baseline",
        "segments", len(filtered),
        "x", round(node["x"], 9),
        "y", round(node["y"], 9),
        "samples", node["samples"],
        "degree", len(page_baseline["adjacency"][node["id"]]),
        "distance_to_grey_crossing", round(distance, 9),
        flush=True,
    )
    page_kept = [segment for segment in filtered if str(segment.get("id")) not in withheld]
    page_graph = build_wall_graph_for_viewport(page_kept)
    distance, node = _node_near(page_graph, CROSSING)
    print(
        "page_withheld",
        "segments", len(page_kept),
        "x", round(node["x"], 9),
        "y", round(node["y"], 9),
        "samples", node["samples"],
        "degree", len(page_graph["adjacency"][node["id"]]),
        "distance_to_grey_crossing", round(distance, 9),
        flush=True,
    )
    nearby = []
    for segment in page_kept:
        for px, py in (
            (float(segment["x1"]), float(segment["y1"])),
            (float(segment["x2"]), float(segment["y2"])),
        ):
            endpoint_distance = ((px - CROSSING[0]) ** 2 + (py - CROSSING[1]) ** 2) ** 0.5
            if endpoint_distance <= 2.5:
                nearby.append((
                    round(endpoint_distance, 6),
                    str(segment.get("id")),
                    round(px, 6),
                    round(py, 6),
                    segment.get("width"),
                    segment.get("stroke"),
                ))
    nearby.sort()
    print("ENDPOINTS_WITHIN_2_5_OF_GREY_CROSSING", len(nearby), nearby, flush=True)
    incident = []
    for edge in page_graph["edges"]:
        if edge["a"] != node["id"] and edge["b"] != node["id"]:
            continue
        incident.append((
            str(edge.get("id")),
            round(float(edge["x1"]), 6), round(float(edge["y1"]), 6),
            round(float(edge["x2"]), 6), round(float(edge["y2"]), 6),
            edge.get("primitive_lineage"),
        ))
    print("INCIDENT_FRAGMENTS", len(incident), flush=True)
    for row in incident:
        print(" FRAGMENT", row, flush=True)


def main() -> None:
    data = PDF.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA:
        raise SystemExit("sha mismatch")
    pdf = fitz.open(stream=data, filetype="pdf")
    try:
        for number in (11,):
            _report(number, pdf.load_page(number - 1))
    finally:
        pdf.close()


if __name__ == "__main__":
    main()
