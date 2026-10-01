"""Takeoff Coverage Audit Adapter and Pipeline Lifecycle Audit (AG-09).

Traces building objects through the complete PlanReader lifecycle:
DETECTED -> AUTHENTICATED -> MODELED -> QUANTIFIED -> PUBLISHED -> DISPLAYED

Identifies and flags objects that drop out ("die") between any stages.
Ensures that coverage auditing is a strict DEVELOPMENT/QA verification capability,
never a customer hallucination mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import unittest

from pb_audit_coverage_record import (
    AuditObjectRecord,
    CoverageState,
    REFUSED_PHYSICAL_STATES,
)
from pb_migration_contracts import QuantityEvidence
from pb_takeoff_coverage_audit_adapter import (
    RegistryCoverageRecordProviderV1,
    REASON_NOT_IN_REGISTRY_UNIVERSE,
    REASON_SCENE_OBJECT_ID_MISSING,
)
from pb_takeoff_coverage_registry import (
    COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY,
    ENUMERATION_COMPLETE,
    EXPECTED_FAMILY_COMPLETENESS_UNKNOWN,
    CoverageRegistryRunManifestV1,
    CoverageRegistrySummaryV1,
    ProducerObjectUniverseSnapshotV1,
    QuantityEvidenceUniverseSnapshotV1,
    TakeoffOutputRowUniverseSnapshotV1,
    build_coverage_registry_v1,
)
from pb_takeoff_output_authority import TakeoffOutputRow


class TakeoffLifecycleStage(str, Enum):
    DETECTED = "DETECTED"
    AUTHENTICATED = "AUTHENTICATED"
    MODELED = "MODELED"
    QUANTIFIED = "QUANTIFIED"
    PUBLISHED = "PUBLISHED"
    DISPLAYED = "DISPLAYED"


LIFECYCLE_STAGE_ORDER = (
    TakeoffLifecycleStage.DETECTED,
    TakeoffLifecycleStage.AUTHENTICATED,
    TakeoffLifecycleStage.MODELED,
    TakeoffLifecycleStage.QUANTIFIED,
    TakeoffLifecycleStage.PUBLISHED,
    TakeoffLifecycleStage.DISPLAYED,
)

SHA = "a" * 64
OBJ_KEY = ("physical_wall", "wall")
QE_KEY = ("wall_quantity", "shadow")
ROW_KEY = ("takeoff_rows", "shadow")


@dataclass(frozen=True)
class ObjectLifecycleReport:
    """Audit report for an individual building object across the 6 pipeline stages."""
    object_id: str
    object_type: str
    highest_stage_reached: TakeoffLifecycleStage
    died_at_stage: Optional[TakeoffLifecycleStage]
    death_reason: Optional[str]
    stage_evaluations: Mapping[str, bool]
    coverage_state: CoverageState
    takeoff_row_ids: tuple[str, ...]
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TakeoffLifecycleAuditSummary:
    """Aggregate lifecycle audit report across all detected building objects."""
    total_detected: int
    total_authenticated: int
    total_modeled: int
    total_quantified: int
    total_published: int
    total_displayed: int
    died_between_stages: Mapping[str, int]
    object_reports: tuple[ObjectLifecycleReport, ...]

    def dropout_rate(self) -> float:
        if self.total_detected == 0:
            return 0.0
        return round((self.total_detected - self.total_displayed) / self.total_detected, 4)


def audit_takeoff_lifecycle(
    *,
    detected_objects: Sequence[Mapping[str, Any]],
    coverage_summary: CoverageRegistrySummaryV1,
    scene_objects: Sequence[Mapping[str, Any]],
    published_takeoff_rows: Sequence[Mapping[str, Any]],
) -> TakeoffLifecycleAuditSummary:
    """Audit all building objects across the 6 pipeline stages.

    Stages:
    1. DETECTED: Object was observed in the drawing/source document.
    2. AUTHENTICATED: Corroborated by an authoritative producer without abstention/conflict.
    3. MODELED: Represented in canonical 3D/geometry model.
    4. QUANTIFIED: Successfully linked to verified takeoff quantity.
    5. PUBLISHED: Present in published takeoff_rows table.
    6. DISPLAYED: Present and drawable in the 3D viewer/HUD without refusal.
    """
    provider = RegistryCoverageRecordProviderV1(coverage_summary)

    scene_by_id: Dict[str, Mapping[str, Any]] = {
        str(obj.get("id")): obj for obj in scene_objects if obj.get("id")
    }

    published_row_ids = {
        str(r.get("id") or r.get("row_id") or r.get("source_reference"))
        for r in published_takeoff_rows
        if r.get("id") or r.get("row_id") or r.get("source_reference")
    }

    object_reports: List[ObjectLifecycleReport] = []
    dropouts: Dict[str, int] = {
        "died_at_authentication": 0,
        "died_at_modeling": 0,
        "died_at_quantification": 0,
        "died_at_publication": 0,
        "died_at_display": 0,
    }

    counts = {
        TakeoffLifecycleStage.DETECTED: 0,
        TakeoffLifecycleStage.AUTHENTICATED: 0,
        TakeoffLifecycleStage.MODELED: 0,
        TakeoffLifecycleStage.QUANTIFIED: 0,
        TakeoffLifecycleStage.PUBLISHED: 0,
        TakeoffLifecycleStage.DISPLAYED: 0,
    }

    for det in detected_objects:
        obj_id = str(det.get("id") or "").strip()
        obj_type = str(det.get("type") or "UNKNOWN")
        counts[TakeoffLifecycleStage.DETECTED] += 1

        stage_flags: Dict[str, bool] = {TakeoffLifecycleStage.DETECTED.value: True}

        highest = TakeoffLifecycleStage.DETECTED
        died_at: Optional[TakeoffLifecycleStage] = None
        death_reason: Optional[str] = None

        # 2. Check AUTHENTICATED
        scene_obj = scene_by_id.get(obj_id, {"id": obj_id, "type": obj_type})
        raw_record = provider._records.get(obj_id)
        audit_record: AuditObjectRecord = provider.record_for(scene_obj)

        is_authenticated = raw_record is not None
        stage_flags[TakeoffLifecycleStage.AUTHENTICATED.value] = is_authenticated

        if is_authenticated:
            assert raw_record is not None
            counts[TakeoffLifecycleStage.AUTHENTICATED] += 1
            highest = TakeoffLifecycleStage.AUTHENTICATED

            # 3. Check MODELED
            has_geometry = bool(
                obj_id in scene_by_id
                and scene_obj.get("geometry")
                and scene_obj.get("geometry", {}).get("basis") != "none"
            )
            stage_flags[TakeoffLifecycleStage.MODELED.value] = has_geometry

            if has_geometry:
                counts[TakeoffLifecycleStage.MODELED] += 1
                highest = TakeoffLifecycleStage.MODELED

                # 4. Check QUANTIFIED
                has_quantity = bool(raw_record.takeoff_row_ids)
                stage_flags[TakeoffLifecycleStage.QUANTIFIED.value] = has_quantity

                if has_quantity:
                    counts[TakeoffLifecycleStage.QUANTIFIED] += 1
                    highest = TakeoffLifecycleStage.QUANTIFIED

                    # 5. Check PUBLISHED
                    is_published = any(
                        rid in published_row_ids or any(rid in p_id for p_id in published_row_ids)
                        for rid in raw_record.takeoff_row_ids
                    )
                    stage_flags[TakeoffLifecycleStage.PUBLISHED.value] = is_published

                    if is_published:
                        counts[TakeoffLifecycleStage.PUBLISHED] += 1
                        highest = TakeoffLifecycleStage.PUBLISHED

                        # 6. Check DISPLAYED
                        is_displayed = (
                            audit_record.coverage_state is CoverageState.ACCOUNTED
                            and not scene_obj.get("refusal_reason")
                            and str(scene_obj.get("physical_state") or "") not in REFUSED_PHYSICAL_STATES
                        )
                        stage_flags[TakeoffLifecycleStage.DISPLAYED.value] = is_displayed

                        if is_displayed:
                            counts[TakeoffLifecycleStage.DISPLAYED] += 1
                            highest = TakeoffLifecycleStage.DISPLAYED
                        else:
                            died_at = TakeoffLifecycleStage.DISPLAYED
                            death_reason = scene_obj.get("refusal_reason") or "renderer_refused_or_partial"
                            dropouts["died_at_display"] += 1
                    else:
                        died_at = TakeoffLifecycleStage.PUBLISHED
                        death_reason = "takeoff_row_not_found_in_published_table"
                        dropouts["died_at_publication"] += 1
                else:
                    died_at = TakeoffLifecycleStage.QUANTIFIED
                    death_reason = "no_commercial_quantity_linked_to_object"
                    dropouts["died_at_quantification"] += 1
            else:
                died_at = TakeoffLifecycleStage.MODELED
                death_reason = "missing_geometry_representation_in_scene"
                dropouts["died_at_modeling"] += 1
        else:
            died_at = TakeoffLifecycleStage.AUTHENTICATED
            death_reason = audit_record.reason_code or "unauthenticated_or_abstained"
            dropouts["died_at_authentication"] += 1

        object_reports.append(
            ObjectLifecycleReport(
                object_id=obj_id,
                object_type=obj_type,
                highest_stage_reached=highest,
                died_at_stage=died_at,
                death_reason=death_reason,
                stage_evaluations=stage_flags,
                coverage_state=audit_record.coverage_state,
                takeoff_row_ids=audit_record.takeoff_row_ids,
                provenance=audit_record.provenance,
            )
        )

    return TakeoffLifecycleAuditSummary(
        total_detected=counts[TakeoffLifecycleStage.DETECTED],
        total_authenticated=counts[TakeoffLifecycleStage.AUTHENTICATED],
        total_modeled=counts[TakeoffLifecycleStage.MODELED],
        total_quantified=counts[TakeoffLifecycleStage.QUANTIFIED],
        total_published=counts[TakeoffLifecycleStage.PUBLISHED],
        total_displayed=counts[TakeoffLifecycleStage.DISPLAYED],
        died_between_stages=dropouts,
        object_reports=tuple(object_reports),
    )


class TakeoffCoverageLifecycleAuditTests(unittest.TestCase):
    """Test suite verifying takeoff coverage audit adapter and lifecycle tracking (AG-09)."""

    def _build_test_summary(
        self,
        object_ids: Sequence[str] = ("w1",),
        linked_ids: Sequence[str] = ("w1",),
    ) -> CoverageRegistrySummaryV1:
        manifest = CoverageRegistryRunManifestV1(
            source_document_id="doc-1",
            revision_id="rev-1",
            source_sha256=SHA,
            registry_run_id="run-1",
            snapshot_id="snap-1",
            expected_object_universe_keys=(OBJ_KEY,),
            expected_quantity_evidence_universe_keys=(QE_KEY,),
            expected_takeoff_row_universe_keys=(ROW_KEY,),
        )
        object_snapshot = ProducerObjectUniverseSnapshotV1(
            producer=OBJ_KEY[0],
            owning_authority="physical_wall_existence_authority",
            category=OBJ_KEY[1],
            source_document_id="doc-1",
            revision_id="rev-1",
            source_sha256=SHA,
            registry_run_id="run-1",
            snapshot_id="snap-1",
            admitted_object_ids=tuple(object_ids),
            enumeration_status=ENUMERATION_COMPLETE,
        )
        qes = []
        rows = []
        if linked_ids:
            for lid in linked_ids:
                qes.append(
                    QuantityEvidence(
                        quantity_id=f"q-{lid}",
                        family="wall_length",
                        semantic_key=f"wall_length:q-{lid}",
                        value=5.0,
                        unit="M",
                        input_entity_ids=(lid,),
                        evidence_ids=(f"ev-{lid}",),
                        authority="wall_length",
                        status="corroborated",
                        confidence=0.9,
                    )
                )
                rows.append(
                    TakeoffOutputRow(
                        quantity_id=f"q-{lid}",
                        description="wall length",
                        value=5.0,
                        unit="M",
                        geometry_ref=lid,
                        is_publishable=False,
                    )
                )
        qe_snapshot = QuantityEvidenceUniverseSnapshotV1(
            producer=QE_KEY[0],
            source=QE_KEY[1],
            source_document_id="doc-1",
            revision_id="rev-1",
            source_sha256=SHA,
            registry_run_id="run-1",
            snapshot_id="snap-1",
            quantity_ids=tuple(q.quantity_id for q in qes),
            enumeration_status=ENUMERATION_COMPLETE,
        )
        row_snapshot = TakeoffOutputRowUniverseSnapshotV1(
            source=ROW_KEY[0],
            collection=ROW_KEY[1],
            source_document_id="doc-1",
            revision_id="rev-1",
            source_sha256=SHA,
            registry_run_id="run-1",
            snapshot_id="snap-1",
            quantity_ids=tuple(r.quantity_id for r in rows),
            enumeration_status=ENUMERATION_COMPLETE,
        )
        return build_coverage_registry_v1(
            manifest=manifest,
            object_universe_snapshots=(object_snapshot,),
            quantity_evidence_universe_snapshots=(qe_snapshot,),
            takeoff_output_row_universe_snapshots=(row_snapshot,),
            quantity_evidence_by_universe={QE_KEY: qes},
            takeoff_rows_by_universe={ROW_KEY: rows},
            object_metadata_by_id={
                oid: {
                    "object_type": "wall",
                    "geometry_ids": [oid],
                    "source_pages": [1],
                    "provenance": {"source": "synthetic"},
                }
                for oid in object_ids
            },
        )

    def test_full_pipeline_success_detected_to_displayed(self):
        """A fully verified wall reaches all 6 stages: DETECTED -> DISPLAYED."""
        summary = self._build_test_summary(object_ids=["wall-101"], linked_ids=["wall-101"])

        detected = [{"id": "wall-101", "type": "WALL"}]
        scene = [
            {
                "id": "wall-101",
                "type": "WALL",
                "geometry": {"basis": "canonical", "pts": [[0, 0], [5, 0]]},
            }
        ]
        # Published row matching the linked quantity_id
        published_rows = [{"id": "q-wall-101", "quantity": 5.0}]

        report = audit_takeoff_lifecycle(
            detected_objects=detected,
            coverage_summary=summary,
            scene_objects=scene,
            published_takeoff_rows=published_rows,
        )

        self.assertEqual(report.total_detected, 1)
        self.assertEqual(report.total_authenticated, 1)
        self.assertEqual(report.total_modeled, 1)
        self.assertEqual(report.total_quantified, 1)
        self.assertEqual(report.total_published, 1)
        self.assertEqual(report.total_displayed, 1)
        self.assertEqual(report.dropout_rate(), 0.0)

        obj_rep = report.object_reports[0]
        self.assertEqual(obj_rep.highest_stage_reached, TakeoffLifecycleStage.DISPLAYED)
        self.assertIsNone(obj_rep.died_at_stage)
        self.assertIsNone(obj_rep.death_reason)

    def test_dropout_detected_but_died_at_authentication(self):
        """An unauthenticated line/stroke dies at AUTHENTICATED stage."""
        summary = self._build_test_summary(object_ids=["valid-wall"], linked_ids=["valid-wall"])

        detected = [{"id": "noise-stroke-01", "type": "LINE"}]
        scene = [{"id": "noise-stroke-01", "type": "LINE"}]

        report = audit_takeoff_lifecycle(
            detected_objects=detected,
            coverage_summary=summary,
            scene_objects=scene,
            published_takeoff_rows=[],
        )

        self.assertEqual(report.total_detected, 1)
        self.assertEqual(report.total_authenticated, 0)
        self.assertEqual(report.died_between_stages["died_at_authentication"], 1)

        obj_rep = report.object_reports[0]
        self.assertEqual(obj_rep.highest_stage_reached, TakeoffLifecycleStage.DETECTED)
        self.assertEqual(obj_rep.died_at_stage, TakeoffLifecycleStage.AUTHENTICATED)
        self.assertEqual(obj_rep.death_reason, REASON_NOT_IN_REGISTRY_UNIVERSE)

    def test_dropout_authenticated_but_died_at_modeling(self):
        """An authenticated wall with no 3D geometry representation dies at MODELED stage."""
        summary = self._build_test_summary(object_ids=["wall-abstract-01"], linked_ids=["wall-abstract-01"])

        detected = [{"id": "wall-abstract-01", "type": "WALL"}]
        # In scene but geometry basis is "none"
        scene = [{"id": "wall-abstract-01", "type": "WALL", "geometry": {"basis": "none"}}]

        report = audit_takeoff_lifecycle(
            detected_objects=detected,
            coverage_summary=summary,
            scene_objects=scene,
            published_takeoff_rows=[{"id": "q-wall-abstract-01"}],
        )

        self.assertEqual(report.total_authenticated, 1)
        self.assertEqual(report.total_modeled, 0)
        self.assertEqual(report.died_between_stages["died_at_modeling"], 1)

        obj_rep = report.object_reports[0]
        self.assertEqual(obj_rep.highest_stage_reached, TakeoffLifecycleStage.AUTHENTICATED)
        self.assertEqual(obj_rep.died_at_stage, TakeoffLifecycleStage.MODELED)
        self.assertEqual(obj_rep.death_reason, "missing_geometry_representation_in_scene")

    def test_dropout_modeled_but_died_at_quantification(self):
        """A modeled wall with zero linked takeoff rows dies at QUANTIFIED stage."""
        # wall-unquant is in object_ids, but NOT in linked_ids -> zero quantity links!
        summary = self._build_test_summary(object_ids=["wall-unquant-01"], linked_ids=[])

        detected = [{"id": "wall-unquant-01", "type": "WALL"}]
        scene = [{"id": "wall-unquant-01", "type": "WALL", "geometry": {"basis": "canonical"}}]

        report = audit_takeoff_lifecycle(
            detected_objects=detected,
            coverage_summary=summary,
            scene_objects=scene,
            published_takeoff_rows=[],
        )

        self.assertEqual(report.total_modeled, 1)
        self.assertEqual(report.total_quantified, 0)
        self.assertEqual(report.died_between_stages["died_at_quantification"], 1)

        obj_rep = report.object_reports[0]
        self.assertEqual(obj_rep.highest_stage_reached, TakeoffLifecycleStage.MODELED)
        self.assertEqual(obj_rep.died_at_stage, TakeoffLifecycleStage.QUANTIFIED)

    def test_dropout_quantified_but_died_at_publication(self):
        """A quantified wall whose row failed publication gate dies at PUBLISHED stage."""
        summary = self._build_test_summary(object_ids=["wall-gated-01"], linked_ids=["wall-gated-01"])

        detected = [{"id": "wall-gated-01", "type": "WALL"}]
        scene = [{"id": "wall-gated-01", "type": "WALL", "geometry": {"basis": "canonical"}}]
        # Published table is empty (publication failed or was rolled back)
        published_rows = []

        report = audit_takeoff_lifecycle(
            detected_objects=detected,
            coverage_summary=summary,
            scene_objects=scene,
            published_takeoff_rows=published_rows,
        )

        self.assertEqual(report.total_quantified, 1)
        self.assertEqual(report.total_published, 0)
        self.assertEqual(report.died_between_stages["died_at_publication"], 1)

        obj_rep = report.object_reports[0]
        self.assertEqual(obj_rep.highest_stage_reached, TakeoffLifecycleStage.QUANTIFIED)
        self.assertEqual(obj_rep.died_at_stage, TakeoffLifecycleStage.PUBLISHED)

    def test_dropout_published_but_died_at_display(self):
        """A published row whose 3D scene object is refused by renderer dies at DISPLAYED stage."""
        summary = self._build_test_summary(object_ids=["wall-refused-01"], linked_ids=["wall-refused-01"])

        detected = [{"id": "wall-refused-01", "type": "WALL"}]
        # Scene has refusal_reason
        scene = [
            {
                "id": "wall-refused-01",
                "type": "WALL",
                "geometry": {"basis": "canonical"},
                "refusal_reason": "geometry_coplanar_overlap",
            }
        ]
        published_rows = [{"id": "q-wall-refused-01"}]

        report = audit_takeoff_lifecycle(
            detected_objects=detected,
            coverage_summary=summary,
            scene_objects=scene,
            published_takeoff_rows=published_rows,
        )

        self.assertEqual(report.total_published, 1)
        self.assertEqual(report.total_displayed, 0)
        self.assertEqual(report.died_between_stages["died_at_display"], 1)

        obj_rep = report.object_reports[0]
        self.assertEqual(obj_rep.highest_stage_reached, TakeoffLifecycleStage.PUBLISHED)
        self.assertEqual(obj_rep.died_at_stage, TakeoffLifecycleStage.DISPLAYED)
        self.assertEqual(obj_rep.death_reason, "geometry_coplanar_overlap")


if __name__ == "__main__":
    unittest.main()
