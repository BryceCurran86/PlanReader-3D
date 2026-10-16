#!/usr/bin/env bash
# Default-path differential: Lot16 page 3 producer-owned retention (hosts, frames, walls, canonical) on main vs a PR head.
export MSYS_NO_PATHCONV=1 ORT_DISABLE_TELEMETRY=1 PYTHONUNBUFFERED=1
PDF="documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf"
OUT=C:/claude-work/audit-out/clean/lot16_diff
mkdir -p "$OUT"
for spec in "main:C:/claude-work/main-ref" "pr2813:C:/claude-work/rev-2811"; do
  name=${spec%%:*}; tree=${spec#*:}
  cd "$tree" || exit 1
  echo "=== $name $(git rev-parse --short=8 HEAD) start $(date +%H:%M:%S)" | tee -a "$OUT/log.txt"
  start=$(date +%s)
  PYTHONPATH=. python -u tools/diag_gptmax_producer_owned_g17_wall_shadow.py --pdf "$PDF" --page-id 3 --output "$OUT/$name.json" > "$OUT/$name.stdout.txt" 2> "$OUT/$name.stderr.txt"
  echo "=== $name exit=$? seconds=$(( $(date +%s) - start ))" | tee -a "$OUT/log.txt"
done
echo "ALL DONE $(date +%H:%M:%S)" | tee -a "$OUT/log.txt"
