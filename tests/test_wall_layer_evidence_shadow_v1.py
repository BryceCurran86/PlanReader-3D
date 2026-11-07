"""Typed source-layer evidence for wall candidates: SHADOW only, descriptive-to-typed, no live consumer.

The atoms read ONLY the producer-owned source-metadata table that the wall authority already publishes (layer values, their status and the
lineage counts). They never read geometry, a project, a file name, a page number or an expected value; no translation / rotation / scale
test applies because no geometry is consumed. Synthetic descriptors only.
"""
from __future__ import annotations

import random
from dataclasses import asdict, replace

import pytest

from pb_physical_wall_source_metadata_shadow import (
    SOURCE_METADATA_DESCRIBED,
    PhysicalWallSourceMetadataDescriptor,
    PhysicalWallSourceMetadataScopeTable,
    unavailable_physical_wall_source_metadata_scope_table,
)
from pb_wall_layer_evidence_shadow import (
    ATOM_EXPLICIT_WALL_LAYER,
    ATOM_MIXED_LAYERS,
    ATOM_NO_LAYER,
    ATOM_OTHER_SINGLE_LAYER,
    RELATION_DIFFERENT_WALL_LAYERS,
    RELATION_NOT_ATTESTED,
    RELATION_SAME_WALL_LAYER,
    RELATION_WALL_VERSUS_OTHER_LAYER,
    build_wall_layer_evidence,
    pair_layer_relation,
)


def _descriptor(wall_id: str, layers=("Enclosure_WallExternal",), *, status: str = "agreed", records: int = 3,
                layer_present=None, missing=()) -> PhysicalWallSourceMetadataDescriptor:
    return PhysicalWallSourceMetadataDescriptor(
        wall_candidate_id=wall_id, source_primitive_ids=tuple(f"{wall_id}-p{i}" for i in range(records)),
        matched_source_primitive_ids=tuple(f"{wall_id}-p{i}" for i in range(records)),
        missing_source_primitive_ids=tuple(missing), source_record_count=records,
        width_status="agreed", width_values_pt=(0.5,), drawing_relative_width_ranks=(), width_present_source_record_count=records,
        stroke_status="agreed", stroke_values=("0",), stroke_present_source_record_count=records,
        fill_status="unknown", fill_values=(), fill_present_source_record_count=0,
        layer_status=status, layer_values=tuple(layers),
        wall_named_layer_values=tuple(v for v in layers if "wall" in v.lower()),
        layer_present_source_record_count=records if layer_present is None else layer_present,
        dashes_status="unknown", dashes_values=(), dashes_present_source_record_count=0,
    )


def _table(*descriptors) -> PhysicalWallSourceMetadataScopeTable:
    return PhysicalWallSourceMetadataScopeTable(
        status=SOURCE_METADATA_DESCRIBED, reason_code=None, page_id="3", decision_scope_id="wall-source:page-3",
        source_segment_count=100, candidate_count=len(descriptors), distinct_widths_pt=(0.5,), distinct_stroke_values=("0",),
        distinct_fill_values=(), distinct_layer_values=tuple(sorted({v for d in descriptors for v in d.layer_values})),
        wall_named_layer_values=(), distinct_dashes_values=(), descriptors=tuple(descriptors),
    )


def _kinds(table):
    return {wall_id: atom.kind for wall_id, atom in build_wall_layer_evidence(table).atoms.items()}


# ---------------------------------------------------------------- classification of one candidate
def test_a_candidate_entirely_in_one_wall_named_layer_is_an_explicit_wall_layer_atom():
    evidence = build_wall_layer_evidence(_table(_descriptor("w1")))
    atom = evidence.atoms["w1"]
    assert atom.kind == ATOM_EXPLICIT_WALL_LAYER and atom.layer_value == "Enclosure_WallExternal"
    assert evidence.page_uses_explicit_wall_layers is True and evidence.explicit_wall_layer_values == ("Enclosure_WallExternal",)


@pytest.mark.parametrize("layer", ["A-WALL-FULL", "WALLS", "wall", "Structure_Wall_Internal"])
def test_the_wall_name_convention_is_case_insensitive_and_literal(layer):
    assert _kinds(_table(_descriptor("w1", (layer,))))["w1"] == ATOM_EXPLICIT_WALL_LAYER


@pytest.mark.parametrize("layer", ["Finish_WallTile", "FINISH-WALL", "Wall_Lining", "A-WALL-CLADDING", "Wall.Paint", "Tiling_Wall"])
def test_a_finish_or_lining_layer_is_not_an_explicit_wall_layer_even_if_it_says_wall(layer):
    assert _kinds(_table(_descriptor("w1", (layer,))))["w1"] == ATOM_OTHER_SINGLE_LAYER


@pytest.mark.parametrize("layer", ["Interior_Joinery", "Service_StormwaterGeneral", "Annotation_FloorPlan", "Enclosure_Roof"])
def test_a_single_agreed_layer_that_is_not_wall_named_is_an_other_single_layer_atom(layer):
    assert _kinds(_table(_descriptor("w1", (layer,))))["w1"] == ATOM_OTHER_SINGLE_LAYER


def test_a_candidate_spanning_layers_is_mixed_and_never_attested_either_way():
    kinds = _kinds(_table(
        _descriptor("a", ("Enclosure_WallExternal", "Interior_Joinery"), status="conflict"),
        _descriptor("b", ("Enclosure_WallExternal", "Enclosure_WallInternal"), status="agreed"),
    ))
    assert kinds == {"a": ATOM_MIXED_LAYERS, "b": ATOM_MIXED_LAYERS}


def test_a_conflict_status_is_mixed_even_if_only_one_value_is_listed():
    # An inconsistent descriptor must never be attested as an explicit wall layer.
    assert _kinds(_table(_descriptor("w1", ("Enclosure_WallExternal",), status="conflict")))["w1"] == ATOM_MIXED_LAYERS


@pytest.mark.parametrize("kwargs", [
    {"layers": (), "status": "unknown"},
    {"layers": ("Enclosure_WallExternal",), "status": "unknown"},
    {"layers": ("Enclosure_WallExternal",), "layer_present": 2},               # a record without a layer
    {"layers": ("Enclosure_WallExternal",), "missing": ("lost-primitive",)},   # lineage not fully matched
    {"layers": ("Enclosure_WallExternal",), "records": 0, "layer_present": 0},
])
def test_incomplete_layer_provenance_is_no_layer_not_a_guess(kwargs):
    assert _kinds(_table(_descriptor("w1", **kwargs)))["w1"] == ATOM_NO_LAYER


# ---------------------------------------------------------------- page level: opposition only when the page names wall layers
def test_a_page_with_no_wall_named_layer_produces_no_opposition_at_all():
    evidence = build_wall_layer_evidence(_table(_descriptor("a", ("Interior_Joinery",)), _descriptor("b", ("Annotation",))))
    assert evidence.page_uses_explicit_wall_layers is False
    assert evidence.opposing_candidate_ids == ()
    assert pair_layer_relation(evidence, "a", "b") == RELATION_NOT_ATTESTED


def test_on_a_page_that_names_wall_layers_other_single_layer_candidates_are_opposing_evidence_but_mixed_and_missing_are_not():
    evidence = build_wall_layer_evidence(_table(
        _descriptor("wall"), _descriptor("joinery", ("Interior_Joinery",)),
        _descriptor("mixed", ("Enclosure_WallExternal", "Interior_Joinery"), status="conflict"),
        _descriptor("none", (), status="unknown"),
    ))
    assert evidence.opposing_candidate_ids == ("joinery",)


# ---------------------------------------------------------------- pair relations
def test_pair_relations_are_typed_and_symmetric():
    evidence = build_wall_layer_evidence(_table(
        _descriptor("ext1", ("Enclosure_WallExternal",)), _descriptor("ext2", ("Enclosure_WallExternal",)),
        _descriptor("int1", ("Enclosure_WallInternal",)), _descriptor("join", ("Interior_Joinery",)),
        _descriptor("mix", ("Enclosure_WallExternal", "Interior_Joinery"), status="conflict"),
        _descriptor("none", (), status="unknown"),
    ))
    expected = {
        ("ext1", "ext2"): RELATION_SAME_WALL_LAYER,
        ("ext1", "int1"): RELATION_DIFFERENT_WALL_LAYERS,
        ("ext1", "join"): RELATION_WALL_VERSUS_OTHER_LAYER,
        ("ext1", "mix"): RELATION_NOT_ATTESTED,
        ("ext1", "none"): RELATION_NOT_ATTESTED,
        ("join", "mix"): RELATION_NOT_ATTESTED,
        ("ext1", "unknown-id"): RELATION_NOT_ATTESTED,
    }
    for (left, right), relation in expected.items():
        assert pair_layer_relation(evidence, left, right) == relation
        assert pair_layer_relation(evidence, right, left) == relation
    assert pair_layer_relation(evidence, "ext1", "ext1") == RELATION_NOT_ATTESTED          # a candidate is not a pair with itself


# ---------------------------------------------------------------- invariance, purity, typing
def test_the_result_does_not_depend_on_descriptor_order_and_is_deterministic():
    descriptors = [_descriptor(f"w{i}", (("Enclosure_WallExternal", "Interior_Joinery", "Enclosure_WallInternal")[i % 3],)) for i in range(9)]
    reference = build_wall_layer_evidence(_table(*descriptors))
    for seed in range(6):
        shuffled = list(descriptors)
        random.Random(seed).shuffle(shuffled)
        again = build_wall_layer_evidence(_table(*shuffled))
        assert again == reference and list(again.atoms) == sorted(again.atoms)
    assert build_wall_layer_evidence(_table(*descriptors)) == reference


def test_inputs_are_not_mutated():
    table = _table(_descriptor("a"), _descriptor("b", ("Interior_Joinery",)))
    before = asdict(table)
    build_wall_layer_evidence(table)
    assert asdict(table) == before


def test_every_result_is_shadow_only_and_grants_nothing():
    evidence = build_wall_layer_evidence(_table(_descriptor("a")))
    assert evidence.shadow_only is True and evidence.live_effect is False and evidence.grants_authority is False


def test_an_unavailable_table_gives_empty_evidence_with_its_reason():
    evidence = build_wall_layer_evidence(unavailable_physical_wall_source_metadata_scope_table(
        page_id="3", decision_scope_id="s", reason_code="metadata_unavailable"))
    assert evidence.atoms == {} and evidence.page_uses_explicit_wall_layers is False and evidence.unavailable_reason == "metadata_unavailable"


def test_wrong_types_and_duplicate_candidates_are_refused():
    with pytest.raises(TypeError):
        build_wall_layer_evidence({"descriptors": []})
    with pytest.raises(ValueError):
        build_wall_layer_evidence(_table(_descriptor("a"), replace(_descriptor("a"), source_record_count=4)))
