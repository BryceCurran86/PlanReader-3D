# GPT MAX PR run cancellation — public runner queues

**Goal:** Do not spend public-runner time executing an older PR commit after
an agent has already pushed a newer head. This is queue efficiency, not
a reduction in testing authority.

Exactly **25 existing** `test-gptmax-*.yml` workflows that had a
`pull_request` trigger and **no top-level concurrency** get:

```yaml
concurrency:
  group: test-gptmax-<unique-workflow-name>-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

The combination matters:
- On a PR, the unique workflow basename and PR number cancel only older
  runs for **that same workflow and PR**, including queued superseded heads.
- Different PR numbers remain independent.
- `main` pushes and manual `workflow_dispatch` runs use a unique
  `github.run_id`, and the cancellation condition is false. These are not
  removed or superseded by developer PRs.
- All original `on` filters, test commands, source PDF verification, matrix
  Python versions, test names, permissions and resource limits remain intact.
  **No frozen takeoff scores, source SHA, issuer lineage, accepted opening
  areas, or original-PDF handling changed.**
- Workflows that ALREADY had top-level concurrency were deliberately left
  alone; GPT3 has independently drafted #2995 for some other workflow lanes.

This PR does not automatically cancel queued runs created before the merge,
nor does it merge 232 workflows into one. Use the existing **CI**
`workflow_dispatch` modes in #3010 for a separate single-run focused,
full, or UNPUBLISHED V2 readiness entry point. Never run the original
private-PDF producer with an untrusted public PR token. Keep the repository
public on standard free GitHub runners.

Before disabling individual specialist workflow triggers, prove that their
extra source-positive, security and signed-customer gates run equivalently in
a consolidated workflow; otherwise a queue win would conceal regressions.
