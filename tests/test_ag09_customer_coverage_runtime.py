from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pb_auto_geometry_v1219 as auto
from pb_migration_contracts import QuantityEvidence
from pb_takeoff_coverage_registry import (
    ENUMERATION_COMPLETE,
    CoverageRegistryRunManifestV1,
    ProducerObjectUniverseSnapshotV1,
    QuantityEvidenceUniverseSnapshotV1,
    TakeoffOutputRowUniverseSnapshotV1,
    build_coverage_registry_v1,
)
from pb_takeoff_output_authority import TakeoffOutputRow


SHA = "c" * 64
OBJ_KEY = ("physical_wall", "wall")
QE_KEY = ("wall_quantity", "live")
ROW_KEY = ("takeoff_rows", "live")


def _summary():
    manifest = CoverageRegistryRunManifestV1(
        source_document_id="doc-live",
        revision_id="rev-live",
        source_sha256=SHA,
        registry_run_id="run-live",
        snapshot_id="snap-live",
        expected_object_universe_keys=(OBJ_KEY,),
        expected_quantity_evidence_universe_keys=(QE_KEY,),
        expected_takeoff_row_universe_keys=(ROW_KEY,),
    )
    obj = ProducerObjectUniverseSnapshotV1(
        producer=OBJ_KEY[0],
        owning_authority="physical_wall_existence_authority",
        category=OBJ_KEY[1],
        source_document_id="doc-live",
        revision_id="rev-live",
        source_sha256=SHA,
        registry_run_id="run-live",
        snapshot_id="snap-live",
        admitted_object_ids=("wall-live-1",),
        enumeration_status=ENUMERATION_COMPLETE,
    )
    quantity = QuantityEvidence(
        quantity_id="qty-live-1",
        family="wall_area",
        semantic_key="wall_area:qty-live-1",
        value=12.5,
        unit="M2",
        input_entity_ids=("wall-live-1",),
        evidence_ids=("evidence-live-1",),
        authority="physical_net_wall",
        status="corroborated",
        confidence=0.95,
    )
    qe_snapshot = QuantityEvidenceUniverseSnapshotV1(
        producer=QE_KEY[0],
        source=QE_KEY[1],
        source_document_id="doc-live",
        revision_id="rev-live",
        source_sha256=SHA,
        registry_run_id="run-live",
        snapshot_id="snap-live",
        quantity_ids=("qty-live-1",),
        enumeration_status=ENUMERATION_COMPLETE,
    )
    output = TakeoffOutputRow(
        quantity_id="qty-live-1",
        description="net wall area",
        value=12.5,
        unit="M2",
        geometry_ref="wall-live-1",
        is_publishable=False,
    )
    row_snapshot = TakeoffOutputRowUniverseSnapshotV1(
        source=ROW_KEY[0],
        collection=ROW_KEY[1],
        source_document_id="doc-live",
        revision_id="rev-live",
        source_sha256=SHA,
        registry_run_id="run-live",
        snapshot_id="snap-live",
        quantity_ids=("qty-live-1",),
        enumeration_status=ENUMERATION_COMPLETE,
    )
    return build_coverage_registry_v1(
        manifest=manifest,
        object_universe_snapshots=(obj,),
        quantity_evidence_universe_snapshots=(qe_snapshot,),
        takeoff_output_row_universe_snapshots=(row_snapshot,),
        quantity_evidence_by_universe={QE_KEY: (quantity,)},
        takeoff_rows_by_universe={ROW_KEY: (output,)},
        object_metadata_by_id={
            "wall-live-1": {
                "object_type": "wall",
                "geometry_ids": ["wall-live-1"],
                "source_pages": [1],
                "evidence_ids": ["evidence-live-1"],
            }
        },
    )


class _App:
    def __init__(self, summary=None):
        self.takeoff_coverage_registry_summaries = (
            [summary] if summary is not None else []
        )

    def lquery(self, sql, params=()):
        if "FROM pages" in sql:
            return []
        if "FROM takeoff_rows" in sql:
            return [
                {
                    "id": 17,
                    "source_reference": (
                        f"{auto.SOURCE_PREFIX} · physical_net_wall:qty-live-1"
                    ),
                    "quantity": 12.5,
                    "unit": "m²",
                    "quantity_status": "Measured",
                    "row_role": "external_wall",
                }
            ]
        return []

    def now_stamp(self):
        return "stamp"


@contextmanager
def _publication(app, workspace_id, rows):
    yield app


def test_analyse_workspace_persists_live_five_stage_coverage_payload():
    app = _App(_summary())
    saved = {}

    def capture_setting(_app, _workspace_id, report):
        saved.update(report)

    with (
        patch.object(auto, "_auto_publication", _publication),
        patch.object(auto, "_refresh_auto_model", return_value=None),
        patch.object(auto, "_setting_set", side_effect=capture_setting),
        patch.object(auto, "_detect_footprint", return_value=None),
        patch.object(auto, "_cross_calibrate_elevations", return_value=None),
        patch.object(auto, "_build_unit_rows", return_value=([], [])),
        patch.object(auto, "_build_facade_rows", return_value=([], [])),
        patch.object(
            auto,
            "_build_internal_partition_rows",
            return_value=([], []),
        ),
        patch.object(
            auto,
            "_build_bound_wall_finish_rows",
            return_value=([], []),
        ),
    ):
        report = auto.analyse_workspace(app, 1)

    coverage = report["coverage_lifecycle"]
    assert coverage == saved["coverage_lifecycle"]
    assert coverage["status"] == "coverage_registry_scope_available"
    assert coverage["expected_family_completeness"] == "UNKNOWN"
    assert coverage["stage_counts"] == {
        "DETECTED": 1,
        "AUTHENTICATED": 1,
        "CANONICALIZED": 1,
        "QUANTIFIED": 1,
        "PUBLISHED": 1,
    }
    obj = coverage["registry_reports"][0]["object_reports"][0]
    assert obj["object_id"] == "wall-live-1"
    assert obj["highest_stage_reached"] == "PUBLISHED"
    assert obj["died_at_stage"] is None


def test_analyse_workspace_reports_unavailable_when_no_live_registry_exists():
    app = _App()
    saved = {}

    def capture_setting(_app, _workspace_id, report):
        saved.update(report)

    with (
        patch.object(auto, "_auto_publication", _publication),
        patch.object(auto, "_refresh_auto_model", return_value=None),
        patch.object(auto, "_setting_set", side_effect=capture_setting),
        patch.object(auto, "_detect_footprint", return_value=None),
        patch.object(auto, "_cross_calibrate_elevations", return_value=None),
        patch.object(auto, "_build_unit_rows", return_value=([], [])),
        patch.object(auto, "_build_facade_rows", return_value=([], [])),
        patch.object(
            auto,
            "_build_internal_partition_rows",
            return_value=([], []),
        ),
        patch.object(
            auto,
            "_build_bound_wall_finish_rows",
            return_value=([], []),
        ),
    ):
        report = auto.analyse_workspace(app, 1)

    coverage = report["coverage_lifecycle"]
    assert coverage == saved["coverage_lifecycle"]
    assert coverage["status"] == "unavailable"
    assert coverage["stage_counts"]["DETECTED"] is None
    assert coverage["stage_counts"]["PUBLISHED"] is None
