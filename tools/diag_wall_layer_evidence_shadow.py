"""Counts-only diagnostic for the SHADOW typed wall-layer evidence (``pb_wall_layer_evidence_shadow``). Read-only: no verdict changes.

  --pdf P --ocg-census          how many optional-content layers the document declares and how many the shadow rule reads as wall layers
  --pdf P --page-id N           compose the wall/opening chain for one page and report the layer atoms, the opposing candidates, and what
                                the layers say about the wall-pair classifications the resolver left AMBIGUOUS

No layer name is printed, only counts. Nothing here is imported by a live path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import fitz

from pb_wall_layer_evidence_shadow import (
    build_wall_layer_evidence,
    is_explicit_wall_layer_name,
    pair_layer_relation,
)


def ocg_census(pdf_path: Path) -> dict:
    doc = fitz.open(pdf_path)
    try:
        ocgs = doc.get_ocgs() or {}
        names = [str(entry.get("name") or "") for entry in ocgs.values()]
        return {
            "pages": doc.page_count,
            "optional_content_layers": len(names),
            "explicit_wall_layer_names": sum(1 for name in names if is_explicit_wall_layer_name(name)),
        }
    finally:
        doc.close()


def page_report(pdf_path: Path, page_id: str) -> dict:
    from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer

    raw = pdf_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=raw, source_locator="memory://wall-layer-shadow.pdf", page_ids=(page_id,))
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id, page_ids=(page_id,))
    scope = next(iter(composition.physical_wall_candidate_authority._scopes.values()))
    evidence = build_wall_layer_evidence(scope.source_metadata_table)
    classes = Counter()
    relations = Counter()
    for left, right, classification in scope.equivalence.pair_classifications:
        classes[classification] += 1
        if classification == "ambiguous_physical_equivalence":
            relations[pair_layer_relation(evidence, left, right)] += 1
    return {
        "source_sha256_prefix": sha[:8],
        "page_id": str(page_id),
        "wall_candidates": len(scope.records),
        "atoms_by_kind": evidence.counts(),
        "explicit_wall_layer_names_on_page": len(evidence.explicit_wall_layer_values),
        "page_uses_explicit_wall_layers": evidence.page_uses_explicit_wall_layers,
        "opposing_candidates": len(evidence.opposing_candidate_ids),
        "pair_classifications": dict(sorted(classes.items())),
        "ambiguous_pairs_by_layer_relation": dict(sorted(relations.items())),
        "shadow_only": evidence.shadow_only,
        "live_effect": evidence.live_effect,
        "grants_authority": evidence.grants_authority,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page-id")
    parser.add_argument("--ocg-census", action="store_true")
    args = parser.parse_args()
    if args.ocg_census == bool(args.page_id):
        parser.error("choose exactly one of --ocg-census or --page-id")
    result = ocg_census(args.pdf) if args.ocg_census else page_report(args.pdf, args.page_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
