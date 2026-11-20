import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "vr-native" / "manifest-bridge" / "preview_acceptance.py"
spec = importlib.util.spec_from_file_location("preview_acceptance", path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

SHA = "a" * 64
GOOD = {
    "schemaVersion": "1.0.0", "renderState": "review",
    "localEvidenceTrusted": False, "measurementAuthorized": False,
    "commercialQuantityPublicationAllowed": False, "canEdit": False,
    "sourceScope": {"workspaceId": "w", "projectId": "p", "documentId": "d",
                    "revisionId": "r", "snapshotId": "s", "sourceSha256": SHA,
                    "modelRevision": 1},
    "coordinateSystem": {"unit": "metres", "renderOrigin": [0, 0, 0]},
    "inputObjectCount": 1,
    "walls": [{"objectId": "wall-1", "kind": "wallFace", "start": [0, 0],
               "end": [2, 0], "heightM": 2.4, "renderState": "review",
               "locallyAuthenticated": False, "canEdit": False,
               "commercialQuantityPublicationAllowed": False}],
}


def fresh():
    import copy
    return copy.deepcopy(GOOD)


class PreviewAcceptanceTests(unittest.TestCase):
    def test_valid_review_packet(self):
        self.assertEqual(gate.validate(fresh(), SHA), [])

    def test_missing_packet_abstains(self):
        self.assertTrue(gate.validate(None))

    def test_source_pin_required_when_provided(self):
        self.assertTrue(gate.validate(fresh(), "b" * 64))
        self.assertTrue(gate.validate(fresh(), "invalid"))

    def test_no_commercial_or_edit_authority(self):
        for key in ("localEvidenceTrusted", "measurementAuthorized",
                    "commercialQuantityPublicationAllowed", "canEdit"):
            with self.subTest(key=key):
                p = fresh()
                p[key] = True
                self.assertTrue(gate.validate(p))

    def test_scope_and_revision_abstain(self):
        for value in (-1, True, 1.0, None, "1"):
            with self.subTest(value=value):
                p = fresh()
                p["sourceScope"]["modelRevision"] = value
                self.assertTrue(gate.validate(p))

    def test_duplicate_walls_abstain(self):
        p = fresh()
        p["walls"].append(dict(p["walls"][0]))
        p["inputObjectCount"] = 2
        self.assertTrue(gate.validate(p))

    def test_invalid_geometry_abstains(self):
        for value in ([0, 0], [float("nan"), 0], ["0", 0], None, {}, [1]):
            with self.subTest(value=str(value)):
                p = fresh()
                p["walls"][0]["end"] = value
                self.assertTrue(gate.validate(p))

    def test_forbidden_wall_authority_abstains(self):
        p = fresh()
        p["walls"][0]["locallyAuthenticated"] = True
        self.assertTrue(gate.validate(p))

    def test_bad_count_abstains(self):
        for value in (0, True, 20001, "1"):
            with self.subTest(value=value):
                p = fresh()
                p["inputObjectCount"] = value
                self.assertTrue(gate.validate(p))

    def test_line_cannot_have_height(self):
        p = fresh()
        p["walls"][0]["kind"] = "wallLine"
        self.assertTrue(gate.validate(p))
        p["walls"][0]["heightM"] = None
        self.assertEqual(gate.validate(p), [])


if __name__ == "__main__":
    unittest.main()
