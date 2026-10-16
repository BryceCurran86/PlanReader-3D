**Claude — complete original-source handoff measurement, 3Laurel and Q5446 (DIAG run 38687716754, PR #2692 head `d266ca06`, base main `40d8e849`).** Measurement only; no production quantity or score claim; nothing merged.

Method: same GitHub runner, variants run sequentially, each a full `run_source_closed_project_handoff.py --family-group all` on the verified original PDF (SHA-256 checked before the run); CPU = user + system from `/usr/bin/time -v`; peak RSS = `Maximum resident set size`. `base` is measured twice (`base2` last) to bound run-to-run noise. **Every output tree (`production_summary.json`, `source_attempt_preflight.json`) is byte-identical across all five variants for both projects** (tree hash `9074ee10…` 3Laurel, `edd76787…` Q5446); the workflow's compare job passes.

| project | variant | code | CPU s | vs base | peak RSS GB | vs base |
|---|---|---|---|---|---|---|
| 3Laurel | base (main) | `40d8e849` | 1109.9 / 1101.1 | 1.000 | 6.34 | 1.000 |
| 3Laurel | #2738 alone | `669e83b9` | 1100.4 | 0.995 | 6.35 | 1.002 |
| 3Laurel | stack (#2693+#2694+#2705+#2706+#2695 staged GC) | `e3b81d42` | 604.7 | **0.547** | 4.19 | **0.661** |
| 3Laurel | stack + #2738 | `b7423a76` | 603.3 | 0.546 | 4.19 | 0.661 |
| Q5446 | base (main) | `40d8e849` | 550.9 / 548.9 | 1.000 | 7.40 | 1.000 |
| Q5446 | #2738 alone | `e713af29` | 543.2 | 0.988 | 6.92 | 0.935 |
| Q5446 | stack | `7980fb37` | 290.3 | **0.528** | 4.70 | **0.635** |
| Q5446 | stack + #2738 | `cc427646` | 291.5 | 0.530 | 4.70 | 0.635 |

Run-to-run noise (base vs base2): 0.81 % CPU on 3Laurel, 0.36 % on Q5446.

Findings:
1. The rebased resource stack roughly **halves CPU (0.53-0.55x) and cuts peak memory by about a third (0.64-0.66x) on both complete original-source runs, with byte-identical outputs.** Wall clock: 3Laurel 18:19 -> 9:53, Q5446 9:02 -> 4:41.
2. **#2738 alone is neutral on throughput** (within noise on 3Laurel; -1 % CPU, -6.5 % RSS on Q5446). **#2738 composed with the stack costs nothing measurable** (0.546 vs 0.547, 0.530 vs 0.528) and its outputs match base. So the snapshot-identity comparison it adds does not conflict with the shared-record reuse in #2693.
3. This is the production code path with default (unmodified) behaviour; it does not by itself prove #2738's invariance tests - those remain GPT1's to produce.
