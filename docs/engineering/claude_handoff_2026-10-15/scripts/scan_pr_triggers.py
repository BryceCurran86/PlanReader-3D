import re, subprocess, sys
sys.path.insert(0, "C:/claude-work/ci-trigger/tests"); sys.path.insert(0, "C:/claude-work/ci-trigger")
import test_signed_output_gate_path_coverage as m
repo = "C:/claude-work/rev-2811"
def git(*a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
for n in sys.argv[1:]:
    files = [f for f in git("diff", "--name-only", "origin/main...pr" + n).split() if f.startswith(".github/workflows/") and f.endswith(".yml")]
    for f in files:
        text = git("show", f"pr{n}:{f}")
        if not m._has_block_pull_request_trigger(text):
            continue
        try:
            m.pull_request_trigger_reaches_main(text)
        except ValueError as e:
            print(f"#{n} {f}: {e}")
