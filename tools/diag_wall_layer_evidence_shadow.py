"""Counts-only diagnostic for the SHADOW typed wall-layer evidence (``pb_wall_layer_evidence_shadow``). Read-only: no verdict changes.

  --pdf P --ocg-census          how many optional-content layers the document declares and how many the shadow rule reads as wall layers
  --pdf P --page-id N           compose the wall/opening chain for one page and report the layer atoms, the opposing candidates, and what
                                the layers say about the wall-pair classifications the resolver left AMBIGUOUS
  --pdf P --page-id N --opening-layers
                                additionally type each candidate OPENING by the layers of its own source primitives and cross-tabulate it
                                against its host-binding first gate (a precision signal: it never creates or rescues an opening)

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
    classify_opening_layers,
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


def page_report(pdf_path: Path, page_id: str, *, opening_layers: bool = False) -> dict:
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
    # The producer's published snapshot advances during composition; selectors must name the CURRENT one.
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    scope = next(iter(composition.physical_wall_candidate_authority._scopes.values()))
    evidence = build_wall_layer_evidence(scope.source_metadata_table)
    classes = Counter()
    relations = Counter()
    for left, right, classification in scope.equivalence.pair_classifications:
        classes[classification] += 1
        if classification == "ambiguous_physical_equivalence":
            relations[pair_layer_relation(evidence, left, right)] += 1
    opening_table = None
    if opening_layers:
        opening_table = _opening_layer_table(source, published, composition, evidence.page_uses_explicit_wall_layers, raw, page_id)
    return {
        "opening_layers_by_host_gate": opening_table,
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


def _host_gate(reason_codes) -> str:
    reasons = set(reason_codes)
    for code, label in (
        ("opening_host_binding_resolved", "host resolved"),
        ("no_authenticated_host_wall_band", "no wall band"),
        ("no_local_host_wall_candidates", "no local wall candidate"),
        ("multiple_authenticated_host_wall_bands", "multiple bands"),
        ("ambiguous_physical_wall_equivalence_for_host", "ambiguous wall equivalence"),
    ):
        if code in reasons:
            return label
    return "other"


def _opening_layer_table(source, published, composition, page_uses_wall_layers: bool, raw: bytes, page_id: str) -> dict:
    """Layer atom of each candidate opening, from the lineage-root primitives the existence proof owns (read-only)."""
    from pb_source_observation_authority import ObservationSelector
    from pb_vector_geometry_v130 import extract_native_page

    native = extract_native_page(fitz.open(stream=raw, filetype="pdf")[int(page_id) - 1])
    layer_by_segment = {str(s.get("id")): (s.get("layer") or "") for s in native.get("segments") or ()}
    store = source._producer._store
    observations = {}
    for (_snapshot_id, observation_id), observation in store.observations.items():
        observations.setdefault(observation_id, observation)

    def layer_of(observation_id, depth=0):
        observation = observations.get(observation_id)
        if observation is None or depth > 4:
            return None
        ref = str(observation.source_primitive_ref or "")
        if ref.startswith("segment:") and ref[8:] in layer_by_segment:
            return layer_by_segment[ref[8:]]
        for parent in observation.derivation_parent_ids or ():
            found = layer_of(parent, depth + 1)
            if found is not None:
                return found
        return None

    physical = composition.physical_opening_authority
    table: dict[str, Counter] = {}
    unresolved = lookups = 0
    for trace in composition.opening_bindings:
        selector = ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id)
        record = physical.prove_existence(selector).existence_record
        if record is None:
            table.setdefault(_host_gate(trace.reason_codes), Counter())["existence record unavailable"] += 1
            continue
        roots = tuple(record.source_lineage_root_ids) or tuple(record.source_observation_ids)
        layers = [layer_of(oid) for oid in roots]
        lookups += len(layers)
        unresolved += sum(1 for value in layers if value is None)
        atom = classify_opening_layers(layers, page_uses_explicit_wall_layers=page_uses_wall_layers)
        label = atom.kind + (" (opposing)" if atom.opposing else "")
        table.setdefault(_host_gate(trace.reason_codes), Counter())[label] += 1
    return {
        "unresolved_primitive_lookups": unresolved,
        "primitive_lookups": lookups,
        "by_host_gate": {gate: dict(sorted(row.items())) for gate, row in sorted(table.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page-id")
    parser.add_argument("--ocg-census", action="store_true")
    parser.add_argument("--opening-layers", action="store_true")
    args = parser.parse_args()
    if args.ocg_census == bool(args.page_id):
        parser.error("choose exactly one of --ocg-census or --page-id")
    if args.opening_layers and not args.page_id:
        parser.error("--opening-layers needs --page-id")
    result = ocg_census(args.pdf) if args.ocg_census else page_report(args.pdf, args.page_id, opening_layers=args.opening_layers)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
