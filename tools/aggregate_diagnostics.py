import json
from collections import Counter, defaultdict
from typing import Any, Mapping


def aggregate_diag(diag_map: Mapping[Any, Mapping[str, Any]]) -> dict[str, Any]:
    by_stage: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for diag in diag_map.values():
        stage = str(diag.get("stage", "unknown"))
        by_stage[stage].append(diag)

    summary: dict[str, Any] = {}
    for stage, items in sorted(by_stage.items()):
        reason_counts: Counter[tuple[str, ...]] = Counter()
        snapshot_counts: Counter[str] = Counter()
        examples: list[dict[str, Any]] = []
        for item in items:
            reason = tuple(
                str(v)
                for v in (
                    item.get("binding_reason_codes")
                    or item.get("pre_boundary_reasons")
                    or item.get("reason_codes")
                    or ("NO_REASON",)
                )
            )
            reason_counts[reason] += 1
            snapshot_id = item.get("snapshot_id")
            if snapshot_id is not None:
                snapshot_counts[str(snapshot_id)] += 1
            if len(examples) < 5:
                examples.append(
                    {
                        "document_id": item.get("document_id"),
                        "revision_id": item.get("revision_id"),
                        "decision_scope_id": item.get("decision_scope_id"),
                        "candidate_id": item.get("candidate_id")
                        or item.get("opening_id")
                        or item.get("scope_id"),
                    }
                )
        summary[stage] = {
            "count": len(items),
            "top_reasons": reason_counts.most_common(10),
            "snapshots": snapshot_counts.most_common(5),
            "examples": examples,
        }
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Aggregate diagnostic result maps.")
    parser.add_argument("input", help="Path to JSON file containing diagnostic payload")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    payload = data if isinstance(data, dict) else {"records": data}
    if isinstance(payload, dict) and "records" in payload:
        result = aggregate_diag(payload["records"])
    else:
        result = aggregate_diag(payload)

    print(json.dumps(result, indent=2, sort_keys=True))
