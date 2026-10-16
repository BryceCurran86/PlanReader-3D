"""Exercise the changed retention assertions of #2778 (Lot16 job) and its Maryborough equality, on synthetic reports.

Re-implements the two snippets from the workflow verbatim (old and new variants) around the repo's real assert_unchanged_or_declared.
"""
import copy
import sys

sys.path.insert(0, r"C:\claude-work\rev-main")
from tools.declared_additive_source_retention import assert_unchanged_or_declared  # noqa: E402

keyed = lambda rows: {row["opening_identity_id"]: row for row in rows}  # noqa: E731


def lot16_old(baseline, report):
    old_b, new_b = keyed(baseline["opening_bindings"]), keyed(report["opening_bindings"])
    assert set(new_b) <= set(old_b)
    if not all(old_b[k] == row for k, row in new_b.items()):
        assert_unchanged_or_declared(baseline, report, message="original opening binding receipt changed")
    old_f, new_f = keyed(baseline["host_frames"]), keyed(report["host_frames"])
    assert set(old_f) <= set(new_f)
    if not all(new_f[k] == row for k, row in old_f.items() if row["record_id"]):
        assert_unchanged_or_declared(baseline, report, message="original framed host receipt changed")


def lot16_new(baseline, report):
    old_b, new_b = keyed(baseline["opening_bindings"]), keyed(report["opening_bindings"])
    assert set(old_b) <= set(new_b), "authenticated opening identity removed"
    if old_b != new_b:
        assert_unchanged_or_declared(baseline, report, message="original opening binding receipt changed")
    old_f, new_f = keyed(baseline["host_frames"]), keyed(report["host_frames"])
    assert set(old_f) <= set(new_f)
    if old_f != new_f:
        assert_unchanged_or_declared(baseline, report, message="original framed host receipt changed")


def base_report():
    return {
        "source_sha256": "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844",
        "opening_bindings": [{"opening_identity_id": f"o{i}", "record_id": f"rec{i}", "host_wall_id": f"w{i}"} for i in range(3)],
        "host_frames": [{"opening_identity_id": f"o{i}", "record_id": f"fr{i}" if i < 2 else None, "status": "corroborated" if i < 2 else "abstained"}
                        for i in range(3)],
        "summary": {},
    }


def outcome(fn, baseline, report):
    try:
        fn(baseline, report)
        return "PASS"
    except AssertionError as exc:
        return f"AssertionError({str(exc)[:46]})"
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}({str(exc)[:46]})"


mutations = {}
b = base_report()
mutations["identical"] = copy.deepcopy(b)
r = copy.deepcopy(b); del r["opening_bindings"][0]; mutations["binding REMOVED"] = r
r = copy.deepcopy(b); r["opening_bindings"].append({"opening_identity_id": "o9", "record_id": "rec9", "host_wall_id": "w9"}); mutations["binding ADDED"] = r
r = copy.deepcopy(b); r["opening_bindings"][1]["host_wall_id"] = "other"; mutations["binding CHANGED"] = r
r = copy.deepcopy(b); del r["host_frames"][0]; mutations["proved frame REMOVED"] = r
r = copy.deepcopy(b); r["host_frames"][0]["record_id"] = "changed"; mutations["proved frame CHANGED"] = r
r = copy.deepcopy(b); r["host_frames"][2]["status"] = "corroborated"; mutations["UNPROVED frame changed"] = r
r = copy.deepcopy(b); r["host_frames"].append({"opening_identity_id": "o9", "record_id": None, "status": "abstained"}); mutations["frame ADDED"] = r

print(f"{'mutation':26s} | {'OLD logic':52s} | NEW logic (#2778)")
for name, report in mutations.items():
    print(f"{name:26s} | {outcome(lot16_old, b, report):52s} | {outcome(lot16_new, b, report)}")
