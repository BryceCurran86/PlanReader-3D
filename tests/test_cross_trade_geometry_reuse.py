"""Tests for fail-closed canonical cross-trade geometry reuse."""
from __future__ import annotations

import unittest

import pb_takeoff_row_contract as takeoff_contract
from pb_auto_geometry_v1219 import _validate_auto_rows
from pb_cross_trade_geometry_reuse import (
    derive_roof_trade_quantities,
    derive_slab_trade_quantities,
    derive_space_trade_quantities,
    derive_wall_trade_quantities,
    to_takeoff_rows,
)


def _wall():
    return {
        "canonical_wall_id": "wall_N01",
        "length_m": 10.0,
        "net_area_m2": 23.4,
        "role": "external",
        "physical_identity_resolved": True,
        "quantity_complete": True,
        "evidence_ids": ["net-wall-record-1"],
    }


def _slab():
    return {
        "canonical_slab_id": "slab_G01",
        "area_m2": 120.0,
        "thickness_m": 0.15,
        "polygon_m": [
            [0.0, 0.0],
            [12.0, 0.0],
            [12.0, 10.0],
            [0.0, 10.0],
        ],
        "geometry_complete": True,
        "thickness_complete": True,
        "reinforcement": [
            {
                "reinforcement_type": "SL72",
                "specification": "SL72 mesh",
            }
        ],
        "provenance": {
            "annotation_raw_text": "150mm RC slab",
            "boundary_id": "slab-boundary-1",
        },
    }


def _roof():
    return {
        "canonical_roof_id": "roof_main",
        "covering_area_m2": 108.24,
        "ridge_length_m": 15.0,
        "eave_length_lm": 42.0,
        "metric_parameter_geometry_complete": True,
        "evidence_ids": ["roof-quantity-1", "roof-geometry-1"],
    }


def _space():
    return {
        "canonical_room_id": "room_101",
        "perimeter_m": 20.0,
        "evidence_ids": ["room-face-1"],
    }


class TestCrossTradeGeometryReuse(unittest.TestCase):
    def test_wall_reuses_one_canonical_object_across_explicit_trade_scopes(self):
        specs = {
            "masonry": {
                "material": "Brick veneer",
                "evidence_ids": ["spec-masonry"],
            },
            "linings": {
                "material": "10mm plasterboard",
                "section": "Internal",
                "physical_face_ids": ["face-int"],
                "evidence_ids": ["spec-lining"],
            },
            "painting": {
                "material": "Acrylic paint system",
                "section": "Internal",
                "physical_face_ids": ["face-int"],
                "evidence_ids": ["spec-paint"],
            },
            "insulation": {
                "material": "R2.5 batts",
                "evidence_ids": ["spec-insulation"],
            },
            "skirting": {
                "material": "MDF 67x18",
                "section": "Internal",
                "physical_face_ids": ["face-int"],
                "door_width_deduction_m": 0.9,
                "evidence_ids": ["spec-skirting", "door-widths-1"],
            },
        }

        quantities = derive_wall_trade_quantities(_wall(), specs)

        self.assertEqual(len(quantities), 5)
        by_trade = {item.trade_scope: item for item in quantities}
        self.assertEqual(by_trade["masonry"].quantity, 23.4)
        self.assertEqual(by_trade["linings"].quantity, 23.4)
        self.assertEqual(by_trade["painting"].quantity, 23.4)
        self.assertEqual(by_trade["insulation"].quantity, 23.4)
        self.assertEqual(by_trade["carpentry"].quantity, 9.1)
        self.assertEqual(by_trade["carpentry"].unit, "lm")
        for item in quantities:
            self.assertEqual(item.host_object_id, "wall_N01")
            self.assertEqual(item.host_object_type, "WALL")
            self.assertEqual(item.host_evidence_ids, ("net-wall-record-1",))
            self.assertTrue(item.spec_evidence_ids)

    def test_wall_face_finishes_require_explicit_physical_face_ownership(self):
        specs = {
            "painting": {
                "material": "Acrylic paint",
                "section": "Internal",
                "evidence_ids": ["spec-paint"],
            },
            "tiling": {
                "material": "Ceramic wall tile",
                "section": "Internal",
                "physical_face_ids": ["face-a", "face-b"],
                "evidence_ids": ["spec-tile"],
            },
        }

        quantities = derive_wall_trade_quantities(_wall(), specs)

        self.assertEqual(len(quantities), 1)
        self.assertEqual(quantities[0].trade_scope, "tiling")
        self.assertEqual(quantities[0].quantity, 46.8)
        self.assertIn("2 source-bound face(s)", quantities[0].derivation_formula)

    def test_wall_without_resolved_canonical_quantity_fails_closed(self):
        wall = _wall()
        wall["quantity_complete"] = False
        specs = {
            "masonry": {
                "material": "Brick veneer",
                "evidence_ids": ["spec-masonry"],
            }
        }
        self.assertEqual(derive_wall_trade_quantities(wall, specs), [])

    def test_slab_reuses_geometry_without_default_lap_or_thickness(self):
        specs = {
            "context": "ground",
            "context_evidence_ids": ["ground-bearing-note"],
            "concrete": {
                "material": "25 MPa concrete",
                "evidence_ids": ["spec-concrete"],
            },
            "edge_formwork": {
                "material": "Timber edge forms",
                "evidence_ids": ["spec-formwork"],
            },
            "waterproofing": {
                "material": "0.2mm DPM",
                "evidence_ids": ["spec-dpm"],
            },
            "reinforcement": {
                "evidence_ids": ["spec-reinforcement"],
            },
        }

        quantities = derive_slab_trade_quantities(_slab(), specs)

        self.assertEqual(len(quantities), 4)
        by_trade = {item.trade_scope: item for item in quantities}
        self.assertEqual(by_trade["concrete"].quantity, 18.0)
        self.assertEqual(by_trade["concrete"].unit, "m³")
        self.assertEqual(by_trade["formwork"].quantity, 6.6)
        self.assertEqual(by_trade["waterproofing"].quantity, 120.0)
        self.assertEqual(by_trade["reinforcement"].quantity, 120.0)
        self.assertIn(
            "no unproven lap or waste factor",
            by_trade["reinforcement"].derivation_formula,
        )

    def test_slab_missing_thickness_never_uses_100mm_default(self):
        slab = _slab()
        slab["thickness_m"] = None
        specs = {
            "concrete": {
                "material": "25 MPa concrete",
                "evidence_ids": ["spec-concrete"],
            }
        }
        self.assertEqual(derive_slab_trade_quantities(slab, specs), [])

    def test_roof_uses_proven_covering_area_not_default_pitch(self):
        specs = {
            "cladding": {
                "material": "Metal roof sheeting",
                "evidence_ids": ["spec-cladding"],
            },
            "insulation": {
                "material": "Roof blanket",
                "evidence_ids": ["spec-insulation"],
            },
            "gutters": {
                "material": "Eaves gutter",
                "evidence_ids": ["spec-gutter"],
            },
            "capping": {
                "material": "Ridge capping",
                "evidence_ids": ["spec-capping"],
            },
        }

        quantities = derive_roof_trade_quantities(_roof(), specs)

        self.assertEqual(len(quantities), 4)
        by_element = {item.element: item for item in quantities}
        self.assertEqual(
            by_element["Roof cladding / coverings"].quantity,
            108.24,
        )
        self.assertEqual(
            by_element["Roof insulation / sarking"].quantity,
            108.24,
        )
        self.assertEqual(by_element["Eaves gutters"].quantity, 42.0)
        self.assertEqual(by_element["Ridge / hip capping"].quantity, 15.0)

        legacy_proxy = {
            "roof_id": "legacy",
            "plan_area_m2": 100.0,
            "pitch_deg": 22.5,
        }
        self.assertEqual(
            derive_roof_trade_quantities(legacy_proxy, specs),
            [],
        )

    def test_room_reuse_is_linear_trim_only_not_floor_or_ceiling_proxy(self):
        specs = {
            "skirting": {
                "material": "MDF skirting",
                "section": "Internal",
                "evidence_ids": ["spec-skirting"],
            },
            "cornice": {
                "material": "90mm cove cornice",
                "section": "Internal",
                "evidence_ids": ["spec-cornice"],
            },
        }

        quantities = derive_space_trade_quantities(
            _space(),
            specs=specs,
            doors=[{"width_m": 0.9}],
        )

        self.assertEqual(len(quantities), 2)
        by_trade = {item.trade_scope: item for item in quantities}
        self.assertEqual(by_trade["carpentry"].quantity, 19.1)
        self.assertEqual(by_trade["plastering"].quantity, 20.0)
        self.assertNotIn("finishes", by_trade)
        self.assertNotIn("linings", by_trade)

    def test_missing_door_width_blocks_skirting_but_not_cornice(self):
        specs = {
            "skirting": {
                "material": "MDF skirting",
                "section": "Internal",
                "evidence_ids": ["spec-skirting"],
            },
            "cornice": {
                "material": "90mm cove cornice",
                "section": "Internal",
                "evidence_ids": ["spec-cornice"],
            },
        }

        quantities = derive_space_trade_quantities(
            _space(),
            specs=specs,
            doors=[{}],
        )

        self.assertEqual(len(quantities), 1)
        self.assertEqual(quantities[0].trade_scope, "plastering")

    def test_no_explicit_trade_specs_means_no_trade_quantities(self):
        self.assertEqual(derive_wall_trade_quantities(_wall()), [])
        self.assertEqual(derive_slab_trade_quantities(_slab()), [])
        self.assertEqual(derive_roof_trade_quantities(_roof()), [])
        self.assertEqual(
            derive_space_trade_quantities(_space(), doors=[]),
            [],
        )

    def test_supported_units_publish_to_legacy_21_field_row(self):
        specs = {
            "masonry": {
                "material": "Brick veneer",
                "evidence_ids": ["spec-masonry"],
            },
            "painting": {
                "material": "Acrylic paint",
                "section": "Internal",
                "physical_face_ids": ["face-int"],
                "evidence_ids": ["spec-paint"],
            },
        }
        quantities = derive_wall_trade_quantities(_wall(), specs)
        rows = to_takeoff_rows(
            workspace_id=77,
            quantities=quantities,
            source_page="p1",
        )

        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(len(row), 21)
            self.assertEqual(row[0], 77)
            self.assertGreater(row[6], 0.0)
            self.assertIn("wall_N01", row[10])
            self.assertEqual(row[12], 0)
            self.assertIn("Spec evidence:", row[17])
        _validate_auto_rows(rows, 77)

    def test_m3_is_preserved_and_legacy_takeoff_publication_fails_closed(self):
        specs = {
            "concrete": {
                "material": "25 MPa concrete",
                "evidence_ids": ["spec-concrete"],
            }
        }
        quantities = derive_slab_trade_quantities(_slab(), specs)
        concrete = quantities[0]

        self.assertEqual(concrete.unit, "m³")
        with self.assertRaises(takeoff_contract.TakeoffRowContractError):
            to_takeoff_rows(
                workspace_id=77,
                quantities=[concrete],
                source_page="p1",
            )


if __name__ == "__main__":
    unittest.main()
