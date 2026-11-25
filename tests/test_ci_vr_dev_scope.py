from scripts.ci_vr_dev_scope import vr_only_paths

import pytest


@pytest.mark.parametrize("paths", [
    b"vr-editor/src/App.tsx\0",
    b"vr-editor/src/Scene.tsx\0vr-editor/tests/example.mjs\0",
    b"vr-editor/src/nested/style.css\0",
])
def test_scoped_vr_development_feedback(paths):
    assert vr_only_paths(paths)


@pytest.mark.parametrize("paths", [
    b"", b"vr-editor/src/App.tsx", b"vr-editor/src/App.tsx\0pb_vr_editor_scene_manifest.py\0",
    b".github/workflows/ci.yml\0", b"vr-editor/package-lock.json\0",
    b"vr-editor/windows/Build-Desktop.ps1\0", b"vr-editor/src/../App.tsx\0",
    b"vr-editor/src//App.tsx\0", b"vr-editor/src/evil\n.ts\0",
    b"vr-editor/src/\xff.ts\0", b"vr-editor/src/asset.pdf\0",
    b"vr-editor/tests/\0", b"vr-editor/src/one.ts\0\0",
])
def test_unknown_or_shared_changes_require_full_ci(paths):
    assert not vr_only_paths(paths)
