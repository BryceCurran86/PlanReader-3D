"""Compare complete-handoff variants produced by the diag workflows: outputs must be byte-identical to the first variant (the baseline).

usage: python tools/diag_claude_variant_compare.py <artifacts-root> <variant,variant,...> <project> [<project> ...]

Each variant directory holds ``out/`` (the handoff output tree), ``time_v.txt`` (``/usr/bin/time -v``), ``exit_code.txt`` and an optional
``rss_kb_timeline.txt``.  Measurement helper only: it reads files and prints Markdown; exit status 1 when a variant is missing, did not
exit 0, or any output file differs from the baseline's.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


def _wall_cpu(text: str):
    def get(pattern):
        match = re.search(pattern, text)
        return None if match is None else match.group(1)

    wall = get(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([\d:.]+)")
    seconds = None
    if wall:
        seconds = 0.0
        for part in wall.split(":"):
            seconds = seconds * 60 + float(part)
    user, system = get(r"User time \(seconds\): ([\d.]+)"), get(r"System time \(seconds\): ([\d.]+)")
    cpu = None if user is None or system is None else float(user) + float(system)
    return seconds, cpu


def _peak_mib(directory: Path):
    path = directory / "rss_kb_timeline.txt"
    if not path.exists():
        return None
    values = [int(line.split()[1]) for line in path.read_text().splitlines() if len(line.split()) == 2]
    return max(values) / 1024.0 if values else None


def _tree_hashes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def main(argv: list[str]) -> int:
    root, variants, projects = Path(argv[1]), argv[2].split(","), argv[3:]
    failures: list[str] = []
    for project in projects:
        base_dir = root / f"full-handoff-{project}"
        print(f"### {project}")
        print("| variant | code | gc | exit | wall s | cpu s (user+sys) | cpu/base | peak RSS MiB | rss/base | output files | identical to base |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        base = None
        for variant in variants:
            directory = base_dir / variant
            if not directory.is_dir():
                failures.append(f"{project}/{variant}: missing")
                print(f"| {variant} | - | - | - | - | - | - | - | - | - | MISSING |")
                continue
            exit_code = (directory / "exit_code.txt").read_text().strip().split("=")[-1] if (directory / "exit_code.txt").exists() else "?"
            wall, cpu = _wall_cpu((directory / "time_v.txt").read_text() if (directory / "time_v.txt").exists() else "")
            peak = _peak_mib(directory)
            code = (directory / "code_sha.txt").read_text().strip()[:8] if (directory / "code_sha.txt").exists() else "-"
            mode = (directory / "gc_mode.txt").read_text().strip() if (directory / "gc_mode.txt").exists() else "-"
            hashes = _tree_hashes(directory / "out") if (directory / "out").is_dir() else {}
            if exit_code != "0":
                failures.append(f"{project}/{variant}: exit {exit_code}")
            if not hashes:
                failures.append(f"{project}/{variant}: no output files")
            if base is None:
                base = (cpu, peak, hashes)
                same = "baseline"
            else:
                same = "yes" if hashes == base[2] else "NO"
                if same != "yes":
                    differing = sorted(k for k in set(hashes) | set(base[2]) if hashes.get(k) != base[2].get(k))
                    failures.append(f"{project}/{variant}: output differs from {variants[0]}: {differing[:5]}")
            ratio = "-" if cpu is None or base is None or not base[0] else f"{cpu / base[0]:.3f}"
            rss_ratio = "-" if peak is None or base is None or not base[1] else f"{peak / base[1]:.3f}"
            print(f"| {variant} | {code} | {mode} | {exit_code} | {wall if wall is not None else '-'} | "
                  f"{'-' if cpu is None else f'{cpu:.1f}'} | {ratio} | {'-' if peak is None else f'{peak:.0f}'} | {rss_ratio} | "
                  f"{len(hashes)} | {same} |")
        print()
    if failures:
        print("FAILURES:")
        for failure in failures:
            print(" -", failure)
        return 1
    print("All variants exited 0 and every output file is byte-identical to the baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
