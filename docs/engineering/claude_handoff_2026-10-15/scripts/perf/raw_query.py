"""Query a py-spy --format raw profile (gz): inclusive time of a function, where inside it the time sits (by line and by callee),
and who calls it.

usage: python raw_query.py profile.raw.gz <function-name> [<function-name> ...]
"""
import gzip, re, sys
from collections import Counter

FRAME = re.compile(r"^(?P<fn>.*?) \((?P<file>[^:()]+):(?P<line>\d+)\)$")
path, names = sys.argv[1], sys.argv[2:]
stacks = []
total = 0
with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        line = line.rstrip("\n")
        if not line:
            continue
        stack, _, count = line.rpartition(" ")
        try:
            n = int(count)
        except ValueError:
            continue
        frames = []
        for raw in stack.split(";"):
            m = FRAME.match(raw)
            frames.append((m["fn"], m["file"].split("/")[-1], int(m["line"])) if m else (raw, "", 0))
        stacks.append((frames, n))
        total += n
print(f"{path}: {total} samples")
for name in names:
    incl = 0
    by_line, by_callee, by_caller = Counter(), Counter(), Counter()
    for frames, n in stacks:
        idx = [i for i, f in enumerate(frames) if f[0] == name]
        if not idx:
            continue
        incl += n
        i = idx[-1]  # innermost occurrence for line/callee attribution
        by_line[(frames[i][1], frames[i][2])] += n
        if i + 1 < len(frames):
            by_callee[(frames[i + 1][0], frames[i + 1][1])] += n
        else:
            by_callee[("<self>", "")] += n
        j = idx[0]
        if j > 0:
            by_caller[(frames[j - 1][0], frames[j - 1][1], frames[j - 1][2])] += n
    print(f"\n=== {name}: inclusive {incl} ({100 * incl / max(total, 1):.1f}%)")
    print("  by line inside the function:")
    for (f, l), c in by_line.most_common(8):
        print(f"    {c:6d} {100 * c / max(incl, 1):5.1f}%  {f}:{l}")
    print("  by callee:")
    for (fn, f), c in by_callee.most_common(8):
        print(f"    {c:6d} {100 * c / max(incl, 1):5.1f}%  {fn} ({f})")
    print("  by caller (frame above, with its line):")
    for (fn, f, l), c in by_caller.most_common(6):
        print(f"    {c:6d} {100 * c / max(incl, 1):5.1f}%  {fn} ({f}:{l})")


def tree(root, depth, min_share=0.02):
    """Top-down inclusive tree below the innermost... first occurrence of ``root`` (callee functions only)."""
    sub = []
    for frames, n in stacks:
        for i, f in enumerate(frames):
            if f[0] == root:
                sub.append((frames[i:], n))
                break
    base = sum(n for _, n in sub)
    print(f"\n### tree of {root}: {base} samples ({100 * base / max(total, 1):.1f}% of total)")

    def walk(items, level):
        groups = {}
        for frames, n in items:
            if level < len(frames):
                key = (frames[level][0], frames[level][1])
                groups.setdefault(key, []).append((frames, n))
        for key, grp in sorted(groups.items(), key=lambda kv: -sum(n for _, n in kv[1])):
            weight = sum(n for _, n in grp)
            if weight < min_share * base:
                continue
            lines = Counter()
            for frames, n in grp:
                lines[frames[level][2]] += n
            top_line = lines.most_common(1)[0][0]
            print("  " * level + f"{weight:6d} {100 * weight / base:5.1f}%  {key[0]} ({key[1]}:{top_line})")
            if level + 1 < depth:
                walk(grp, level + 1)

    walk(sub, 0)


import os
if os.environ.get("RAW_TREE"):
    for spec in os.environ["RAW_TREE"].split(","):
        name, _, d = spec.partition(":")
        tree(name, int(d or 6))
