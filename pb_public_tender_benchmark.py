"""RETIRED legacy public-tender benchmark loader.

Public-tender percentage scoring is no longer an active PlanReader validation
system. This tombstone exists only so isolation checks can identify forbidden
legacy dependencies.
"""
RETIRED = True


def __getattr__(name: str):
    raise RuntimeError(
        f"pb_public_tender_benchmark.{name} is retired; use Full Plan V2 truth"
    )
