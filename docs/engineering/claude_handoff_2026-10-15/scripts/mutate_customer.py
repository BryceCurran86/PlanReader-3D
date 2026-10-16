"""Mutation probe: verify_sealed_customer_output on REAL archived signed runs/customer rows under a chosen code tree (argv[1])."""
import copy, json, sys
from pathlib import Path
tree = sys.argv[1]
sys.path.insert(0, tree)
sys.modules["rapidocr"] = None
sys.modules["onnxruntime"] = None
from scripts.report_full_plan_v2_readiness import _parse_evidence_json  # noqa: E402
from pb_customer_output_verification import CustomerOutputVerificationError, verify_sealed_customer_output  # noqa: E402
from pb_source_closed_run_export import sealed_source_closed_run_from_dict  # noqa: E402

ROOT = Path("C:/claude-work/audit-out/gpt3rev")
CASES = {
    "lot16": (ROOT / "lot16/production/source_sealed_run.json", ROOT / "lot16/production/verified_customer_rows.json"),
    "maryborough": (ROOT / "mary/source/production/source_sealed_run.json", ROOT / "mary/source/production/verified_customer_rows.json"),
}


def outcome(sealed, rows):
    try:
        v = verify_sealed_customer_output(sealed, rows)
        return "OK:%d" % len(v.verified_quantity_ids)
    except CustomerOutputVerificationError as e:
        return "CustomerOutputVerificationError:" + str(e)[:80]
    except Exception as e:  # noqa: BLE001
        return type(e).__name__ + ":" + str(e)[:80]


def notes_obj(row):
    return json.loads(row["notes"]) if isinstance(row.get("notes"), str) and row["notes"].strip().startswith("{") else None


res = {}
for name, (sp, rp) in CASES.items():
    sealed = sealed_source_closed_run_from_dict(_parse_evidence_json(sp.read_text(encoding="utf-8")))
    rows = _parse_evidence_json(rp.read_text(encoding="utf-8"))
    r0 = rows[0]
    out = {"baseline_unmodified": outcome(sealed, rows)}
    has_notes = isinstance(r0.get("notes"), str) and r0["notes"].strip() != ""
    out["row_shape"] = {"keys": sorted(r0.keys()), "has_quantity_id": "quantity_id" in r0, "has_direct_provenance": "commercial_projection_provenance" in r0, "notes_is_json_object": notes_obj(r0) is not None}

    def mutated(fn):
        rs = copy.deepcopy(rows)
        fn(rs)
        return outcome(sealed, rs)

    def add_to_notes(rs, literal):
        n = rs[0]["notes"]
        rs[0]["notes"] = n[:-1] + ',"unexpected_metadata":' + literal + "}"

    out["notes_plus_NaN"] = mutated(lambda rs: add_to_notes(rs, "NaN"))
    out["notes_plus_Infinity"] = mutated(lambda rs: add_to_notes(rs, "Infinity"))
    out["notes_plus_1e10000"] = mutated(lambda rs: add_to_notes(rs, "1e10000"))
    out["notes_plus_400digit_int"] = mutated(lambda rs: add_to_notes(rs, "9" * 400))
    out["notes_plus_duplicate_key"] = mutated(lambda rs: rs[0].__setitem__("notes", rs[0]["notes"][:-1] + ',"adapter":"commercial_takeoff"}'))
    out["notes_depth_513"] = mutated(lambda rs: add_to_notes(rs, "[" * 513 + "0" + "]" * 513))
    out["notes_depth_100_legit"] = mutated(lambda rs: add_to_notes(rs, "[" * 100 + "0" + "]" * 100))
    out["notes_truncated_json"] = mutated(lambda rs: rs[0].__setitem__("notes", rs[0]["notes"][:-5]))
    out["notes_bad_escape"] = mutated(lambda rs: rs[0].__setitem__("notes", rs[0]["notes"].replace('"adapter"', '"ad\\qapter"', 1)))
    out["duplicate_row_identity"] = mutated(lambda rs: rs.append(copy.deepcopy(rs[0])))
    out["drop_row"] = mutated(lambda rs: rs.pop())
    out["notes_only_row_(no_quantity_id,no_direct)"] = mutated(lambda rs: [rs[0].pop("quantity_id", None), rs[0].pop("commercial_projection_provenance", None)])

    def swap_revision(rs):
        p = rs[0].get("commercial_projection_provenance")
        if isinstance(p, dict):
            s = json.dumps(p)
            rs[0]["commercial_projection_provenance"] = json.loads(s.replace('source_revision', 'source_revisionX', 1)) if "source_revision" in s else p
        n = notes_obj(rs[0])
        if n is not None:
            n2 = json.loads(json.dumps(n).replace("revision", "revisionX", 1))
            rs[0]["notes"] = json.dumps(n2)
    out["revision_key_corrupted"] = mutated(swap_revision)
    out["manual_row_freetext_notes_added"] = mutated(lambda rs: rs.append({"description": "manual estimator row", "notes": "free text [not json] {x}", "quantity": 1}))
    out["manual_row_nan_notes_added"] = mutated(lambda rs: rs.append({"description": "manual", "notes": '{"x": NaN}', "quantity": 1}))
    res[name] = out
print(json.dumps(res, indent=1, sort_keys=True))
