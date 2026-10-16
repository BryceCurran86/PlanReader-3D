"""Synthetic proof for tools.prove_candidate_id_snapshot_remap / record_candidate_id_inputs.

No PDF, no production module is exercised except ``stable_contract_id``.  The synthetic
world mimics the two things the real proof relies on: candidate ids are
``stable_contract_id(kind, payload)`` with ``snapshot_id`` inside the payload, and the
stage report carries closure id lists plus the snapshot token.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from pb_migration_contracts import stable_contract_id
from tools import prove_candidate_id_snapshot_remap as proof
from tools import record_candidate_id_inputs as recorder

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = {"document_id": "doc", "revision_id": "rev", "source_sha256": "ab" * 32}


def snapshot(seed: str) -> str:
    return stable_contract_id("source_snapshot", {"seed": seed}, digest_chars=32)


def candidates(snap: str) -> list[dict]:
    """Two raster raw gaps and three native candidates, with distinct supports."""
    raster = [
        {"kind": "physical_opening_raw_candidate", "closure": "raster",
         "payload": {**DOC, "snapshot_id": snap, "page_id": "p3", "pattern": "raster_wall_band_gap_candidate",
                     "gap_box_pt": [10.0 + i, 20.0, 12.0 + i, 22.0],
                     "source_observation_ids": [f"obs_r{i}a", f"obs_r{i}b"]}}
        for i in range(2)
    ]
    native = [
        {"kind": "physical_opening_candidate", "closure": "native",
         "payload": {**DOC, "snapshot_id": snap, "page_id": "p3", "structural_pattern": "jamb_bounded",
                     "viewport_id": None, "source_lineage_root_ids": [f"root_{i}"],
                     "source_observation_ids": [f"obs_n{i}a", f"obs_n{i}b"]}}
        for i in range(2)
    ] + [
        {"kind": "physical_opening_raw_candidate", "closure": "native",
         "payload": {**DOC, "snapshot_id": snap, "page_id": "p3", "pattern": "door_jamb_leaf_candidate",
                     "source_observation_ids": ["obs_n9a", "obs_n9b"]}}
    ]
    return raster + native


def world(snap: str, *, mutate=None):
    """Return (stage_report, recording) for one run at snapshot ``snap``."""
    items = candidates(snap)
    if mutate:
        mutate(items)
    recording, closure = {}, {"raster": [], "native": []}
    for item in items:
        cid = stable_contract_id(item["kind"], item["payload"], digest_chars=32)
        recording[cid] = [{"kind": item["kind"], "payload": copy.deepcopy(item["payload"]),
                           "args": [], "kw": {"digest_chars": 32}}]
        closure[item["closure"]].append((cid, item["payload"]["source_observation_ids"]))

    def row(name):
        rows = closure[name]
        return {"page_id": "p3", "status": "corroborated", "reason_codes": ["r"],
                "raw_candidate_count": len(rows), "resolved_candidate_count": 0,
                "candidate_universe_complete": False,
                "unresolved_candidate_ids": [c for c, _ in rows],
                "unresolved_observation_ids": sorted({o for _, obs in rows for o in obs})}
    report = {"source_snapshot_id": snap, "raster_candidate_closures": [row("raster")],
              "native_candidate_closures": [row("native")]}
    return report, recording


BASE_SNAP, CAND_SNAP = snapshot("before"), snapshot("after")


def run(candidate_mutate=None, baseline_mutate=None, **kw):
    base_report, base_rec = world(BASE_SNAP, mutate=baseline_mutate)
    cand_report, cand_rec = world(CAND_SNAP, mutate=candidate_mutate)
    return proof.prove_snapshot_remap(base_report, cand_report, base_rec, cand_rec, **kw), \
        (base_report, cand_report, base_rec, cand_rec)


def test_pure_snapshot_change_is_proven_and_every_id_moves():
    result, (base_report, cand_report, *_) = run()
    assert result["PROVEN"] and result["total_mapped"] == 5 and not result["failures"]
    assert all(c["injective"] and c["onto_candidate_set"] for c in result["closures"])
    moved = {i for r in base_report["native_candidate_closures"] + base_report["raster_candidate_closures"]
             for i in r["unresolved_candidate_ids"]}
    kept = {i for r in cand_report["native_candidate_closures"] + cand_report["raster_candidate_closures"]
            for i in r["unresolved_candidate_ids"]}
    assert moved.isdisjoint(kept)


@pytest.mark.parametrize("name, mutate", [
    ("dropped observation", lambda items: items[0]["payload"].__setitem__("source_observation_ids", ["obs_r0a"])),
    ("moved gap box", lambda items: items[0]["payload"].__setitem__("gap_box_pt", [10.001, 20.0, 12.0, 22.0])),
    ("changed pattern", lambda items: items[4]["payload"].__setitem__("pattern", "window_jamb_pair_candidate")),
    ("changed lineage root", lambda items: items[2]["payload"].__setitem__("source_lineage_root_ids", ["other"])),
    ("changed viewport", lambda items: items[3]["payload"].__setitem__("viewport_id", "vp")),
    ("changed page", lambda items: items[1]["payload"].__setitem__("page_id", "p4")),
])
def test_any_change_beyond_snapshot_is_refused(name, mutate):
    result, _ = run(candidate_mutate=mutate)
    assert not result["PROVEN"], name
    assert result["failures"]


def test_extra_candidate_in_candidate_run_is_refused():
    def add(items):
        extra = copy.deepcopy(items[0])
        extra["payload"]["source_observation_ids"] = ["obs_new1", "obs_new2"]
        items.append(extra)
    result, _ = run(candidate_mutate=add)
    assert not result["PROVEN"]
    assert any("no baseline preimage" in f["reason"] for f in result["failures"])


def test_missing_candidate_in_candidate_run_is_refused():
    result, _ = run(candidate_mutate=lambda items: items.pop())
    assert not result["PROVEN"]


def test_closure_summary_change_is_refused():
    base_report, base_rec = world(BASE_SNAP)
    cand_report, cand_rec = world(CAND_SNAP)
    cand_report["native_candidate_closures"][0]["status"] = "ambiguous"
    result = proof.prove_snapshot_remap(base_report, cand_report, base_rec, cand_rec)
    assert not result["PROVEN"]
    assert any("status" in f["reason"] for f in result["failures"])


def test_unfaithful_recording_is_refused():
    base_report, base_rec = world(BASE_SNAP)
    cand_report, cand_rec = world(CAND_SNAP)
    victim = base_report["native_candidate_closures"][0]["unresolved_candidate_ids"][0]
    base_rec[victim][0]["payload"]["page_id"] = "tampered"
    result = proof.prove_snapshot_remap(base_report, cand_report, base_rec, cand_rec)
    assert not result["PROVEN"]
    assert any("does not reproduce" in f["reason"] for f in result["failures"])


def test_missing_and_ambiguous_recordings_are_refused():
    base_report, base_rec = world(BASE_SNAP)
    cand_report, cand_rec = world(CAND_SNAP)
    ids = base_report["native_candidate_closures"][0]["unresolved_candidate_ids"]
    del base_rec[ids[0]]
    twin = copy.deepcopy(base_rec[ids[1]][0])
    twin["payload"]["page_id"] = "p9"
    base_rec[ids[1]].append(twin)
    reasons = " ".join(f["reason"] for f in proof.prove_snapshot_remap(
        base_report, cand_report, base_rec, cand_rec)["failures"])
    assert "no recorded hash input" in reasons and "more than one distinct input" in reasons


def test_report_with_two_snapshots_is_rejected():
    base_report, base_rec = world(BASE_SNAP)
    cand_report, cand_rec = world(CAND_SNAP)
    cand_report["extra"] = snapshot("third")
    with pytest.raises(ValueError, match="exactly one source snapshot"):
        proof.prove_snapshot_remap(base_report, cand_report, base_rec, cand_rec)


def test_input_order_and_no_mutation():
    base_report, base_rec = world(BASE_SNAP)
    cand_report, cand_rec = world(CAND_SNAP)
    snapshot_before = copy.deepcopy((base_report, cand_report, base_rec, cand_rec))
    first = proof.prove_snapshot_remap(base_report, cand_report, base_rec, cand_rec)
    assert (base_report, cand_report, base_rec, cand_rec) == snapshot_before
    for report in (base_report, cand_report):
        for key in proof.CLOSURE_KEYS:
            report[key][0]["unresolved_candidate_ids"].reverse()
    second = proof.prove_snapshot_remap(base_report, cand_report, base_rec, cand_rec)
    assert first["PROVEN"] and second["PROVEN"]
    assert first["closures"][0]["pairs"] == second["closures"][0]["pairs"]


def test_translation_of_geometry_changes_ids_but_not_the_proof():
    def shift(items):
        for item in items:
            if "gap_box_pt" in item["payload"]:
                item["payload"]["gap_box_pt"] = [v + 500.0 for v in item["payload"]["gap_box_pt"]]
    result, _ = run(candidate_mutate=shift, baseline_mutate=shift)
    assert result["PROVEN"]


def observations(snapshot_inside: bool = False, drift: bool = False):
    out = {}
    for item in candidates(BASE_SNAP):
        for obs in item["payload"]["source_observation_ids"] + item["payload"].get("source_lineage_root_ids", []):
            ident = {"document_id": "doc", "kind": "seg", "primitive_ref": obs, "geometry": [0.0, 1.0]}
            if snapshot_inside:
                ident["snapshot_id"] = BASE_SNAP
            out[obs] = [{"kind": "source_observation", "payload": ident, "args": [], "kw": {}}]
    if drift:
        out["obs_r0a"][0]["payload"]["geometry"] = [0.0, 1.5]
    return out


def test_observation_identity_check():
    base_obs, cand_obs = observations(), observations()
    result, _ = run(baseline_observations=base_obs, candidate_observations=cand_obs)
    assert result["PROVEN"] and result["observation_identity"]["identical"] == result["observation_identity"]["referenced"]
    drifted, _ = run(baseline_observations=base_obs, candidate_observations=observations(drift=True))
    assert not drifted["PROVEN"]
    scoped, _ = run(baseline_observations=observations(snapshot_inside=True),
                    candidate_observations=observations(snapshot_inside=True))
    assert not scoped["PROVEN"]
    absent = observations()
    del absent["obs_n0a"]
    missing, _ = run(baseline_observations=base_obs, candidate_observations=absent)
    assert not missing["PROVEN"]


def test_controls_discriminate_on_every_hashed_key():
    _, (base_report, cand_report, base_rec, cand_rec) = run()
    controls = proof.run_controls(base_report, cand_report, base_rec, cand_rec)
    assert controls["discriminating"]
    assert controls["controls"]["faithful_remap"] == 5
    assert controls["controls"]["baseline_snapshot_kept"] == 0
    perturbed = {k for k in controls["controls"] if k.startswith("perturb:")}
    assert {"perturb:gap_box_pt", "perturb:pattern", "perturb:structural_pattern", "perturb:viewport_id",
            "perturb:source_lineage_root_ids", "perturb:source_observation_ids",
            "perturb:page_id"} <= perturbed


def test_cli_exit_codes(tmp_path):
    def dump(name, obj):
        path = tmp_path / name
        path.write_text(json.dumps(obj), encoding="utf-8")
        return str(path)
    base_report, base_rec = world(BASE_SNAP)
    cand_report, cand_rec = world(CAND_SNAP)
    args = ["--baseline-stage", dump("bs.json", base_report), "--candidate-stage", dump("cs.json", cand_report),
            "--baseline-recording", dump("br.json", base_rec), "--candidate-recording", dump("cr.json", cand_rec),
            "--controls", "--out", str(tmp_path / "out.json")]
    assert proof.main(args) == 0
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))["PROVEN"] is True
    bad_report, bad_rec = world(CAND_SNAP, mutate=lambda items: items[0]["payload"].__setitem__("page_id", "p9"))
    args[args.index(str(tmp_path / "cs.json"))] = dump("cs2.json", bad_report)
    args[args.index(str(tmp_path / "cr.json"))] = dump("cr2.json", bad_rec)
    assert proof.main(args) == 1


# ---- recorder -------------------------------------------------------------------

def test_recorder_wrapper_returns_identical_ids_and_records_inputs(tmp_path):
    fake_tool = tmp_path / "fake_stage_tool.py"
    fake_tool.write_text(textwrap.dedent("""
        import json, sys
        from pb_migration_contracts import stable_contract_id
        payload = {"snapshot_id": "source_snapshot_aaaaaaaa", "source_observation_ids": ("b", "a")}
        ids = [stable_contract_id("physical_opening_raw_candidate", payload, digest_chars=32),
               stable_contract_id("physical_opening_candidate", {"k": 1}, digest_chars=32),
               stable_contract_id("unrelated_prefix", {"k": 2}, digest_chars=32)]
        open(sys.argv[1], "w").write(json.dumps(ids))
    """), encoding="utf-8")
    out_ids, out_rec = tmp_path / "ids.json", tmp_path / "rec.json"
    subprocess.run([sys.executable, "-m", "tools.record_candidate_id_inputs", "--recording-out", str(out_rec),
                    "--stage-tool", str(fake_tool), "--", str(out_ids)],
                   cwd=REPO_ROOT, check=True, capture_output=True, env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT)})
    ids = json.loads(out_ids.read_text(encoding="utf-8"))
    expected = [
        stable_contract_id("physical_opening_raw_candidate",
                           {"snapshot_id": "source_snapshot_aaaaaaaa", "source_observation_ids": ("b", "a")},
                           digest_chars=32),
        stable_contract_id("physical_opening_candidate", {"k": 1}, digest_chars=32),
        stable_contract_id("unrelated_prefix", {"k": 2}, digest_chars=32)
    ]
    assert ids == expected  # wrapper does not change any id
    recording = json.loads(out_rec.read_text(encoding="utf-8"))
    assert set(recording) == {expected[0], expected[1]}  # only candidate prefixes recorded
    record = recording[expected[0]][0]
    assert record["payload"]["source_observation_ids"] == ["b", "a"]
    # the recorded form re-hashes to the same id (faithfulness the prover depends on)
    assert stable_contract_id(record["kind"], record["payload"], *record["args"], **record["kw"]) == expected[0]


def test_set_valued_payload_is_not_reproduced_by_its_recording():
    # A set payload hashes through ``str(set)`` (hash-seed dependent) and its sorted-list
    # recording does not reproduce it.  Real candidate payloads hold only
    # dict/str/float/tuple/None, but the prover re-hashes every baseline id from its
    # recording first and refuses ("recording does not reproduce") rather than trusting it.
    payload = {"bag": frozenset({"y", "x"})}
    contract_id = stable_contract_id("physical_opening_candidate", payload, digest_chars=32)
    recorded = recorder._normalise(payload)
    assert recorded == {"bag": ["x", "y"]}
    assert stable_contract_id("physical_opening_candidate", recorded, digest_chars=32) != contract_id


def test_candidate_recording_that_disagrees_with_its_id_is_refused():
    # Belt and braces behind the re-hash: the candidate run's own recorded payload for a
    # mapped id must equal the baseline payload modulo snapshot_id.
    base_report, base_rec = world(BASE_SNAP)
    cand_report, cand_rec = world(CAND_SNAP)
    victim = cand_report["native_candidate_closures"][0]["unresolved_candidate_ids"][0]
    cand_rec[victim][0]["payload"]["source_observation_ids"] = ["obs_other"]
    result = proof.prove_snapshot_remap(base_report, cand_report, base_rec, cand_rec)
    assert not result["PROVEN"]
    assert any("differs beyond snapshot_id" in f["reason"] for f in result["failures"])


def test_unresolved_observation_inventory_change_is_refused():
    base_report, base_rec = world(BASE_SNAP)
    cand_report, cand_rec = world(CAND_SNAP)
    cand_report["raster_candidate_closures"][0]["unresolved_observation_ids"].append("obs_unrelated")
    result = proof.prove_snapshot_remap(base_report, cand_report, base_rec, cand_rec)
    assert not result["PROVEN"]
    assert any("observation inventory" in f["reason"] for f in result["failures"])
