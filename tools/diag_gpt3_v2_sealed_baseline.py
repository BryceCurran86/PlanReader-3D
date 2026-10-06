from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path


def audit(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    quantities=payload.get("quantities") or []
    family=Counter()
    authority=Counter()
    unit=Counter()
    duplicate_identity_refs=defaultdict(list)
    duplicate_quantity_ids=Counter()
    zero_non_abstained=[]
    bad_lineage=[]
    abstained=[]
    no_identity=[]
    rows=[]
    for q in quantities:
        qid=str(q.get("quantity_id") or "")
        fam=str(q.get("family") or "")
        family[fam]+=1
        authority[str(q.get("authority") or "")]+=1
        unit[str(q.get("unit") or "")]+=1
        duplicate_quantity_ids[qid]+=1
        refs=tuple(sorted(str(x) for x in (q.get("object_identity_refs") or ()) if str(x)))
        if refs:
            duplicate_identity_refs[(fam,refs)].append(qid)
        else:
            no_identity.append(qid)
        value=q.get("value")
        if not q.get("abstained",False) and value is not None and float(value)==0.0:
            zero_non_abstained.append(qid)
        if not bool(q.get("lineage_ok",False)):
            bad_lineage.append(qid)
        if bool(q.get("abstained",False)):
            abstained.append(qid)
        rows.append({
            "quantity_id":qid,
            "family":fam,
            "semantic_key":q.get("semantic_key"),
            "value":value,
            "unit":q.get("unit"),
            "authority":q.get("authority"),
            "abstained":bool(q.get("abstained",False)),
            "lineage_ok":bool(q.get("lineage_ok",False)),
            "object_identity_refs":list(refs),
            "evidence_refs":q.get("evidence_refs") or [],
        })
    duplicate_ref_groups=[
        {"family":fam,"object_identity_refs":list(refs),"quantity_ids":ids}
        for (fam,refs),ids in duplicate_identity_refs.items()
        if len(ids)>1
    ]
    duplicate_ids=[qid for qid,n in duplicate_quantity_ids.items() if qid and n>1]
    return {
        "project_id":payload.get("project_id"),
        "run_id":payload.get("run_id"),
        "fingerprint":payload.get("fingerprint"),
        "source_sha256s":payload.get("source_sha256s"),
        "quantity_count":len(quantities),
        "family_counts":dict(family.most_common()),
        "authority_counts":dict(authority.most_common()),
        "unit_counts":dict(unit.most_common()),
        "abstained_count":len(abstained),
        "lineage_conflict_count":len(bad_lineage),
        "zero_non_abstained_count":len(zero_non_abstained),
        "missing_identity_count":len(no_identity),
        "duplicate_quantity_id_count":len(duplicate_ids),
        "duplicate_identity_group_count":len(duplicate_ref_groups),
        "duplicate_quantity_ids":duplicate_ids,
        "duplicate_identity_groups":duplicate_ref_groups,
        "bad_lineage_quantity_ids":bad_lineage,
        "zero_non_abstained_quantity_ids":zero_non_abstained,
        "missing_identity_quantity_ids":no_identity,
        "quantities":rows,
    }


def main():
    root=Path("artifacts/gpt3-v2-baseline")
    projects=[
        "au_qld_maryborough_service_station",
        "au_qld_lot16_power",
    ]
    result={}
    for project in projects:
        path=root/f"{project}.json"
        result[project]=audit(path)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
