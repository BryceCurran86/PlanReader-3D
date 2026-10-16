"""Print the comparison table for stage reports produced by counterfactual_stage.py.

usage: python summarize_counterfactuals.py <dir containing stage_<mode>.json files>
"""
import collections
import json
import os
import sys

directory = sys.argv[1]
for mode in ("baseline", "scale", "eligible", "eligible_wall_layer", "boundary_scale"):
    path = os.path.join(directory, f"stage_{mode}.json")
    if not os.path.exists(path):
        continue
    report = json.load(open(path, encoding="utf-8"))
    summary = report["summary"]
    scope = report["source_owned_wall_scopes"][0]
    equivalence = scope["equivalence"]
    bindings = report["opening_bindings"]
    pairs = collections.Counter(p[2] for p in equivalence["pair_classifications"])
    tainted = len(scope["boundary_evaluation"]["boundary_tainted_wall_candidate_ids"])
    print(f"== {mode:20s} hosts={summary['authenticated_hosts']} tainted={tainted} "
          f"scope_complete={scope['scope_complete']} representatives={len(equivalence['representative_wall_ids'])} "
          f"ambiguous_walls={len(equivalence['ambiguous_wall_ids'])}")
    print("     pair classes:", dict(pairs))
    print("     binding status:", dict(collections.Counter(b.get("status") for b in bindings)))
    print("     corroborated openings:", [b["opening_identity_id"][-8:] for b in bindings if b.get("status") == "corroborated"])
