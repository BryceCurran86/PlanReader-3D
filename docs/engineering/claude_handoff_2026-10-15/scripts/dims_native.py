import sys, json
sys.modules["rapidocr"]=None; sys.modules["onnxruntime"]=None
sys.path.insert(0,"C:/claude-work/ft3-p11-p7")
import fitz
from pb_figured_dimension_evidence import extract_dimension_evidence_bundle
doc=fitz.open("C:/claude-work/ft3-p11-p7/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
b=extract_dimension_evidence_bundle(doc[10],page_num=11)
print(type(b), [a for a in dir(b) if not a.startswith("_")][:40])
print(len(b.observations),len(b.bindings))
obs=[o for o in b.observations]
print(type(obs[0]), [a for a in dir(obs[0]) if not a.startswith("_")][:30])
for o in obs:
    t=str(getattr(o,"text",getattr(o,"raw_text","")))
    if t.strip() in ("3297","4025","3950","6425","2536","3570"):
        print(t, {k:getattr(o,k,None) for k in ("orientation","bbox","value_mm","observation_id")})
bd=b.bindings
print(type(bd[0]), [a for a in dir(bd[0]) if not a.startswith("_")][:30])
print("----")
for o in obs:
    t=str(o.raw_text).strip()
    if t in ("3297","4025","3950","6425","3570","2536"):
        print(t,o.orientation,"endpoints",[[round(v,2) for v in p] for p in o.endpoints] if o.endpoints else None,"conflict",o.conflict_state,"bound",o.bound_geometry_id is not None)
