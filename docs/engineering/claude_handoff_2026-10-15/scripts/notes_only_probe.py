import copy, json, sys
from pathlib import Path
tree=sys.argv[1]; sys.path.insert(0,tree); sys.modules["rapidocr"]=None; sys.modules["onnxruntime"]=None
from scripts.report_full_plan_v2_readiness import _parse_evidence_json
from pb_customer_output_verification import CustomerOutputVerificationError, verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
R=Path("C:/claude-work/audit-out/gpt3rev")
for name,(sp,rp) in {"lot16":(R/"lot16/production/source_sealed_run.json",R/"lot16/production/verified_customer_rows.json"),"maryborough":(R/"mary/source/production/source_sealed_run.json",R/"mary/source/production/verified_customer_rows.json")}.items():
    sealed=sealed_source_closed_run_from_dict(_parse_evidence_json(sp.read_text(encoding="utf-8")))
    rows=_parse_evidence_json(rp.read_text(encoding="utf-8"))
    def run(lit):
        rs=copy.deepcopy(rows)
        for r in rs: r.pop("commercial_projection_provenance",None)      # legacy notes-only rows
        if lit is not None: rs[0]["notes"]=rs[0]["notes"][:-1]+',"unexpected_metadata":'+lit+"}"
        try: return "OK:%d"%len(verify_sealed_customer_output(sealed,rs).verified_quantity_ids)
        except CustomerOutputVerificationError as e: return "CustomerOutputVerificationError:"+str(e)[:70]
        except Exception as e: return type(e).__name__+":"+str(e)[:70]
    print(name,"legacy notes-only unmodified:",run(None))
    for lit in ("NaN","Infinity","1e10000","9"*400): print(name,"notes-only +",lit[:12],":",run(lit))
