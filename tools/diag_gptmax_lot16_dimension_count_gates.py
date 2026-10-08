"""Source-only all-page audit; never an input to live prediction or scoring."""
from collections import Counter
from dataclasses import asdict
import hashlib
import json

from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_schedule_opening_instance_binding_authority import ScheduleOpeningInstanceBindingProducer
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_lot16_current_host_funnel import PDF, EXPECTED_SHA


def main():
    data = PDF.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA:
        raise SystemExit("source sha mismatch")
    source = SourceVisibilityProducer(producer_method="gptmax-dimension-count-source-audit", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id=f"source-audit:{EXPECTED_SHA[:32]}",
        source_bytes=data, source_locator="memory://dimension-count-source-audit.pdf")
    published = source.augment_with_raster_opening_primitives(published.revision.revision_id, page_ids=("3",))
    physical = source.physical_opening_authority()
    binding = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    labels = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    dimensions = source.opening_dimension_authority()
    rows = {}
    for observation_id in sorted(published.raster_opening_primitive_observation_ids):
        selector = ObservationSelector(document_id=published.revision.document_id,
            revision_id=published.revision.revision_id, source_sha256=EXPECTED_SHA,
            snapshot_id=published.snapshot.snapshot_id, observation_id=observation_id)
        opening = physical.prove_existence(selector).existence_record
        if (opening is None or opening.structural_pattern != "raster_door_swing_wall_band_interruption"
                or opening.record_id in rows):
            continue
        schedule = binding.publish_scope(opening_selector=selector, decision_scope_id="source-audit:page-3")
        width = dimensions.resolve_width(selector)
        label = labels.publish_scope(selector)
        rows[opening.record_id] = {
            "aperture_bbox_pt": opening.aperture_bbox_pt,
            "schedule_status": schedule.status.value,
            "schedule_reason_codes": schedule.reason_codes,
            "authenticated_tag_mark": schedule.authenticated_tag_mark,
            "schedule_record": None if schedule.record is None else asdict(schedule.record),
            "width_status": width.status.value,
            "width_reason_codes": width.reason_codes,
            "width_mm": width.value_mm,
            "label_status": label.status.value,
            "label_reason_codes": label.reason_codes,
            "label_evidence": None if label.evidence is None else asdict(label.evidence),
        }
    semantic = SemanticOpeningEnumerationProducer.from_source_visibility_producer(source).publish_page_scope(
        revision_id=published.revision.revision_id, decision_scope_id="source-audit:page-3", page_ids=("3",))
    record = semantic.record
    print(json.dumps({
        "source_sha256": EXPECTED_SHA,
        "source_decode_coverage": asdict(published.coverage),
        "swing_count": len(rows),
        "schedule_reason_counts": dict(Counter(reason for row in rows.values() for reason in row["schedule_reason_codes"])),
        "width_reason_counts": dict(Counter(reason for row in rows.values() for reason in row["width_reason_codes"])),
        "semantic_status": semantic.status.value,
        "semantic_reason_codes": semantic.reason_codes,
        "structural_enumeration_complete": None if record is None else record.structural_enumeration_complete,
        "physical_opening_universe_complete": None if record is None else record.physical_opening_universe_complete,
        "residual_source_observation_count": None if record is None else len(record.residual_visible_observation_ids),
        "swing_rows": rows,
    }, indent=2, sort_keys=True, default=lambda v: v.value))


if __name__ == "__main__":
    main()
