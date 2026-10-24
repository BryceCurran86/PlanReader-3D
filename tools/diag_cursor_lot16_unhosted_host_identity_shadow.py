"""Original Lot16: host-identity shadow on G17-unhosted openings (mission 2/5).

Uses exact W4 ancestry candidates only. Never nearest-elects or grants host.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_unhosted_host_identity_original_attach import (
    attach_host_identity_to_unhosted_ancestry,
)
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_raster_unhosted_flank_source import (
    audit_g17_unhosted_flank_original_ancestry,
)

LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def lot16_unhosted_host_identity_shadow_report(
    pdf: bytes, *, expected_sha256: str = LOT16_SHA,
) -> dict:
    if type(pdf) is not bytes or not pdf:
        raise TypeError("original PDF bytes required")
    digest = sha256(pdf).hexdigest()
    if digest != expected_sha256:
        raise ValueError("original Lot16 source SHA mismatch")

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    pub = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=pdf,
        source_locator="memory://cursor-lot16-host-identity.pdf",
        page_ids=(3,),
    )
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=pub.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source, wall_opening_composition=comp)
    published = source.published_snapshot_for_revision(pub.revision.revision_id)
    before = _retention(comp, voids, verify_customer_rows=True)
    ancestry = audit_g17_unhosted_flank_original_ancestry(source, published, comp)

    pair_rows: list[tuple[str, str, str]] = []
    for scope in before["walls"]:
        equivalence = scope.get("equivalence") or {}
        for row in equivalence.get("pair_classifications") or ():
            if len(row) == 3:
                pair_rows.append((str(row[0]), str(row[1]), str(row[2])))

    attach = attach_host_identity_to_unhosted_ancestry(
        ancestry, pair_classifications=pair_rows,
    )
    quantity_ids = {str(q["quantity_id"]) for q in before.get("quantities") or ()}
    return {
        "status": "UNPUBLISHED_LOT16_UNHOSTED_HOST_IDENTITY_SHADOW",
        "source_sha256": digest,
        "page_id": PAGE_ID,
        "unhosted_g17_flank_opening_count": len(ancestry),
        "signed_quantity_count": len(quantity_ids),
        "signed_eight_retained": len(quantity_ids) == 8,
        "host_identity_attach": {
            "status": attach["status"],
            "unhosted_opening_count": attach["unhosted_opening_count"],
            "disposition_counts": attach["disposition_counts"],
            "openings": [
                {
                    "physical_opening_id": row["physical_opening_id"],
                    "exact_source_w4_candidate_count": row[
                        "exact_source_w4_candidate_count"],
                    "disposition": row["host_identity_shadow"]["disposition"],
                    "retained_candidate_count": row["host_identity_shadow"][
                        "retained_candidate_count"],
                    "elected_host_wall_id": None,
                    "host_granted": False,
                }
                for row in attach["openings"]
            ],
        },
        "host_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha256", default=LOT16_SHA)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    raw = args.pdf.read_bytes()
    if sha256(raw).hexdigest() != args.sha256:
        raise SystemExit("source SHA mismatch")
    report = lot16_unhosted_host_identity_shadow_report(
        raw, expected_sha256=args.sha256)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "unhosted_g17_flank_opening_count": report["unhosted_g17_flank_opening_count"],
        "disposition_counts": report["host_identity_attach"]["disposition_counts"],
        "signed_eight_retained": report["signed_eight_retained"],
        "host_granted": False,
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
