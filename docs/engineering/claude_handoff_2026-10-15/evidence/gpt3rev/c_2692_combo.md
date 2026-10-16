**Shipping-combination check for the resource stack (main + #2693 + #2694 + #2695 + #2705 + #2706 + #2784, branch `claude/resource-stack-integration-20261015`, head `a8eb952b`).** The individual performance PRs' own CI ran the Lot16 signed replay but not the Maryborough one (its path filter omits their files; #2781 closes that gap), so I dispatched both replays on the combined tree:

- Lot16 (run 38710205939) and Maryborough (run 38710210418), both success: `source_sealed_run.json` and `verified_customer_rows.json` are **byte-identical (`cmp`)** to the archived signed originals (Lot16 fp `ef58f8ae...` = 8 quantities; Maryborough fp `9f3ab9ac...` = 3 FIRM floors).
- Complete 3Laurel / Q5446 handoffs of that combination: 0.448x / 0.530x CPU, 0.654x / 0.631x peak RSS, every output file byte-identical to main (details on #2784).

Not a formal approval; release blocked by B1 and by independent review of the performance PRs by GPT1 / GPT3.
