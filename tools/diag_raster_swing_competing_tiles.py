from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_DOOR_SWING_AMBIGUOUS,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


ROOT = Path("documents/sources")
LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def _page_registration_factors(page) -> tuple[tuple[float, float], ...]:
    factors = []
    for image in page.get_images(full=True) or ():
        if len(image) < 4:
            continue
        try:
            xref = int(image[0])
            pixel_width = int(image[2])
            pixel_height = int(image[3])
        except (TypeError, ValueError):
            continue
        if pixel_width <= 0 or pixel_height <= 0:
            continue
        try:
            rects = page.get_image_rects(xref) or ()
        except Exception:
            continue
        for rect in rects:
            sx = (float(rect.x1) - float(rect.x0)) / float(pixel_width)
            sy = (float(rect.y1) - float(rect.y0)) / float(pixel_height)
            if (
                not math.isfinite(sx)
                or not math.isfinite(sy)
                or sx <= 0.0
                or sy <= 0.0
            ):
                continue
            ref = math.sqrt(sx * sy)
            factors.append((sx / ref, sy / ref))
    return tuple(factors)


def _page_needs_fallback(page) -> bool:
    factors = _page_registration_factors(page)
    if not factors:
        return False
    x0, y0 = factors[0]
    return any(
        not (
            math.isclose(x, x0, rel_tol=1e-4, abs_tol=1e-6)
            and math.isclose(y, y0, rel_tol=1e-4, abs_tol=1e-6)
        )
        for x, y in factors[1:]
    )


def scan_pdf(path: Path) -> dict:
    source_bytes = path.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        fallback_page_ids = tuple(
            str(i + 1)
            for i in range(doc.page_count)
            if _page_needs_fallback(doc.load_page(i))
        )

    if not fallback_page_ids:
        return {
            "path": path.as_posix(),
            "source_sha256": source_sha,
            "fallback_page_ids": [],
            "primitive_count": 0,
            "framed_count": 0,
            "swing_count": 0,
            "swing_ambiguous_support_count": 0,
            "pages": {},
        }

    producer = SourceVisibilityProducer(
        producer_method="diag_raster_swing_competing_tiles",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=f"diag:{path.as_posix()}",
        source_bytes=source_bytes,
        source_locator=str(path),
        page_ids=fallback_page_ids,
    )
    # Every selected page must really take the fallback path in production.
    unexpected_registered = {
        page_id: producer.raster_opening_registration_scale(
            published.revision.revision_id,
            page_id,
        )
        for page_id in fallback_page_ids
        if producer.raster_opening_registration_scale(
            published.revision.revision_id,
            page_id,
        ) is not None
    }
    if unexpected_registered:
        raise SystemExit(
            f"direct fallback classification disagrees with producer: {unexpected_registered}"
        )

    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=fallback_page_ids,
    )
    authority = producer.physical_opening_authority()

    unique_records = {}
    conflicts = Counter()
    for observation_id in published.raster_opening_primitive_observation_ids:
        result = authority.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            unique_records[result.existence_record.record_id] = result.existence_record
        elif (
            result.status is EvidenceResolutionStatus.CONFLICT
            and RASTER_DOOR_SWING_AMBIGUOUS in result.reason_codes
            and result.source_observation is not None
            and result.source_observation.observation is not None
        ):
            conflicts[str(result.source_observation.observation.page_id)] += 1

    by_page = defaultdict(Counter)
    for record in unique_records.values():
        by_page[str(record.page_id)][record.structural_pattern] += 1

    page_rows = {}
    for page_id in fallback_page_ids:
        page_rows[page_id] = {
            "framed_count": int(
                by_page[page_id][RASTER_FRAMED_WALL_BAND_INTERRUPTION]
            ),
            "swing_count": int(
                by_page[page_id][RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION]
            ),
            "swing_ambiguous_support_count": int(conflicts[page_id]),
        }

    return {
        "path": path.as_posix(),
        "source_sha256": source_sha,
        "fallback_page_ids": list(fallback_page_ids),
        "primitive_count": len(published.raster_opening_primitive_observation_ids),
        "framed_count": sum(row["framed_count"] for row in page_rows.values()),
        "swing_count": sum(row["swing_count"] for row in page_rows.values()),
        "swing_ambiguous_support_count": sum(
            row["swing_ambiguous_support_count"] for row in page_rows.values()
        ),
        "pages": page_rows,
    }


def main() -> None:
    rows = [scan_pdf(path) for path in sorted(ROOT.rglob("*.pdf"))]
    lot16 = [row for row in rows if row["source_sha256"] == LOT16_SHA]
    if len(lot16) != 1:
        raise SystemExit("exact Lot16 source not found once")
    lot16_row = lot16[0]

    payload = {
        "rows": rows,
        "lot16": lot16_row,
        "non_lot16_swing_positives": [
            {
                "path": row["path"],
                "source_sha256": row["source_sha256"],
                "fallback_page_ids": row["fallback_page_ids"],
                "swing_count": row["swing_count"],
                "pages": {
                    page_id: page
                    for page_id, page in row["pages"].items()
                    if page["swing_count"]
                },
            }
            for row in rows
            if row["source_sha256"] != LOT16_SHA and row["swing_count"]
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    page3 = lot16_row["pages"].get("3")
    if page3 is None:
        raise SystemExit("Lot16 page 3 is not exercising competing-transform fallback")
    if int(page3["framed_count"]) != 14:
        raise SystemExit(
            f"Lot16 fallback framed regression: {page3['framed_count']}"
        )
    if int(page3["swing_count"]) != 0:
        raise SystemExit(
            f"Lot16 fallback manufactured swing positives: {page3['swing_count']}"
        )
    if payload["non_lot16_swing_positives"]:
        raise SystemExit(
            "competing-transform fallback produced non-Lot16 swing positives"
        )


if __name__ == "__main__":
    main()
