"""Retired legacy benchmark CLI guard."""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "Legacy PlanReader benchmark CLI is retired. "
        "Use benchmarks/frozen_holdout/full_plan_v2/run_baseline.py "
        "and V2 truth/coverage tooling.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
