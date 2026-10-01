"""RETIRED legacy holdout registry tombstone.

Full Plan V2 truth integrity is validated by scripts/check_full_plan_v2_integrity.py.
"""
RETIRED = True


def __getattr__(name: str):
    raise RuntimeError(f"pb_holdout_suite_registry.{name} is retired; use Full Plan V2")
