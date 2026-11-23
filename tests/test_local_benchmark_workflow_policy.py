from pathlib import Path


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_hosted_workflows_have_no_original_source_provisioning():
    for path in WORKFLOWS.glob("*.y*ml"):
        content = path.read_text(encoding="utf-8")
        for route in (
            "ORIGINAL_SOURCES_TOKEN",
            "vars.ORIGINAL_SOURCES_REPOSITORY",
            "PlanReader-3D-sources/",
            "provision-original-sources",
            "tools.run_frozen120_owner_benchmark",
        ):
            assert route not in content, (path.name, route)
