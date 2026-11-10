"""Read-only, counts-only diagnostic for the door-swing figure binding SHADOW.

Reads one original in place (SHA-checked), composes the plan page with the existing producers, finds the native
quarter-circle door swings and the figure-like words, applies the shadow rule (a printed figure inside a door's swing
drawing belongs to that door) and compares each candidate with the word the existing opening label authority bound. It
writes ids, reason codes and counts only and never writes a width, kind, host, frame, quantity or customer row.

    python -m tools.diag_door_swing_figure_binding_shadow --pdf <original.pdf> --plan-page 3 \
        --expected-source-sha256 <hex> --output out.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Sequence

from pb_door_swing_figure_binding_adapter import (
    opening_ends_from_composition, read_figure_words, read_native_swing_arcs,
)
from pb_door_swing_figure_binding_shadow import bind_figures_to_swings


def _label_authority_word(source, comp, opening_id: str):
    """The single text observation id the opening label authority used for this opening, else ``None``."""
    from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
    from pb_source_observation_authority import ObservationSelector

    trace = next((t for t in comp.opening_bindings if t.opening_identity_id == opening_id), None)
    selector = comp.binding_selectors.get(opening_id)
    if trace is None or selector is None:
        return None
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(source).publish_scope(ObservationSelector(
        document_id=selector.document_id, revision_id=selector.revision_id, source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id, observation_id=trace.representative_observation_id))
    evidence = getattr(result, "evidence", None)
    if evidence is None or len(evidence.source_text_observation_ids) != 1:
        return None
    return str(evidence.source_text_observation_ids[0])


def run(pdf: Path, plan_page: int, expected_sha: str, focus: Sequence[str] = ()) -> dict:
    from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer

    payload = pdf.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != expected_sha:
        raise SystemExit("original source SHA-256 mismatch")
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall",
                                      producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
                                      raster_paired_outer_faces_shadow=True)
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://door-swing-figure-binding.pdf", page_ids=(plan_page,))
    revision = initial.revision.revision_id
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=revision, page_ids=(str(plan_page),),
        include_unmeasured_ink_closed_flanks_shadow=True, source_fragment_roles_shadow=True)
    arcs = read_native_swing_arcs(payload, expected_sha256=sha, page_number=plan_page)
    figures = read_figure_words(source, revision_id=revision, page_id=str(plan_page))
    openings = opening_ends_from_composition(comp, comp.physical_opening_authority)
    bindings = bind_figures_to_swings(openings, arcs, figures, enabled=True)
    by_word = {f.word_id: f for f in figures}
    rows, agree, different, no_label = [], 0, 0, 0
    for b in bindings:
        if not b.is_candidate:
            continue
        label_word = _label_authority_word(source, comp, b.opening_id)
        verdict = "no_label_authority_word" if label_word is None else ("agrees" if label_word == b.figure_word_id else "different")
        agree += verdict == "agrees"
        different += verdict == "different"
        no_label += verdict == "no_label_authority_word"
        rows.append({"opening": b.opening_id[-8:], "figure": b.figure_text, "text_trust": b.text_trust,
                     "swing": b.swing_arc_id, "receipt_count": len(b.source_observation_ids),
                     "label_authority": verdict, "result_id": b.result_id})
    candidates = [b for b in bindings if b.is_candidate]
    return {
        "schema_version": "1.0.0", "source_sha256": sha, "shadow_only": True, "benchmark_score_granted": False,
        "plan_page": plan_page, "arc_source": "native_cubic_drawings_of_the_sha_pinned_pdf_not_visibility_observations",
        "native_swing_arcs": len(arcs), "figure_like_words": len(figures),
        "figure_text_trust": dict(sorted(Counter(f.text_trust or "none" for f in figures).items())),
        "plan_opening_records": len(openings),
        "bindings_by_status": dict(sorted(Counter(b.status.value for b in bindings).items())),
        "first_reason_counts": dict(sorted(Counter(b.reason_codes[0] for b in bindings).items())),
        "candidate_records": len(candidates), "distinct_swings_with_a_candidate": len({b.swing_arc_id for b in candidates}),
        "distinct_figures_bound": len({b.figure_word_id for b in candidates}),
        "label_authority_agrees": agree, "label_authority_different": different, "label_authority_no_word": no_label,
        "candidates": sorted(rows, key=lambda r: r["opening"]),
        "focus_rows": [{"opening": b.opening_id[-8:], "status": b.status.value, "reasons": list(b.reason_codes),
                        "figure": b.figure_text, "swing": b.swing_arc_id}
                       for b in bindings if any(b.opening_id.endswith(f) for f in focus)],
        "figures_total_known": len(by_word),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--plan-page", type=int, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--focus", nargs="*", default=[], help="opening id suffixes to explain")
    args = parser.parse_args()
    report = run(args.pdf, args.plan_page, args.expected_source_sha256, args.focus)
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({"native_swing_arcs": report["native_swing_arcs"], "candidates": report["candidate_records"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
