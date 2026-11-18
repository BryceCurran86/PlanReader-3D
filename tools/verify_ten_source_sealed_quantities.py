#!/usr/bin/env python3
"""Verify exactly ten source-sealed, customer-projected quantities.

Loads sealed + customer packets, proves bijection via
``verify_sealed_customer_output``, and emits a private receipt listing ten
non-abstained verified quantity IDs. Does not invent metric values, does not
mutate packets, and does not touch frozen benchmarks.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pb_customer_output_verification import (  # noqa: E402
    CustomerOutputVerificationError,
    verify_sealed_customer_output,
)
from pb_source_closed_run_export import sealed_source_closed_run_from_dict  # noqa: E402
from pb_topology_metric_seal_gate import (  # noqa: E402
    assess_acacia_p2_title_block_only_gate,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _quantity_rows(sealed: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = sealed.get("quantities")
    if not isinstance(rows, list):
        raise ValueError(f"sealed packet missing quantities list: {sealed.get('project_id')!r}")
    return [row for row in rows if isinstance(row, Mapping)]


def collect_verified_items(
    *,
    sealed_path: Path,
    customer_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sealed = _load_json(sealed_path)
    customer = _load_json(customer_path)
    if not isinstance(sealed, Mapping):
        raise ValueError(f"sealed packet must be an object: {sealed_path}")
    if not isinstance(customer, list):
        raise ValueError(f"customer packet must be a list: {customer_path}")

    verification = verify_sealed_customer_output(
        sealed_source_closed_run_from_dict(sealed),
        customer,
    )
    verified_ids = set(verification.verified_quantity_ids)
    items: list[dict[str, Any]] = []
    for row in _quantity_rows(sealed):
        if row.get("abstained"):
            continue
        qid = str(row.get("quantity_id") or "")
        if qid not in verified_ids:
            continue
        items.append(
            {
                "project_id": sealed.get("project_id"),
                "quantity_id": qid,
                "family": row.get("family"),
                "status": row.get("status"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "authority": row.get("authority"),
                "source_sha256s": list(sealed.get("source_sha256s") or []),
                "revision_ids": list(sealed.get("revision_ids") or []),
                "run_id": sealed.get("run_id"),
                "fingerprint": sealed.get("fingerprint"),
                "sealed_path": str(sealed_path),
                "customer_path": str(customer_path),
                "verified": True,
            }
        )
    return verification.to_dict(), items


def select_ten(
    pools: Sequence[tuple[Path, Path]],
    *,
    required: int = 10,
) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    project_summaries: list[dict[str, Any]] = []
    for sealed_path, customer_path in pools:
        summary, items = collect_verified_items(
            sealed_path=sealed_path,
            customer_path=customer_path,
        )
        project_summaries.append(
            {
                "sealed_path": str(sealed_path),
                "customer_path": str(customer_path),
                **summary,
                "live_verified_count": len(items),
            }
        )
        for item in items:
            if len(selected) >= required:
                break
            selected.append(item)
        if len(selected) >= required:
            break

    acacia_gate = assess_acacia_p2_title_block_only_gate(
        topology_candidate_count=33,
    ).to_dict()

    return {
        "required": required,
        "selected_count": len(selected),
        "complete": len(selected) >= required,
        "selected": selected[:required],
        "project_summaries": project_summaries,
        "acacia_p2_metric_seal_gate": acacia_gate,
        "authority_note": (
            "Selected items are existing source-sealed, customer-verified quantities. "
            "Acacia p2 topology remains blocked: title-block 1:100 alone is not FIRM "
            "measurement authority."
        ),
    }


def _default_pools(packet_root: Path) -> list[tuple[Path, Path]]:
    return [
        (
            packet_root / "sealed" / "au_qld_lot16_power.json",
            packet_root / "customer" / "au_qld_lot16_power.customer_rows.json",
        ),
        (
            packet_root / "sealed" / "au_qld_q5446_armstrong32_harlequin.json",
            packet_root / "customer" / "au_qld_q5446_armstrong32_harlequin.customer_rows.json",
        ),
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet-root",
        type=Path,
        default=Path(r"C:\Users\bryce\private_packets\four_project_e2e_score_20261116"),
        help="Private packet root containing sealed/ and customer/ folders",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON receipt to this path",
    )
    parser.add_argument("--required", type=int, default=10)
    args = parser.parse_args(list(argv) if argv is not None else None)

    pools = [
        (sealed, customer)
        for sealed, customer in _default_pools(args.packet_root)
        if sealed.is_file() and customer.is_file()
    ]
    if not pools:
        print(f"ERROR: no sealed/customer pairs under {args.packet_root}", file=sys.stderr)
        return 2

    try:
        receipt = select_ten(pools, required=int(args.required))
    except (CustomerOutputVerificationError, ValueError, TypeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(receipt, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)

    if not receipt["complete"]:
        print(
            f"ERROR: only {receipt['selected_count']}/{receipt['required']} verified sealed items",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
