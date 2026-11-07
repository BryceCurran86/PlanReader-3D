"""Study B step 3: apply the PRE-REGISTERED decision rules (Part A4) to the per-document analysis files.

usage: python tools/item8_b/b_aggregate.py <analysis_json> [<analysis_json> ...]   (one per document, from b_analyse.py)

Counts only. Refuses any analysis whose status is not "complete"."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.item8_b.b_core import decide  # noqa: E402


def main(paths: list[str]) -> int:
    analyses = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    stats = {}
    for a in analyses:
        c = a["label_counts"]
        print("DOCUMENT %s p%s: status %s | marks %d, picked unique %d (duplicates %d), no outline fits %d, "
              "no containing structure %d, more than one containing %d" % (
                  a["label"], a["page"], a["status"], c["marks"], c["picked_unique"], c["picked_duplicates"],
                  c["no_outline_fits"], c["no_containing_structure"], c["more_than_one_containing"]))
        if a["status"] != "complete":
            print("   REFUSED:", a["problems"])
            return 2
        stats[a["label"]] = a["stats"]
        s = a["stats"]
        print("   R-A items %d, interior ink outside the face-line paint range in %d" % (s["with_interior"], s["r_a_true"]))
        print("   R-B items %d from %d structures, decisive %d [nearer interior %d, nearer wall %d], ties %d" % (
            s["b_items"], s["b_structures"], s["b_decisive"], s["b_nearer_interior"], s["b_nearer_wall"], s["b_tie"]))
        print("   R-C items %d from %d structures, same style as a face line %d" % (s["c_items"], s["c_structures"], s["c_same"]))
    for name, verdict in decide(stats).items():
        print("%s: %s" % (name, json.dumps(verdict, sort_keys=True)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
