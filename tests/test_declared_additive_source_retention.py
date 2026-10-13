"""Declared additive-source retention: explicit, single-event, fail-closed.

The default strict comparators must stay strict.  A declaration may only
approve the one (SHA, baseline snapshot, candidate snapshot) event it names, and
only when the snapshot-independent physical proposition behind every prior host
and frame is unchanged.
"""
from copy import deepcopy
from hashlib import sha256
import json
import random

import pytest

from scripts.gptmax_source_opposition_retention import compare_opposed_source_reports
from tools.gptmax_compare_source_face_retention import compare_source_face_reports
from tools.declared_additive_source_retention import (
    DECLARATION_SCHEMA,
    DEFAULT_DECLARATIONS_PATH,
    approve_declared_additive_rekeys,
    as_ledger_report,
    load_declarations,
    parse_declaration,
    parse_declarations,
)

PDF_BYTES = b"synthetic immutable source bytes"
SHA = sha256(PDF_BYTES).hexdigest()
A, B, T, U = (f"physical_opening_existence_{c}" for c in ("a", "b", "t", "u"))
BASE_SNAP, NEW_SNAP = "snapshot_old", "snapshot_new"


def _wall(wid, y, ordinal):
    prim = f"raster_segment:source:1.0.0:{y}"
    return {
        "wall_candidate_id": wid,
        "physical_identity": {
            "candidate_identity_id": f"wall2_{wid}",
            "status": "corroborated",
            "blocking_reasons": [],
            "source_primitive_ids": [prim],
            "path_fingerprint": [[10.0, y], [70.0, y]],
            "edge_ids": [f"split_{ordinal}"],
        },
        "wall_candidate": {
            "centerline_pts": [[10.0, y], [70.0, y]],
            "reason_codes": ["source_proven"],
            "representation": "single_line",
            "status": "candidate",
            "end_node_ids": [f"node_{ordinal}_a", f"node_{ordinal}_b"],
            "face_a_segment_ids": [f"split_{ordinal}"],
        },
        "source_edge_fragments": [
            {
                "edge_id": f"split_{ordinal}",
                "geometry": [10.0, y, 70.0, y],
                "source_primitive_ids": [prim],
            }
        ],
    }


def _binding(oid, snap, host=None, members=(), status="corroborated", reasons=()):
    return {
        "opening_identity_id": oid,
        "page_id": "3",
        "status": status,
        "host_wall_id": f"group_{snap}_{oid}" if host else None,
        "record_id": f"host_{snap}_{oid}" if host else None,
        "member_wall_candidate_ids": list(members),
        "representative_observation_id": f"obs_{oid}",
        "reason_codes": list(reasons),
    }


def _frame_row(oid, snap, framed):
    if not framed:
        return {
            "opening_identity_id": oid,
            "host_wall_id": None,
            "record_id": None,
            "reason_codes": ["opening_host_frame_host_unavailable"],
        }
    return {
        "opening_identity_id": oid,
        "host_wall_id": f"group_{snap}_{oid}",
        "record_id": f"frame_{snap}_{oid}",
        "reason_codes": ["opening_host_frame_resolved"],
        "whole_wall_candidate_ids": [f"wall_{oid}"],
    }


def _frame_evidence(oid, snap):
    return {
        "opening_identity_id": oid,
        "record_id": f"frame_{snap}_{oid}",
        "whole_wall_frame_id": f"frame_id_{snap}_{oid}",
        "host_wall_id": f"group_{snap}_{oid}",
        "host_binding_record_id": f"host_{snap}_{oid}",
        "selector": {
            "snapshot_id": snap,
            "opening_identity_id": oid,
            "page_id": "3",
            "source_sha256": SHA,
        },
        "origin_pt": [10.0, 10.0],
        "axis_unit": [1.0, 0.0],
        "normal_unit": [0.0, 1.0],
        "whole_wall_length_pt": 60.0,
        "whole_wall_candidate_ids": [f"wall_{oid}"],
        "wall_thickness_pt": 4.0,
        "u0_pt": 0.0,
        "u1_pt": 60.0,
    }


UNMAPPED_LEFT = ["no_authenticated_host_wall_band", "raster_source_band_left_source_primitive_unmapped"]
UNMAPPED_RIGHT = ["no_authenticated_host_wall_band", "raster_source_band_right_source_primitive_unmapped"]


def report(snap, *, ordinal_shift=0, t_hosted=False, u_reasons=UNMAPPED_LEFT):
    """A hosted+framed A, hosted/unframed B, target T, unrelated unhosted U."""
    walls = [
        _wall("wall_" + A, 10.0, 100 + ordinal_shift),
        _wall("wall_" + B, 30.0, 200 + ordinal_shift),
    ]
    bindings = [
        _binding(A, snap, host=True, members=["wall_" + A], reasons=["opening_host_binding_resolved"]),
        _binding(B, snap, host=True, members=["wall_" + B], reasons=["opening_host_binding_resolved"]),
        _binding(U, snap, status="abstained", reasons=u_reasons),
    ]
    frames = [_frame_row(A, snap, True), _frame_row(B, snap, False), _frame_row(U, snap, False)]
    if t_hosted:
        walls.append(_wall("wall_" + T, 50.0, 300 + ordinal_shift))
        bindings.append(_binding(T, snap, host=True, members=["wall_" + T],
                                 reasons=["opening_host_binding_resolved", "raster_source_band_host_resolved"]))
        frames.append(_frame_row(T, snap, False))
    else:
        bindings.append(_binding(T, snap, status="abstained", reasons=UNMAPPED_LEFT))
        frames.append(_frame_row(T, snap, False))
    return {
        "source_sha256": SHA,
        "snapshot_id": snap,
        "selected_geometry_page_ids": ["3"],
        "primitive_safety_cap": 20_000,
        "opening_bindings": bindings,
        "host_frames": frames,
        "resolved_host_frame_evidence": [_frame_evidence(A, snap)],
        "source_owned_wall_scope_results": [
            {
                "source_sha256": SHA,
                "page_id": "3",
                "status": "corroborated",
                "scope_complete": True,
                "records": walls,
            }
        ],
    }


def event():
    return report(BASE_SNAP), report(NEW_SNAP, ordinal_shift=7, t_hosted=True, u_reasons=UNMAPPED_RIGHT)


def declaration_raw(**overrides):
    raw = {
        "source_sha256": SHA,
        "report_shape": "stage_report",
        "baseline_snapshot_id": BASE_SNAP,
        "candidate_snapshot_id": NEW_SNAP,
        "expected_new_host_ids": [T],
        "expected_new_frame_host_ids": [],
        "expected_unhosted_reason_changes": [
            {"opening_identity_id": U, "before": UNMAPPED_LEFT, "after": UNMAPPED_RIGHT}
        ],
        "expected_id_churn_report_keys": [],
        "expected_changed_report_keys": [
            "snapshot_id", "opening_bindings", "host_frames",
            "resolved_host_frame_evidence", "source_owned_wall_scope_results",
        ],
        "allow_snapshot_receipt_rekey": True,
        "tracking_issue": 2608,
    }
    raw.update(overrides)
    return raw


def declared(**overrides):
    return (parse_declaration(declaration_raw(**overrides)),)


# --------------------------------------------------------------------------
# Strict by default
# --------------------------------------------------------------------------

def test_committed_declarations_are_well_formed_and_strict_by_default():
    assert DEFAULT_DECLARATIONS_PATH.exists()
    parsed = load_declarations()
    assert parsed == parse_declarations(json.loads(DEFAULT_DECLARATIONS_PATH.read_text()))
    # No reviewed additive-source event may be silently live on a clean tree.
    assert all(d.tracking_issue > 0 for d in parsed)


def test_without_a_declaration_the_same_event_still_fails_every_strict_gate():
    base, cand = event()
    assert approve_declared_additive_rekeys(base, cand, ()) is None
    strict = compare_source_face_reports(base, cand, declarations=())
    assert strict["retention_pass"] is False
    assert {r["physical_opening_id"] for r in strict["changed_proof_records_needing_review"]} == {A, B}
    assert "declared_additive_source_retention" not in strict
    with pytest.raises(ValueError, match="binding changed"):
        compare_opposed_source_reports(base, cand, source_bytes=PDF_BYTES, declarations=())


def test_exact_unchanged_report_never_needs_a_declaration():
    base = report(BASE_SNAP)
    assert compare_source_face_reports(base, deepcopy(base), declarations=())["retention_pass"]
    assert compare_opposed_source_reports(base, deepcopy(base), source_bytes=PDF_BYTES, declarations=())["retention_pass"]


# --------------------------------------------------------------------------
# Positive: exactly the declared event
# --------------------------------------------------------------------------

def test_declared_event_is_approved_and_grants_nothing():
    base, cand = event()
    snapshot = deepcopy((base, cand))
    approval = approve_declared_additive_rekeys(base, cand, declared())
    assert approval["declaration_applied"] is True
    assert approval["rekeyed_host_ids"] == sorted([A, B])
    assert approval["exact_retained_host_ids"] == []
    assert approval["declared_new_host_ids"] == [T]
    assert approval["accepted_unhosted_reason_change_ids"] == [U]
    assert approval["official_host_receipt_identity_acceptance"] is False
    assert approval["host_publication_allowed"] is False
    assert approval["opening_count_or_metric_publication_allowed"] is False
    assert approval["benchmark_accuracy"] is None
    assert (base, cand) == snapshot  # no mutation
    assert approve_declared_additive_rekeys(base, cand, declared()) == approval  # deterministic


def test_declared_event_passes_both_comparators_and_records_what_it_accepted():
    base, cand = event()
    face = compare_source_face_reports(base, cand, declarations=declared())
    assert face["retention_pass"] is True
    assert {r["physical_opening_id"] for r in face["declared_rekeys_accepted"]} == {A, B}
    assert face["changed_proof_records_needing_review"] == []
    assert [r["physical_opening_id"] for r in face["new_proof_records"]] == [T]
    assert face["quantity_publication_permitted"] is False
    opposed = compare_opposed_source_reports(base, cand, source_bytes=PDF_BYTES, declarations=declared())
    assert opposed["retention_pass"] is True
    assert opposed["host_publication_allowed"] is False
    assert opposed["declared_additive_source_retention"]["declared_new_host_ids"] == [T]


def test_stage_tool_report_shape_is_viewed_without_mutation():
    base, cand = event()
    stage_base, stage_cand = deepcopy(base), deepcopy(cand)
    for stage in (stage_base, stage_cand):
        stage["host_frame_traces"] = stage.pop("host_frames")
        stage["source_owned_wall_scopes"] = stage.pop("source_owned_wall_scope_results")
    frozen = deepcopy((stage_base, stage_cand))
    assert "host_frames" in as_ledger_report(stage_base)
    stage_declaration = declared(expected_changed_report_keys=[
        "snapshot_id", "opening_bindings", "host_frame_traces",
        "resolved_host_frame_evidence", "source_owned_wall_scopes",
    ])
    assert approve_declared_additive_rekeys(stage_base, stage_cand, stage_declaration)["rekeyed_host_ids"] == sorted([A, B])
    assert (stage_base, stage_cand) == frozen


def test_input_order_and_unrelated_content_do_not_change_the_decision():
    base, cand = event()
    expected = approve_declared_additive_rekeys(base, cand, declared())
    rng = random.Random(7)
    for _ in range(5):
        b2, c2 = deepcopy(base), deepcopy(cand)
        for rep in (b2, c2):
            rng.shuffle(rep["opening_bindings"])
            rng.shuffle(rep["host_frames"])
            rng.shuffle(rep["source_owned_wall_scope_results"][0]["records"])
        assert approve_declared_additive_rekeys(b2, c2, declared()) == expected
    extra = "physical_opening_existence_extra"
    for rep in (base, cand):
        rep["opening_bindings"].append(_binding(extra, rep["snapshot_id"], status="abstained", reasons=UNMAPPED_LEFT))
        rep["host_frames"].append(_frame_row(extra, rep["snapshot_id"], False))
    assert approve_declared_additive_rekeys(base, cand, declared())["rekeyed_host_ids"] == sorted([A, B])


def test_uniform_translation_of_source_geometry_is_invariant():
    base, cand = event()
    for rep in (base, cand):
        for record in rep["source_owned_wall_scope_results"][0]["records"]:
            dx, dy = 123.5, -40.25
            for fragment in record["source_edge_fragments"]:
                g = fragment["geometry"]
                fragment["geometry"] = [g[0] + dx, g[1] + dy, g[2] + dx, g[3] + dy]
            record["physical_identity"]["path_fingerprint"] = [
                [x + dx, y + dy] for x, y in record["physical_identity"]["path_fingerprint"]
            ]
            record["wall_candidate"]["centerline_pts"] = [
                [x + dx, y + dy] for x, y in record["wall_candidate"]["centerline_pts"]
            ]
    assert approve_declared_additive_rekeys(base, cand, declared())["declared_new_host_ids"] == [T]


# --------------------------------------------------------------------------
# The declaration is bound to exactly one event
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "override",
    [
        {"source_sha256": "f" * 64},
        {"baseline_snapshot_id": "snapshot_other"},
        {"candidate_snapshot_id": "snapshot_other"},
    ],
)
def test_declaration_for_any_other_event_is_ignored_not_applied(override):
    base, cand = event()
    assert approve_declared_additive_rekeys(base, cand, declared(**override)) is None
    assert compare_source_face_reports(base, cand, declarations=declared(**override))["retention_pass"] is False


def test_declaration_is_single_use_after_the_candidate_becomes_the_baseline():
    _, cand = event()
    later = deepcopy(cand)
    later["snapshot_id"] = "snapshot_next"
    for row in later["opening_bindings"]:
        if row["host_wall_id"]:
            row["host_wall_id"] += "_next"
            row["record_id"] += "_next"
    assert approve_declared_additive_rekeys(cand, later, declared()) is None


def test_mismatched_candidate_source_sha_is_not_approved():
    base, cand = event()
    cand["source_sha256"] = "e" * 64
    assert approve_declared_additive_rekeys(base, cand, declared()) is None


# --------------------------------------------------------------------------
# Every physical / authority change still fails, even when declared
# --------------------------------------------------------------------------

def _walls(rep):
    return {r["wall_candidate_id"]: r for r in rep["source_owned_wall_scope_results"][0]["records"]}


def _damage(name, base, cand):
    wall = _walls(cand)["wall_" + A]
    binding = {r["opening_identity_id"]: r for r in cand["opening_bindings"]}
    frame = {r["opening_identity_id"]: r for r in cand["host_frames"]}
    if name == "fragment_geometry":
        wall["source_edge_fragments"][0]["geometry"][2] += 0.1
    elif name == "centerline":
        wall["wall_candidate"]["centerline_pts"][1][0] += 0.1
        wall["physical_identity"]["path_fingerprint"][1][0] += 0.1
    elif name == "source_primitive":
        wall["physical_identity"]["source_primitive_ids"] = ["raster_segment:other:1.0.0:1"]
        wall["source_edge_fragments"][0]["source_primitive_ids"] = ["raster_segment:other:1.0.0:1"]
    elif name == "candidate_identity":
        wall["physical_identity"]["candidate_identity_id"] = "wall2_other"
    elif name == "member_ids":
        binding[A]["member_wall_candidate_ids"] = ["wall_" + B]
    elif name == "host_lost":
        binding[A].update(host_wall_id=None, record_id=None, status="abstained")
    elif name == "frame_lost":
        frame[A].update(record_id=None, host_wall_id=None)
    elif name == "frame_geometry":
        cand["resolved_host_frame_evidence"][0]["whole_wall_length_pt"] += 0.5
    elif name == "frame_axis":
        cand["resolved_host_frame_evidence"][0]["axis_unit"] = [0.0, 1.0]
    elif name == "new_frame_on_unframed_old_host":
        frame[B].update(
            record_id=f"frame_{NEW_SNAP}_{B}", host_wall_id=binding[B]["host_wall_id"],
            whole_wall_candidate_ids=["wall_" + B],
        )
        evidence = _frame_evidence(B, NEW_SNAP)
        evidence["whole_wall_candidate_ids"] = ["wall_" + B]
        cand["resolved_host_frame_evidence"].append(evidence)
    elif name == "host_representative":
        binding[A]["representative_observation_id"] = "obs_other"
    elif name == "host_status":
        binding[A]["status"] = "conflict"
    elif name == "frame_status":
        frame[A]["status"] = "abstained"
    elif name == "host_reason":
        binding[A]["reason_codes"] = ["opening_host_binding_resolved", "something_else"]
    elif name == "frame_reason":
        frame[A]["reason_codes"] = ["opening_host_frame_changed"]
    elif name == "undeclared_new_host":
        binding[U].update(
            status="corroborated", host_wall_id="group_new_U", record_id="host_new_U",
            member_wall_candidate_ids=["wall_" + A],
        )
    elif name == "declared_host_not_hosted":
        binding[T].update(status="abstained", host_wall_id=None, record_id=None, member_wall_candidate_ids=[])
    elif name == "declared_host_uncorroborated":
        binding[T]["status"] = "conflict"
    elif name == "declared_host_without_receipt":
        binding[T]["record_id"] = None
    elif name == "declared_host_page":
        binding[T]["page_id"] = "4"
    elif name == "declared_host_representative":
        binding[T]["representative_observation_id"] = "obs_other"
    elif name == "undeclared_new_frame":
        frame[T].update(record_id=f"frame_{NEW_SNAP}_{T}", host_wall_id=binding[T]["host_wall_id"],
                        whole_wall_candidate_ids=["wall_" + T])
        evidence = _frame_evidence(T, NEW_SNAP)
        evidence["whole_wall_candidate_ids"] = ["wall_" + T]
        cand["resolved_host_frame_evidence"].append(evidence)
    elif name == "unrelated_status":
        binding[U]["status"] = "conflict"
    elif name == "unrelated_representative":
        binding[U]["representative_observation_id"] = "obs_other"
    elif name == "unrelated_members":
        binding[U]["member_wall_candidate_ids"] = ["wall_" + B]
    elif name == "undeclared_reason":
        binding[U]["reason_codes"] = ["no_authenticated_host_wall_band", "brand_new_reason"]
    elif name == "unrelated_frame_reason":
        frame[U]["reason_codes"] = ["opening_host_frame_whole_wall_unproven"]
    elif name == "universe_added":
        cand["opening_bindings"].append(_binding("physical_opening_existence_new", NEW_SNAP, status="abstained"))
        cand["host_frames"].append(_frame_row("physical_opening_existence_new", NEW_SNAP, False))
    elif name == "universe_removed":
        cand["opening_bindings"] = [r for r in cand["opening_bindings"] if r["opening_identity_id"] != U]
        cand["host_frames"] = [r for r in cand["host_frames"] if r["opening_identity_id"] != U]
    elif name == "cap":
        cand["primitive_safety_cap"] = 20_001
    elif name == "pages":
        cand["selected_geometry_page_ids"] = ["4"]
    else:  # pragma: no cover
        raise AssertionError(name)


DAMAGE = [
    "fragment_geometry", "centerline", "source_primitive", "candidate_identity", "member_ids",
    "host_lost", "frame_lost", "frame_geometry", "frame_axis", "new_frame_on_unframed_old_host",
    "host_reason", "frame_reason", "host_representative", "host_status", "frame_status",
    "undeclared_new_host", "declared_host_page", "declared_host_representative",
    "undeclared_new_frame", "declared_host_not_hosted",
    "declared_host_uncorroborated", "declared_host_without_receipt", "unrelated_status",
    "unrelated_representative", "unrelated_members", "undeclared_reason", "unrelated_frame_reason",
    "universe_added", "universe_removed", "cap", "pages",
]


@pytest.mark.parametrize("damage", DAMAGE)
def test_declared_event_with_any_authority_or_physical_change_fails_closed(damage):
    base, cand = event()
    _damage(damage, base, cand)
    with pytest.raises(ValueError):
        approve_declared_additive_rekeys(base, cand, declared())
    with pytest.raises(ValueError):
        compare_source_face_reports(base, cand, declarations=declared())
    with pytest.raises(ValueError):
        compare_opposed_source_reports(base, cand, source_bytes=PDF_BYTES, declarations=declared())


def test_declared_reason_transition_must_match_exactly_and_must_occur():
    base, cand = event()
    wrong = declared(expected_unhosted_reason_changes=[
        {"opening_identity_id": U, "before": UNMAPPED_LEFT, "after": ["no_authenticated_host_wall_band"]}])
    with pytest.raises(ValueError, match="undeclared reason change"):
        approve_declared_additive_rekeys(base, cand, wrong)
    unused = declared(expected_unhosted_reason_changes=[
        {"opening_identity_id": U, "before": UNMAPPED_LEFT, "after": UNMAPPED_RIGHT},
        {"opening_identity_id": "physical_opening_existence_never", "before": ["x"], "after": ["y"]}])
    with pytest.raises(ValueError, match="did not occur"):
        approve_declared_additive_rekeys(base, cand, unused)
    no_reason_declared = declared(expected_unhosted_reason_changes=[])
    with pytest.raises(ValueError, match="undeclared reason change"):
        approve_declared_additive_rekeys(base, cand, no_reason_declared)


def test_tolerance_is_limited_to_receipt_addresses_of_declared_rows():
    base, cand = event()
    decl = declared()
    ok = compare_opposed_source_reports(base, cand, source_bytes=PDF_BYTES, declarations=decl)
    assert ok["retention_pass"]
    # Rekeyed rows may differ only by receipt addresses: any other drift on a
    # retained host must fail even though that row is "tolerated".
    drift = deepcopy(cand)
    next(r for r in drift["opening_bindings"] if r["opening_identity_id"] == A)["representative_observation_id"] = "other"
    with pytest.raises(ValueError, match="beyond receipt addresses"):
        compare_opposed_source_reports(base, drift, source_bytes=PDF_BYTES, declarations=decl)


# --------------------------------------------------------------------------
# Declaration schema
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "override",
    [
        {"source_sha256": "A" * 64},
        {"source_sha256": "abc"},
        {"expected_new_host_ids": []},
        {"expected_new_host_ids": [T, T]},
        {"expected_new_host_ids": [" " + T]},
        {"expected_new_host_ids": [3]},
        {"report_shape": "other"},
        {"report_shape": None},
        {"allow_snapshot_receipt_rekey": "yes"},
        {"allow_snapshot_receipt_rekey": 1},
        {"expected_new_frame_host_ids": [U]},
        {"expected_new_frame_host_ids": [T, T]},
        {"expected_new_frame_host_ids": "none"},
        {"baseline_snapshot_id": ""},
        {"candidate_snapshot_id": None},
        {"tracking_issue": True},
        {"tracking_issue": 0},
        {"tracking_issue": "2608"},
        {"expected_unhosted_reason_changes": [{"opening_identity_id": U, "before": ["x"], "after": ["x"]}]},
        {"expected_unhosted_reason_changes": [{"opening_identity_id": T, "before": ["x"], "after": ["y"]}]},
        {"expected_unhosted_reason_changes": [
            {"opening_identity_id": U, "before": ["x"], "after": ["y"]},
            {"opening_identity_id": U, "before": ["y"], "after": ["z"]}]},
        {"expected_unhosted_reason_changes": [{"opening_identity_id": U, "before": ["x"]}]},
        {"expected_unhosted_reason_changes": "none"},
        {"expected_changed_report_keys": []},
        {"expected_changed_report_keys": ["opening_bindings"]},  # snapshot_id is mandatory
        {"expected_changed_report_keys": ["snapshot_id", "snapshot_id"]},
        {"expected_changed_report_keys": ["snapshot_id", 3]},
        {"expected_changed_report_keys": "snapshot_id"},
        {"expected_id_churn_report_keys": ["not_declared_changed"]},
        {"expected_id_churn_report_keys": ["snapshot_id", "snapshot_id"]},
        {"expected_id_churn_report_keys": "summary"},
        # keys verified by dedicated rules cannot be waved through as id churn
        {"expected_id_churn_report_keys": ["canonical_openings"],
         "expected_changed_report_keys": ["snapshot_id", "canonical_openings"]},
        {"expected_id_churn_report_keys": ["summary"],
         "expected_changed_report_keys": ["snapshot_id", "summary"]},
    ],
)
def test_malformed_declarations_are_rejected(override):
    with pytest.raises(ValueError):
        parse_declaration(declaration_raw(**override))


def test_unknown_or_missing_declaration_fields_and_duplicate_events_are_rejected():
    raw = declaration_raw()
    with pytest.raises(ValueError):
        parse_declaration({**raw, "approved_by": "anyone"})
    missing = dict(raw)
    del missing["tracking_issue"]
    with pytest.raises(ValueError):
        parse_declaration(missing)
    with pytest.raises(ValueError, match="schema"):
        parse_declarations({"schema": "other", "declarations": []})
    with pytest.raises(ValueError):
        parse_declarations({"schema": DECLARATION_SCHEMA, "declarations": [raw, raw]})
    with pytest.raises(ValueError):
        parse_declarations({"schema": DECLARATION_SCHEMA})


def test_inline_helper_and_cli_agree_with_the_approval(tmp_path, monkeypatch, capsys):
    from tools import declared_additive_source_retention as module

    base, cand = event()
    assert module.declared_event_approved(base, cand, declared()) is True
    assert module.declared_event_approved(base, cand, ()) is False
    stderr = capsys.readouterr().err
    assert "UNDECLARED additive-source event" in stderr and BASE_SNAP in stderr and NEW_SNAP in stderr
    assert module.declared_event_approved(base, cand, (), explain=False) is False
    assert capsys.readouterr().err == ""
    broken = deepcopy(cand)
    _damage("fragment_geometry", base, broken)
    with pytest.raises(ValueError):  # a violated declared event is never "just undeclared"
        module.declared_event_approved(base, broken, declared())

    (tmp_path / "b.json").write_text(json.dumps(base))
    (tmp_path / "c.json").write_text(json.dumps(cand))
    args = ["--baseline", str(tmp_path / "b.json"), "--candidate", str(tmp_path / "c.json"),
            "--output", str(tmp_path / "out.json")]
    monkeypatch.setattr(module, "load_declarations", lambda path=None: declared())
    assert module.main(args) == 0
    assert json.loads((tmp_path / "out.json").read_text())["declared_new_host_ids"] == [T]
    monkeypatch.setattr(module, "load_declarations", lambda path=None: ())
    assert module.main(args) == 1
    assert "NO DECLARATION" in capsys.readouterr().out


def test_declared_new_frame_must_occur_and_only_when_declared():
    base, cand = event()
    binding = {r["opening_identity_id"]: r for r in cand["opening_bindings"]}
    frame = {r["opening_identity_id"]: r for r in cand["host_frames"]}
    frame[T].update(record_id=f"frame_{NEW_SNAP}_{T}", host_wall_id=binding[T]["host_wall_id"],
                    whole_wall_candidate_ids=["wall_" + T])
    evidence = _frame_evidence(T, NEW_SNAP)
    evidence["whole_wall_candidate_ids"] = ["wall_" + T]
    cand["resolved_host_frame_evidence"].append(evidence)
    with pytest.raises(ValueError, match="undeclared new frames"):
        approve_declared_additive_rekeys(base, cand, declared())
    ok = approve_declared_additive_rekeys(base, cand, declared(expected_new_frame_host_ids=[T]))
    assert ok["declared_new_frame_host_ids"] == [T]
    # Declaring a frame that the candidate does not resolve is a stale declaration.
    base2, cand2 = event()
    with pytest.raises(ValueError, match="declared new frame did not occur"):
        approve_declared_additive_rekeys(base2, cand2, declared(expected_new_frame_host_ids=[T]))


# --------------------------------------------------------------------------
# A declared event cannot hide a change to an unrelated part of the report
# --------------------------------------------------------------------------

def test_undeclared_report_key_change_is_refused_even_when_hosts_are_fine():
    base, cand = event()
    base["source_decode_coverage"] = {"pages": 13, "decoded": 13}
    cand["source_decode_coverage"] = {"pages": 13, "decoded": 12}
    with pytest.raises(ValueError, match="undeclared report keys changed: source_decode_coverage"):
        approve_declared_additive_rekeys(base, cand, declared())
    with pytest.raises(ValueError):
        compare_source_face_reports(base, cand, declarations=declared())
    # Declaring the key makes the same change an explicit, reviewed expectation.
    ok = approve_declared_additive_rekeys(base, cand, declared(expected_changed_report_keys=[
        "snapshot_id", "opening_bindings", "host_frames", "resolved_host_frame_evidence",
        "source_owned_wall_scope_results", "source_decode_coverage"]))
    assert ok["declared_report_keys_without_change"] == []
    # A key present in only one report counts as a change.
    base2, cand2 = event()
    cand2["extra_authority_key"] = {"x": 1}
    with pytest.raises(ValueError, match="extra_authority_key"):
        approve_declared_additive_rekeys(base2, cand2, declared())


def test_normalizer_only_forgives_ordering_the_gate_itself_forgives():
    base, cand = event()
    base["opening_void_reason_codes"] = ["a", "b"]
    cand["opening_void_reason_codes"] = ["b", "a"]
    with pytest.raises(ValueError, match="opening_void_reason_codes"):
        approve_declared_additive_rekeys(base, cand, declared())

    def gate_normalize(value):  # the shape the real workflows use
        if isinstance(value, dict):
            return {
                k: (sorted(v) if k in ("void_reason_codes", "opening_void_reason_codes") else gate_normalize(v))
                for k, v in value.items()
                if k != "sidecar_only"
            }
        if isinstance(value, list):
            return [gate_normalize(v) for v in value]
        return value

    # Order differences in an *undeclared* key pass only with the gate's own normalizer...
    ok = approve_declared_additive_rekeys(base, cand, declared(), normalize=gate_normalize)
    assert ok["declared_new_host_ids"] == [T]
    # ...including a sidecar key the gate itself ignores...
    base["sidecar_only"] = {"a": 1}
    cand["sidecar_only"] = {"a": 2}
    assert approve_declared_additive_rekeys(base, cand, declared(), normalize=gate_normalize)
    with pytest.raises(ValueError, match="sidecar_only"):
        approve_declared_additive_rekeys(base, cand, declared())
    # ...and never forgives a real content change.
    cand["opening_void_reason_codes"] = ["b", "c"]
    with pytest.raises(ValueError, match="opening_void_reason_codes"):
        approve_declared_additive_rekeys(base, cand, declared(), normalize=gate_normalize)


def test_declared_keys_that_did_not_change_are_reported_not_silently_accepted():
    base, cand = event()
    approval = approve_declared_additive_rekeys(base, cand, declared(expected_changed_report_keys=[
        "snapshot_id", "opening_bindings", "host_frames", "resolved_host_frame_evidence",
        "source_owned_wall_scope_results", "selected_geometry_page_ids"]))
    assert approval["declared_report_keys_without_change"] == ["selected_geometry_page_ids"]


def test_assert_unchanged_or_declared_has_exactly_three_outcomes(monkeypatch):
    from tools import declared_additive_source_retention as module

    base, cand = event()
    module.assert_unchanged_or_declared(base, deepcopy(base))  # strictly equal: no declaration needed
    monkeypatch.setattr(module, "load_declarations", lambda path=None: declared())
    module.assert_unchanged_or_declared(base, cand)  # declared and proven
    monkeypatch.setattr(module, "load_declarations", lambda path=None: ())
    with pytest.raises(AssertionError, match="original source authority changed"):
        module.assert_unchanged_or_declared(base, cand)  # undeclared: strict outcome
    monkeypatch.setattr(module, "load_declarations", lambda path=None: declared())
    broken = deepcopy(cand)
    _damage("fragment_geometry", base, broken)
    with pytest.raises(ValueError):  # declared but violated is never the undeclared case
        module.assert_unchanged_or_declared(base, broken)


def test_strict_or_declared_context_runs_the_gates_own_assertions_first(monkeypatch):
    from tools import declared_additive_source_retention as module

    base, cand = event()
    ran = []
    with module.strict_or_declared(base, deepcopy(base)):
        ran.append("strict block ran")
        assert base == deepcopy(base)
    assert ran == ["strict block ran"]

    monkeypatch.setattr(module, "load_declarations", lambda path=None: declared())
    with module.strict_or_declared(base, cand):  # failing assertion excused by a proven event
        assert base["opening_bindings"] == cand["opening_bindings"]
    with pytest.raises(ValueError):  # ...but a declared, violated event is never excused
        broken = deepcopy(cand)
        _damage("fragment_geometry", base, broken)
        with module.strict_or_declared(base, broken):
            assert base["opening_bindings"] == broken["opening_bindings"]

    monkeypatch.setattr(module, "load_declarations", lambda path=None: ())
    with pytest.raises(AssertionError):  # undeclared: the gate's own assertion decides
        with module.strict_or_declared(base, cand):
            assert base["opening_bindings"] == cand["opening_bindings"]
    with pytest.raises(KeyError):  # non-assertion errors are never swallowed
        with module.strict_or_declared(base, cand):
            base["missing"]


# --------------------------------------------------------------------------
# W4 changes must be explained by the added source
# --------------------------------------------------------------------------

def _add_unhosted_wall(rep, wid, y, prim):
    record = _wall(wid, y, 900 + int(y))
    record["physical_identity"]["source_primitive_ids"] = [prim]
    record["source_edge_fragments"][0]["source_primitive_ids"] = [prim]
    rep["source_owned_wall_scope_results"][0]["records"].append(record)
    return record


def _event_with_unhosted_wall():
    base, cand = event()
    _add_unhosted_wall(base, "wall_extra", 70.0, "raster_segment:source:1.0.0:extra")
    _add_unhosted_wall(cand, "wall_extra", 70.0, "raster_segment:source:1.0.0:extra")
    return base, cand


def test_w4_delta_counts_are_reported_for_the_declared_event():
    base, cand = _event_with_unhosted_wall()
    approval = approve_declared_additive_rekeys(base, cand, declared())
    assert approval["w4_wall_delta"] == {"retained": 3, "lost_with_successor": 0, "gained_from_new_source": 1}


def test_unhosted_wall_may_gain_an_interior_split_node_without_changing_its_path():
    base, cand = _event_with_unhosted_wall()
    record = _walls(cand)["wall_extra"]
    record["wall_candidate"]["centerline_pts"] = [[10.0, 70.0], [40.0, 70.0], [70.0, 70.0]]
    record["source_edge_fragments"] = [
        {"edge_id": "split_a", "geometry": [10.0, 70.0, 40.0, 70.0],
         "source_primitive_ids": ["raster_segment:source:1.0.0:extra"]},
        {"edge_id": "split_b", "geometry": [40.0, 70.0, 70.0, 70.0],
         "source_primitive_ids": ["raster_segment:source:1.0.0:extra"]},
    ]
    assert approve_declared_additive_rekeys(base, cand, declared())["declared_new_host_ids"] == [T]


def test_unhosted_wall_whose_terminal_moved_needs_a_successor_on_the_same_primitives():
    base, cand = _event_with_unhosted_wall()
    cand["source_owned_wall_scope_results"][0]["records"] = [
        r for r in cand["source_owned_wall_scope_results"][0]["records"] if r["wall_candidate_id"] != "wall_extra"
    ]
    with pytest.raises(ValueError, match="disappeared without a successor"):
        approve_declared_additive_rekeys(base, cand, declared())
    moved = _add_unhosted_wall(cand, "wall_extra_moved", 70.0, "raster_segment:source:1.0.0:extra")
    moved["physical_identity"]["path_fingerprint"] = [[10.0, 70.0], [68.2, 70.0]]
    moved["wall_candidate"]["centerline_pts"] = [[10.0, 70.0], [68.2, 70.0]]
    moved["source_edge_fragments"][0]["geometry"] = [10.0, 70.0, 68.2, 70.0]
    approval = approve_declared_additive_rekeys(base, cand, declared())
    assert approval["w4_wall_delta"]["lost_with_successor"] == 1


@pytest.mark.parametrize("damage", ["path", "identity", "ancestry"])
def test_retained_unhosted_wall_id_cannot_change_its_physical_identity_path_or_ancestry(damage):
    base, cand = _event_with_unhosted_wall()
    record = _walls(cand)["wall_extra"]
    if damage == "path":
        record["physical_identity"]["path_fingerprint"] = [[10.0, 70.0], [71.0, 70.0]]
    elif damage == "identity":
        record["physical_identity"]["candidate_identity_id"] = "wall2_other"
    else:
        record["physical_identity"]["source_primitive_ids"] = ["raster_segment:source:1.0.0:other"]
        record["source_edge_fragments"][0]["source_primitive_ids"] = ["raster_segment:source:1.0.0:other"]
    with pytest.raises(ValueError, match="retained W4 wall changed"):
        approve_declared_additive_rekeys(base, cand, declared())


def test_new_wall_built_only_from_old_source_is_not_explained_by_the_added_source():
    base, cand = _event_with_unhosted_wall()
    _add_unhosted_wall(cand, "wall_invented", 90.0, "raster_segment:source:1.0.0:extra")
    with pytest.raises(ValueError, match="not built from any new source primitive"):
        approve_declared_additive_rekeys(base, cand, declared())


def test_wall_split_into_two_successors_is_conservatively_refused():
    base, cand = _event_with_unhosted_wall()
    cand["source_owned_wall_scope_results"][0]["records"] = [
        r for r in cand["source_owned_wall_scope_results"][0]["records"] if r["wall_candidate_id"] != "wall_extra"
    ]
    for name, y in (("wall_extra_a", 70.0), ("wall_extra_b", 71.0)):
        _add_unhosted_wall(cand, name, y, "raster_segment:source:1.0.0:extra")
    with pytest.raises(ValueError, match="not built from any new source primitive"):
        approve_declared_additive_rekeys(base, cand, declared())


# --------------------------------------------------------------------------
# face_report shape: no frame geometry array; the declared shape must match
# --------------------------------------------------------------------------

def _as_face(rep):
    rep = deepcopy(rep)
    rep.pop("resolved_host_frame_evidence")
    return rep


def face_declared(**overrides):
    return declared(report_shape="face_report", **overrides)


def test_face_report_event_is_approved_with_frame_geometry_explicitly_unverified():
    base, cand = event()
    fb, fc = _as_face(base), _as_face(cand)
    approval = approve_declared_additive_rekeys(fb, fc, face_declared())
    assert approval["report_shape"] == "face_report"
    assert approval["frame_geometry_verified"] is False
    assert approval["rekeyed_host_ids"] == sorted([A, B])
    assert compare_source_face_reports(fb, fc, declarations=face_declared())["retention_pass"] is True
    assert compare_opposed_source_reports(fb, fc, source_bytes=PDF_BYTES, declarations=face_declared())["retention_pass"]
    assert approve_declared_additive_rekeys(base, cand, declared())["frame_geometry_verified"] is True


def test_declared_shape_must_match_the_reports_so_evidence_cannot_be_silently_dropped():
    base, cand = event()
    fb, fc = _as_face(base), _as_face(cand)
    with pytest.raises(ValueError):  # stage_report declared, but the evidence array vanished
        approve_declared_additive_rekeys(fb, fc, declared())
    with pytest.raises(ValueError, match="declared without it"):  # face_report declared, evidence present
        approve_declared_additive_rekeys(base, cand, face_declared())
    half_dropped = _as_face(cand)
    with pytest.raises(ValueError):
        approve_declared_additive_rekeys(base, half_dropped, declared())


@pytest.mark.parametrize("damage", ["fragment_geometry", "centerline", "host_lost", "member_ids",
                                    "host_reason", "frame_reason", "frame_status", "undeclared_new_host",
                                    "unrelated_status", "undeclared_reason", "universe_removed"])
def test_face_report_still_fails_closed_on_everything_it_can_see(damage):
    base, cand = event()
    fb, fc = _as_face(base), _as_face(cand)
    _damage(damage, fb, fc)
    fc.pop("resolved_host_frame_evidence", None)
    with pytest.raises(ValueError):
        approve_declared_additive_rekeys(fb, fc, face_declared())


def test_face_report_catches_frame_loss_and_frame_membership_change():
    base, cand = event()
    fb, fc = _as_face(base), _as_face(cand)
    frame = {r["opening_identity_id"]: r for r in fc["host_frames"]}
    frame[A].update(record_id=None, host_wall_id=None)
    with pytest.raises(ValueError):
        approve_declared_additive_rekeys(fb, fc, face_declared())
    fb, fc = _as_face(base), _as_face(cand)
    for r in fc["host_frames"]:
        if r["opening_identity_id"] == A:
            r["whole_wall_candidate_ids"] = ["wall_" + A, "wall_" + B]
    with pytest.raises(ValueError):
        approve_declared_additive_rekeys(fb, fc, face_declared())


@pytest.mark.parametrize("field", ["candidate_identity_id", "source_primitive_ids", "path_fingerprint"])
def test_malformed_w4_wall_record_is_a_refusal_not_a_crash(field):
    base, cand = _event_with_unhosted_wall()
    del _walls(cand)["wall_extra"]["physical_identity"][field]
    with pytest.raises(ValueError):
        approve_declared_additive_rekeys(base, cand, declared())


# --------------------------------------------------------------------------
# Re-sealed prior quantities change only by snapshot-scoped receipts
# --------------------------------------------------------------------------

def _sealed(quantity_id, value, host, frame=None):
    ids = ["source_observation_1", "opening_label_dimension_x", f"opening_host_binding_v3_{host}"]
    if frame:
        ids.append(f"opening_host_frame_v2_{frame}")
    return {
        "quantity_id": quantity_id, "value": value, "unit": "m2", "family": "opening_area",
        "object_identity_refs": [f"physical_{quantity_id}"], "status": "corroborated",
        "evidence_ids": sorted(ids), "trace_evidence_ids": sorted(ids),
        "fingerprint": f"fp_{host}_{frame}",
    }


def test_resealed_prior_rows_may_swap_only_one_host_and_one_frame_receipt():
    from tools.declared_additive_source_retention import sealed_quantities_changed_only_by_snapshot_receipts as check

    old = [_sealed("q1", 2.16, "a", "fa"), _sealed("q2", 0.9, "b")]
    new = [_sealed("q1", 2.16, "a2", "fa2"), _sealed("q2", 0.9, "b2"), _sealed("q3", 1.8, "c")]
    snapshot = deepcopy((old, new))
    assert check(old, new) == {"prior_rows": 2, "rekeyed_rows": 2, "new_rows": 1}
    assert check(old, old) == {"prior_rows": 2, "rekeyed_rows": 0, "new_rows": 0}
    assert (old, new) == snapshot


@pytest.mark.parametrize("damage", ["value", "unit", "refs", "status", "extra_evidence", "swap_source_observation",
                                    "two_host_receipts", "missing_row", "duplicate_id", "retag_trace_only"])
def test_resealed_prior_rows_that_changed_anything_else_are_refused(damage):
    from tools.declared_additive_source_retention import sealed_quantities_changed_only_by_snapshot_receipts as check

    old = [_sealed("q1", 2.16, "a", "fa")]
    new = [_sealed("q1", 2.16, "a2", "fa2")]
    row = new[0]
    if damage == "value":
        row["value"] = 2.17
    elif damage == "unit":
        row["unit"] = "m"
    elif damage == "refs":
        row["object_identity_refs"] = ["physical_other"]
    elif damage == "status":
        row["status"] = "candidate"
    elif damage == "extra_evidence":
        row["evidence_ids"] = sorted(row["evidence_ids"] + ["opening_host_binding_v3_extra"])
    elif damage == "swap_source_observation":
        row["evidence_ids"] = sorted(i if i != "source_observation_1" else "source_observation_2" for i in row["evidence_ids"])
    elif damage == "two_host_receipts":
        row["trace_evidence_ids"] = sorted(row["trace_evidence_ids"] + ["opening_host_binding_v3_other", "opening_host_binding_v3_third"])
    elif damage == "missing_row":
        new = []
    elif damage == "duplicate_id":
        new = [row, deepcopy(row)]
    else:  # retag_trace_only: a non-receipt id swapped only in the trace set
        row["trace_evidence_ids"] = sorted(i if i != "source_observation_1" else "source_observation_9" for i in row["trace_evidence_ids"])
    with pytest.raises(ValueError):
        check(old, new)


# --------------------------------------------------------------------------
# Receipt rekey is a separate, explicit decision (default: exact retention)
# --------------------------------------------------------------------------

def test_rekeyed_receipts_are_refused_unless_the_declaration_explicitly_allows_them():
    base, cand = event()
    with pytest.raises(ValueError, match="allow_snapshot_receipt_rekey"):
        approve_declared_additive_rekeys(base, cand, declared(allow_snapshot_receipt_rekey=False))
    with pytest.raises(ValueError):
        compare_source_face_reports(base, cand, declarations=declared(allow_snapshot_receipt_rekey=False))
    ok = approve_declared_additive_rekeys(base, cand, declared())
    assert ok["snapshot_receipt_rekey_allowed"] is True


def test_exact_retention_event_needs_no_rekey_permission():
    # Same snapshot, same receipts for every prior host/frame; only the declared
    # host is new.  This is the strict stance: nothing previously authenticated moves.
    base = report(BASE_SNAP)
    cand = report(BASE_SNAP, t_hosted=True, u_reasons=UNMAPPED_RIGHT)
    strict = declared(candidate_snapshot_id=BASE_SNAP, allow_snapshot_receipt_rekey=False)
    approval = approve_declared_additive_rekeys(base, cand, strict)
    assert approval["rekeyed_host_ids"] == []
    assert approval["exact_retained_host_ids"] == sorted([A, B])
    assert approval["snapshot_receipt_rekey_allowed"] is False
    assert compare_source_face_reports(base, cand, declarations=strict)["retention_pass"] is True
    assert compare_opposed_source_reports(base, cand, source_bytes=PDF_BYTES, declarations=strict)["retention_pass"]
    # ...and a single moved prior receipt breaks exactness even in that event.
    moved = deepcopy(cand)
    next(r for r in moved["opening_bindings"] if r["opening_identity_id"] == A)["record_id"] = "moved"
    with pytest.raises(ValueError):
        approve_declared_additive_rekeys(base, moved, strict)


# --------------------------------------------------------------------------
# Scoped equality helpers
# --------------------------------------------------------------------------

HEX = "0123456789abcdef" * 2  # 32 hex digits


def sid(prefix, digit="a"):
    return f"{prefix}_{digit * 32}"


def test_mask_and_unordered_equality_ignore_only_snapshot_scoped_ids_and_list_order():
    from tools.source_report_scoped_equality import (
        SNAPSHOT_SCOPED_ID_PREFIXES,
        equal_modulo_snapshot_scoped_ids,
        mask_snapshot_scoped_ids,
    )

    left = {"rows": [{"id": sid("opening_host_binding_v3", "a"), "v": 1}, {"id": sid("source_snapshot", "b"), "v": 2}]}
    right = {"rows": [{"id": sid("source_snapshot", "c"), "v": 2}, {"id": sid("opening_host_binding_v3", "d"), "v": 1}]}
    assert equal_modulo_snapshot_scoped_ids(left, right)
    assert mask_snapshot_scoped_ids(sid("opening_host_binding_group", "e") + " text") == "<SNAPSHOT_SCOPED_ID> text"
    # ids that are physical / source identities are never masked
    for prefix in ("physical_opening_existence", "source_observation", "wall2", "opening_label_dimension"):
        assert prefix not in SNAPSHOT_SCOPED_ID_PREFIXES
        assert not equal_modulo_snapshot_scoped_ids({"id": sid(prefix, "a")}, {"id": sid(prefix, "b")})
    # values, counts and structure still matter
    assert not equal_modulo_snapshot_scoped_ids({"v": 1}, {"v": 2})
    assert not equal_modulo_snapshot_scoped_ids({"rows": [1, 2]}, {"rows": [1, 2, 3]})
    assert not equal_modulo_snapshot_scoped_ids({"a": 1}, {"b": 1})
    assert not equal_modulo_snapshot_scoped_ids(
        {"rows": [sid("source_room_face", "a"), sid("source_room_face", "b")]},
        {"rows": [sid("source_room_face", "a")]},
    )


def test_snapshot_scoped_prefixes_are_the_code_derived_set():
    import pathlib

    from tools.source_report_scoped_equality import SNAPSHOT_SCOPED_ID_PREFIXES

    root = pathlib.Path(__file__).resolve().parent.parent
    for prefix in SNAPSHOT_SCOPED_ID_PREFIXES:
        if prefix == "source_snapshot":
            continue
        sources = [p for p in root.glob("pb_*.py") if f'"{prefix}"' in p.read_text(encoding="utf-8")]
        assert sources, f"no production module constructs {prefix}"


def test_additive_observation_inventory_allows_only_added_observations():
    from tools.source_report_scoped_equality import additive_observation_inventory_equal as equal

    base = {"record": {"visible_observation_ids": ["o1", "o2"], "conflict_observation_ids": ["o1"], "status": "conflict",
                       "record_id": sid("semantic_opening_enumeration", "a")}}
    grown = {"record": {"visible_observation_ids": ["o2", "o1", "o3"], "conflict_observation_ids": ["o1"], "status": "conflict",
                        "record_id": sid("semantic_opening_enumeration", "b")}}
    assert equal(base, grown)
    lost = deepcopy(grown)
    lost["record"]["visible_observation_ids"] = ["o1", "o3"]
    assert not equal(base, lost)
    repeated = deepcopy(grown)
    repeated["record"]["visible_observation_ids"] = ["o1", "o1", "o2"]
    assert not equal(base, repeated)
    other = deepcopy(grown)
    other["record"]["status"] = "abstained"
    assert not equal(base, other)
    renamed_key = deepcopy(grown)
    renamed_key["record"]["extra"] = 1
    assert not equal(base, renamed_key)


def test_evidence_swap_matches_rules():
    from tools.source_report_scoped_equality import evidence_swap_matches as ok

    b1, f1 = sid("opening_host_binding_v3", "a"), sid("opening_host_frame_v2", "a")
    b2, f2 = sid("opening_host_binding_v3", "b"), sid("opening_host_frame_v2", "b")
    base = ["x", "y", b1, f1]
    assert ok(base, ["x", "y", b2, f2])  # one binding + one frame swapped
    assert ok(base, base)
    assert not ok(base, ["x", "z", b2, f2])  # a non-receipt id changed
    assert not ok(base, ["x", "y", b2, f2, sid("opening_host_binding_v3", "c")])  # second binding added
    assert not ok(base, ["x", "y", b2])  # frame receipt silently dropped
    assert ok(["x"], ["x", b2], net_additions={"opening_host_binding_v3": 1})  # declared new host binding
    assert not ok(["x"], ["x", b2])  # ...but only when declared
    assert not ok(["x", "x"], ["x"])  # duplicate ids are malformed
    assert not ok("x", ["x"])


# --------------------------------------------------------------------------
# Dedicated key rules: canonical openings, summary, semantic inventory, id churn
# --------------------------------------------------------------------------

def _canonical(oid, snap, *, hosted, framed, area=1.8):
    ids = ["source_observation_1", "opening_label_dimension_x", f"physical_opening_existence_{oid[-1]}"]
    if hosted:
        ids.append(sid("opening_host_binding_v3", snap[-1] if snap[-1] in HEX else "a"))
    if framed:
        ids.append(sid("opening_host_frame_v2", snap[-1] if snap[-1] in HEX else "a"))
    return {
        "physical_opening_id": oid,
        "area_m2": area,
        "area_basis": "figured_opening_label",
        "snapshot_id": snap,
        "host_wall_id": f"group_{snap}_{oid}" if hosted else None,
        "host_binding_record_id": f"host_{snap}_{oid}" if hosted else None,
        "host_frame_record_id": f"frame_{snap}_{oid}" if framed else None,
        "evidence_ids": sorted(ids),
    }


def rich_event():
    """The basic event plus canonical openings, summary, semantic inventory and a churn key."""
    base, cand = event()
    for rep, snap, t_hosted in ((base, BASE_SNAP, False), (cand, NEW_SNAP, True)):
        # distinct hex digit per snapshot so the receipt ids differ like real ones
        digit = "a" if snap == BASE_SNAP else "b"
        rows = []
        for oid in (A, B, T, U):
            hosted = oid in (A, B) or (oid == T and t_hosted)
            row = _canonical(oid, snap, hosted=hosted, framed=(oid == A))
            row["evidence_ids"] = sorted(
                i if not i.startswith(("opening_host_binding_v3_", "opening_host_frame_v2_"))
                else i.rsplit("_", 1)[0] + "_" + digit * 32
                for i in row["evidence_ids"]
            )
            rows.append(row)
        rep["canonical_openings"] = rows
        rep["summary"] = {
            "authenticated_hosts": 3 if t_hosted else 2,
            "resolved_source_frames": 1,
            "physical_existence_claims": 4,
            "room_scope_reason_counts": {"resolved": 1},
        }
        rep["semantic_inventory"] = {"record": {
            "visible_observation_ids": ["o1", "o2"] + (["o3"] if t_hosted else []),
            "status": "conflict",
            "record_id": sid("semantic_opening_enumeration", digit),
        }}
        rep["native_candidate_closures"] = [
            {"candidate_id": sid("physical_opening_candidate", digit), "physical": "physical_opening_existence_x", "n": 3},
            {"candidate_id": sid("physical_opening_raw_candidate", digit), "physical": "physical_opening_existence_y", "n": 4},
        ]
    return base, cand


RICH_KEYS = [
    "snapshot_id", "opening_bindings", "host_frames", "resolved_host_frame_evidence",
    "source_owned_wall_scope_results", "canonical_openings", "summary", "semantic_inventory",
    "native_candidate_closures",
]


def rich_declared(**overrides):
    fields = {
        "expected_changed_report_keys": RICH_KEYS,
        "expected_id_churn_report_keys": ["native_candidate_closures"],
    }
    fields.update(overrides)
    return declared(**fields)


def test_rich_event_is_approved_and_names_nothing_unverified():
    base, cand = rich_event()
    approval = approve_declared_additive_rekeys(base, cand, rich_declared())
    assert approval["unverified_changed_report_keys"] == []
    assert approval["rekeyed_host_ids"] == sorted([A, B])


def test_blind_keys_are_reported_not_hidden():
    base, cand = rich_event()
    base["composition_reason_codes"] = ["a", "b"]
    cand["composition_reason_codes"] = ["a", "c"]
    with pytest.raises(ValueError, match="undeclared report keys changed: composition_reason_codes"):
        approve_declared_additive_rekeys(base, cand, rich_declared())
    approval = approve_declared_additive_rekeys(
        base, cand, rich_declared(expected_changed_report_keys=RICH_KEYS + ["composition_reason_codes"])
    )
    assert approval["unverified_changed_report_keys"] == ["composition_reason_codes"]


@pytest.mark.parametrize("damage", [
    "area_changed",                   # an old opening's figured area moved
    "area_basis_changed",
    "evidence_other_changed",         # a non-receipt evidence id swapped
    "evidence_second_binding",        # two host-binding receipts instead of one
    "unrelated_host_field",           # an unhosted opening gained host fields
    "unrelated_evidence",             # an unhosted opening's evidence changed
    "canonical_disagrees_with_binding",
    "canonical_universe_changed",
    "new_host_two_bindings",
    "new_host_area_changed",
    "summary_hosts_wrong",
    "summary_other_key_changed",
    "summary_shape_changed",
    "inventory_lost_observation",
    "inventory_status_changed",
    "churn_value_changed",
    "churn_physical_id_changed",
    "churn_count_changed",
])
def test_dedicated_rules_refuse_what_a_blind_excuse_would_have_hidden(damage):
    base, cand = rich_event()
    can = {r["physical_opening_id"]: r for r in cand["canonical_openings"]}
    if damage == "area_changed":
        can[A]["area_m2"] = 2.2
    elif damage == "area_basis_changed":
        can[B]["area_basis"] = "schedule"
    elif damage == "evidence_other_changed":
        can[A]["evidence_ids"] = sorted(i if i != "source_observation_1" else "source_observation_2" for i in can[A]["evidence_ids"])
    elif damage == "evidence_second_binding":
        can[B]["evidence_ids"] = sorted(can[B]["evidence_ids"] + [sid("opening_host_binding_v3", "f")])
    elif damage == "unrelated_host_field":
        can[U]["host_wall_id"] = "group_x"
    elif damage == "unrelated_evidence":
        can[U]["evidence_ids"] = sorted(can[U]["evidence_ids"] + [sid("opening_host_binding_v3", "f")])
    elif damage == "canonical_disagrees_with_binding":
        can[A]["host_wall_id"] = "group_other"
    elif damage == "canonical_universe_changed":
        cand["canonical_openings"] = [r for r in cand["canonical_openings"] if r["physical_opening_id"] != U]
    elif damage == "new_host_two_bindings":
        can[T]["evidence_ids"] = sorted(can[T]["evidence_ids"] + [sid("opening_host_binding_v3", "f")])
    elif damage == "new_host_area_changed":
        can[T]["area_m2"] = 9.9
    elif damage == "summary_hosts_wrong":
        cand["summary"]["authenticated_hosts"] = 5
    elif damage == "summary_other_key_changed":
        cand["summary"]["physical_existence_claims"] = 5
    elif damage == "summary_shape_changed":
        cand["summary"]["extra"] = 1
    elif damage == "inventory_lost_observation":
        cand["semantic_inventory"]["record"]["visible_observation_ids"] = ["o1", "o3"]
    elif damage == "inventory_status_changed":
        cand["semantic_inventory"]["record"]["status"] = "corroborated"
    elif damage == "churn_value_changed":
        cand["native_candidate_closures"][0]["n"] = 99
    elif damage == "churn_physical_id_changed":
        cand["native_candidate_closures"][0]["physical"] = "physical_opening_existence_z"
    else:  # churn_count_changed
        cand["native_candidate_closures"].append({"candidate_id": sid("physical_opening_candidate", "f"), "n": 1})
    with pytest.raises(ValueError):
        approve_declared_additive_rekeys(base, cand, rich_declared())


def test_exact_retention_event_with_rich_report_needs_no_receipt_changes():
    # Same snapshot: canonical rows may then differ only for the declared new host.
    base, _ = rich_event()
    cand = deepcopy(base)
    cand["opening_bindings"] = report(BASE_SNAP, t_hosted=True, u_reasons=UNMAPPED_RIGHT)["opening_bindings"]
    cand["host_frames"] = report(BASE_SNAP, t_hosted=True, u_reasons=UNMAPPED_RIGHT)["host_frames"]
    cand["source_owned_wall_scope_results"] = report(BASE_SNAP, t_hosted=True)["source_owned_wall_scope_results"]
    can = {r["physical_opening_id"]: r for r in cand["canonical_openings"]}
    can[T].update(host_wall_id=f"group_{BASE_SNAP}_{T}", host_binding_record_id=f"host_{BASE_SNAP}_{T}",
                  evidence_ids=sorted(can[T]["evidence_ids"] + [sid("opening_host_binding_v3", "a")]))
    cand["summary"]["authenticated_hosts"] = 3
    strict = rich_declared(candidate_snapshot_id=BASE_SNAP, allow_snapshot_receipt_rekey=False)
    approval = approve_declared_additive_rekeys(base, cand, strict)
    assert approval["rekeyed_host_ids"] == []
    # an old host's canonical host fields moving is a rekey and is refused when not allowed
    can[A]["host_wall_id"] = "moved"
    with pytest.raises(ValueError):
        approve_declared_additive_rekeys(base, cand, strict)
