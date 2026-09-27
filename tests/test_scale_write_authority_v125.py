from pb_takeoff_accuracy_v125 import guarded_exec


class FakeApp:
    def __init__(self):
        self.page = {
            "workspace_id": 1,
            "px_per_m": 0.0,
            "scale_method": "",
            "scale_verified": 0,
        }

    @staticmethod
    def to_float(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def lquery(self, sql, params=()):
        if "SELECT workspace_id,px_per_m,scale_method,scale_verified FROM pages" in sql:
            return [dict(self.page)]
        if "SELECT DISTINCT takeoff_row_id FROM measurement_lines" in sql:
            return []
        return []


def _base_exec(app, calls):
    def run(sql, params=()):
        params = tuple(params or ())
        calls.append((sql, params))
        normalized = " ".join(sql.strip().lower().split())
        if normalized.startswith("update pages set px_per_m="):
            app.page["px_per_m"] = float(params[0])
        elif normalized.startswith("update pages set scale_method=?,scale_verified=?"):
            app.page["scale_method"] = params[0]
            app.page["scale_verified"] = int(params[1])
        elif normalized.startswith("update pages set scale_method='manual_calibration',scale_verified=1,px_per_m="):
            app.page["scale_method"] = "manual_calibration"
            app.page["scale_verified"] = 1
            app.page["px_per_m"] = float(params[0])
        return 1

    return run


def test_repeated_generic_scale_writes_never_promote_to_manual():
    app = FakeApp()
    calls = []
    run = guarded_exec(app, _base_exec(app, calls))

    run("UPDATE pages SET px_per_m=? WHERE id=?", (28.346, 7))
    assert app.page["scale_method"] == "auto_detected"
    assert app.page["scale_verified"] == 0

    run("UPDATE pages SET px_per_m=? WHERE id=?", (28.346, 7))
    assert app.page["scale_method"] == "auto_detected"
    assert app.page["scale_verified"] == 0


def test_explicit_manual_calibration_write_is_authoritative():
    app = FakeApp()
    calls = []
    run = guarded_exec(app, _base_exec(app, calls))

    run(
        "UPDATE pages SET scale_method='manual_calibration',scale_verified=1,px_per_m=? WHERE id=?",
        (42.0, 7),
    )

    assert app.page["px_per_m"] == 42.0
    assert app.page["scale_method"] == "manual_calibration"
    assert app.page["scale_verified"] == 1


def test_unchanged_automatic_rerun_preserves_real_manual_verification():
    app = FakeApp()
    app.page.update(px_per_m=42.0, scale_method="manual_calibration", scale_verified=1)
    run = guarded_exec(app, _base_exec(app, []))

    run("UPDATE pages SET px_per_m=? WHERE id=?", (42.0, 7))

    assert app.page["scale_method"] == "manual_calibration"
    assert app.page["scale_verified"] == 1


def test_changed_automatic_scale_revokes_old_manual_verification():
    app = FakeApp()
    app.page.update(px_per_m=42.0, scale_method="manual_calibration", scale_verified=1)
    run = guarded_exec(app, _base_exec(app, []))

    run("UPDATE pages SET px_per_m=? WHERE id=?", (50.0, 7))

    assert app.page["px_per_m"] == 50.0
    assert app.page["scale_method"] == "auto_detected"
    assert app.page["scale_verified"] == 0
