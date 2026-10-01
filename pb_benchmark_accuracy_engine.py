"""RETIRED legacy PlanReader percentage benchmark evaluator.

The active validation system is Full Plan V2 source-closed truth. This module is
kept only as a dependency-isolation tombstone so old imports fail clearly.
"""
from __future__ import annotations

import sys

RETIRED = True
GOLD_TOKEN = "RETIRED_LEGACY_BENCHMARK"


def main(argv: list[str] | None = None) -> int:
    del argv
    print(
        "Legacy benchmark evaluator is retired. Use "
        "benchmarks/frozen_holdout/full_plan_v2 and V2 validation tooling.",
        file=sys.stderr,
    )
    return 2


def __getattr__(name: str):
    raise RuntimeError(
        f"pb_benchmark_accuracy_engine.{name} is retired; use Full Plan V2 validation"
    )


if __name__ == "__main__":
    raise SystemExit(main())
