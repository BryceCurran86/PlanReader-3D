"""RETIRED legacy benchmark schema compatibility shim.

Project identity contracts moved to pb_project_identity_models. Legacy scoring
schemas are intentionally unavailable.
"""
from pb_project_identity_models import ProjectIdentity, SourceManifest

RETIRED = True
__all__ = ["ProjectIdentity", "SourceManifest", "RETIRED"]


def __getattr__(name: str):
    raise RuntimeError(f"pb_benchmark_schema.{name} is retired")
