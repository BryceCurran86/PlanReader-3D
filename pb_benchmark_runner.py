"""RETIRED legacy golden-plan benchmark runner.

The only active PlanReader benchmark/validation framework is Full Plan V2.
"""
from __future__ import annotations

import sys

RETIRED = True


def main(argv: list[str] | None = None) -> int:
    del argv
    print(
        "Legacy benchmark runner is retired. Use Full Plan V2 validation tooling.",
        file=sys.stderr,
    )
    return 2


def __getattr__(name: str):
    raise RuntimeError(f"pb_benchmark_runner.{name} is retired")


if __name__ == "__main__":
    raise SystemExit(main())
