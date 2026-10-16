#!/usr/bin/env bash
# Complete original-source handoff for Q5446, main vs the integration tree, same machine, sequential.
export MSYS_NO_PATHCONV=1 ORT_DISABLE_TELEMETRY=1 PYTHONUNBUFFERED=1
PDF="documents/sources/Q5446_Standard_Plans_V1_20220320.pdf"
PID_="au_qld_q5446_armstrong32_harlequin"
OUT=C:/claude-work/audit-out/clean/h_q5446
mkdir -p "$OUT"
for spec in "main:C:/claude-work/main-ref" "integration:C:/claude-work/release-int"; do
  name=${spec%%:*}; tree=${spec#*:}
  cd "$tree" || exit 1
  echo "=== $name $(git rev-parse --short=8 HEAD) start $(date +%H:%M:%S)" | tee -a "$OUT/log.txt"
  start=$(date +%s)
  PYTHONPATH=. python -u tools/run_source_closed_project_handoff.py --pdf "$PDF" --project-id "$PID_" --family-group all --output-dir "$OUT/$name" > "$OUT/$name.stdout.txt" 2> "$OUT/$name.stderr.txt"
  code=$?
  echo "=== $name exit=$code seconds=$(( $(date +%s) - start ))" | tee -a "$OUT/log.txt"
done
echo "ALL DONE $(date +%H:%M:%S)" | tee -a "$OUT/log.txt"
