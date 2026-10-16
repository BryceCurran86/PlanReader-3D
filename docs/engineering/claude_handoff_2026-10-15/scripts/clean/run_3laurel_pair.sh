#!/usr/bin/env bash
# Complete original-source handoff for 3Laurel on main BEFORE the production batch (cfc86cb8) and AFTER (current main), same machine, sequential.
export MSYS_NO_PATHCONV=1 ORT_DISABLE_TELEMETRY=1 PYTHONUNBUFFERED=1
PDF="documents/sources/3LAUREL - Construction Plan Set Rev3 08.05.26.pdf"
PID_="au_qld_3laurel"
OUT=C:/claude-work/audit-out/clean/h_3laurel
mkdir -p "$OUT"
for spec in "pre:C:/claude-work/main-pre" "post:C:/claude-work/main-ref"; do
  name=${spec%%:*}; tree=${spec#*:}
  cd "$tree" || exit 1
  echo "=== $name $(git rev-parse --short=8 HEAD) start $(date +%H:%M:%S)" | tee -a "$OUT/log.txt"
  start=$(date +%s)
  PYTHONPATH=. python -u tools/run_source_closed_project_handoff.py --pdf "$PDF" --project-id "$PID_" --family-group all --output-dir "$OUT/$name" > "$OUT/$name.stdout.txt" 2> "$OUT/$name.stderr.txt"
  echo "=== $name exit=$? seconds=$(( $(date +%s) - start ))" | tee -a "$OUT/log.txt"
done
echo "ALL DONE $(date +%H:%M:%S)" | tee -a "$OUT/log.txt"
