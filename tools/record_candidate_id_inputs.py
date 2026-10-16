"""Record the hashed inputs of physical-opening candidate ids while a stage tool runs.

Read-only wrapper.  ``stable_contract_id`` is wrapped so it returns exactly what the
original returns; for the selected prefixes it additionally stores
``(prefix, payload, extra args, kwargs)`` under the returned id.  The wrapped tool is
run unchanged, so no production module is edited and no id, report or quantity moves.

The recording is the input of ``tools/prove_candidate_id_snapshot_remap.py``, which
needs the *exact* payload behind every id (the report only carries the ids).

Run it from the checkout whose behaviour you want to record -- once from the baseline
tree and once from the candidate tree -- because it executes that tree's own modules::

    PYTHONPATH=. python -m tools.record_candidate_id_inputs \\
        --recording-out rec_base.json -- \\
        --pdf plan.pdf --page-id 3 --output stage_base.json

Everything after ``--`` is passed to the stage tool verbatim.
"""
from __future__ import annotations

import argparse
import json
import runpy
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE_TOOL = "tools/diag_gptmax_source_authority_stages.py"
CANDIDATE_PREFIXES = ("physical_opening_raw_candidate", "physical_opening_candidate")
OBSERVATION_PREFIXES = ("source_observation",)


def _normalise(value: Any) -> Any:
    """JSON-safe, order-stable copy.  Sets become sorted lists, tuples lists."""
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_normalise(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def install_recorder(prefixes: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    """Wrap ``pb_migration_contracts.stable_contract_id``; return the live record dict.

    Must run before the stage tool imports its modules so every ``from
    pb_migration_contracts import stable_contract_id`` binds the wrapper.  Modules that
    were already imported with the original binding are re-pointed.
    """
    import pb_migration_contracts as contracts

    original = contracts.stable_contract_id
    wanted = frozenset(prefixes)
    records: dict[str, list[dict[str, Any]]] = {}

    def recording_stable_contract_id(prefix, payload=None, *args, **kwargs):
        contract_id = original(prefix, payload, *args, **kwargs)
        if prefix in wanted:
            records.setdefault(contract_id, []).append({
                "kind": prefix,
                "payload": _normalise(payload),
                "args": _normalise(list(args)),
                "kw": _normalise(kwargs),
            })
        return contract_id

    contracts.stable_contract_id = recording_stable_contract_id
    for module in list(sys.modules.values()):
        if module is not None and getattr(module, "stable_contract_id", None) is original:
            module.stable_contract_id = recording_stable_contract_id
    return records


def run_stage_tool(stage_tool: str, stage_args: Sequence[str]) -> None:
    tool_path = Path(stage_tool)
    if not tool_path.is_absolute():
        tool_path = REPO_ROOT / tool_path
    previous_argv = sys.argv
    sys.argv = [str(tool_path), *stage_args]
    try:
        runpy.run_path(str(tool_path), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise
    finally:
        sys.argv = previous_argv


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        split = argv.index("--")
        own, stage_args = argv[:split], argv[split + 1:]
    else:
        own, stage_args = argv, []
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recording-out", required=True, help="where to write the JSON recording")
    parser.add_argument("--stage-tool", default=DEFAULT_STAGE_TOOL, help="repo-relative tool to run")
    parser.add_argument(
        "--include-observations", action="store_true",
        help="also record source_observation identity payloads (large: ~75 MB for Lot16)")
    args = parser.parse_args(own)
    prefixes = CANDIDATE_PREFIXES + (OBSERVATION_PREFIXES if args.include_observations else ())
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    records = install_recorder(prefixes)
    try:
        run_stage_tool(args.stage_tool, stage_args)
    finally:
        # Written even if the stage tool fails so a partial run is inspectable.
        Path(args.recording_out).write_text(json.dumps(records, indent=1, sort_keys=True), encoding="utf-8")
    print(f"recorded {len(records)} ids -> {args.recording_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
