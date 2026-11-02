"""S3 census for ONE page of ONE original (read-only). Counts only; no coordinates are written.

usage: python tools/item8_s3/s3_census.py <label> <pdf> <page_number> <out_json> <budget_seconds>

Pre-registered unit (docs/engineering/claude_item8_s3_population_study_20261102.md, Part A): every jamb-bounded structure the
existing six-line rule finds on the page, with its own lines as the named members. Structures are processed in candidate-id
order (a hash order that does not depend on content); if the time budget runs out the page is reported as partial with the
number processed. Shadow measurement only: it imports the S2b adapter and decides nothing."""
import json
import sys
import time
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pb_face_ink_paint_relation_shadow import FaceInkPaintRelationAudit  # noqa: E402
from pb_source_observation_authority import ObservationSelector  # noqa: E402
from pb_source_visibility_authority import NATIVE_PDF_VISIBLE_SEGMENT, SourceVisibilityProducer  # noqa: E402


def census_page(label: str, pdf: Path, page_no: int, budget: float) -> dict:
    t0 = time.time()
    raw = pdf.read_bytes()
    sha = sha256(raw).hexdigest()
    result = dict(label=label, page=page_no, sha256_prefix=sha[:8], status="started", structures_found=0,
                  structures_processed=0, seconds=0.0, rows=[])
    try:
        producer = SourceVisibilityProducer(producer_method="s3-census-readonly", producer_version="1")
        published = producer.ingest_native_pdf_bytes(
            document_id=f"s3:{label}:{sha[:16]}", source_bytes=raw, source_locator="memory://s3.pdf", page_ids=(page_no,))
        rows = producer.authority().authenticated_visible_observations(published, bind_page_id=str(page_no))
        native = [(oid, rec) for oid, rec in rows if rec.observation_kind == NATIVE_PDF_VISIBLE_SEGMENT]
        result["visible_native_segments"] = len(native)
        if not native:
            result["status"] = "no_native_visible_segments"
        else:
            def selector(observation_id):
                return ObservationSelector(published.revision.document_id, published.revision.revision_id,
                                           published.revision.source_sha256, published.snapshot.snapshot_id, observation_id)

            physical = producer.physical_opening_authority()
            source_result = physical._resolve_visible_cached(selector(native[0][0]))
            records, _failures = physical._visible_snapshot_records(source_result)
            started = time.time()
            structures = sorted(physical._visible_structural_candidates(source_result.observation, tuple(records)),
                                key=lambda c: c.candidate_id)
            result["structures_found"] = len(structures)
            result["enumeration_seconds"] = round(time.time() - started, 1)
            audit = FaceInkPaintRelationAudit(physical, producer, enabled=True)
            for structure in structures:
                if time.time() - t0 > budget:
                    result["status"] = "partial_time_budget"
                    break
                members = tuple(sorted(structure.source_observation_ids))
                sel = selector(members[0])
                inventory = physical.seeded_face_ink_inventory(sel, members)
                entry = next((s for s in inventory.structures if s.candidate_id == structure.candidate_id), None)
                if entry is None:
                    result["rows"].append(dict(anomaly="structure_not_reproduced_from_its_own_members"))
                    result["structures_processed"] += 1
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
                result["rows"].append(row)
                result["structures_processed"] += 1
            if result["status"] == "started":
                result["status"] = "complete"
    except Exception as exc:  # recorded, never hidden
        result["status"] = "error:" + type(exc).__name__ + ":" + str(exc)[:160]
    result["seconds"] = round(time.time() - t0, 1)
    return result


if __name__ == "__main__":
    label, pdf_path, page, out_json, budget_seconds = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4], float(sys.argv[5])
    outcome = census_page(label, pdf_path, page, budget_seconds)
    Path(out_json).write_text(json.dumps(outcome), encoding="utf-8")
    print(label, page, outcome["status"], "found", outcome["structures_found"], "processed", outcome["structures_processed"],
          "rows", len(outcome["rows"]), outcome["seconds"], "s")
