import { useEffect, useRef, useState } from "react";
import type { SceneManifest } from "./types";
import type { DraftHistory } from "./reviewDraft";
import { eligibleHeightTargets, makeHeightBatch } from "./batchRequest";
import { verifyBatchPreview } from "./batchProtocol";
import type { VerifiedBatchPreview } from "./batchProtocol";

type Props = { scene: SceneManifest; drafts: DraftHistory; authenticated: boolean };
export function BatchImpactPreview({ scene, drafts, authenticated }: Props) {
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<VerifiedBatchPreview | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const lease = useRef(0);
  const eligible = eligibleHeightTargets(scene, drafts);
  const snapshotKey = JSON.stringify([
    scene.scope.workspaceId, scene.scope.snapshotId, scene.scope.modelRevision,
    eligible.map(id => [id, drafts.drafts.find(d => d.objectId === id)?.heightM]),
  ]);

  // Any change in the source, selection or ghost height invalidates a remote receipt.
  useEffect(() => {
    lease.current += 1;
    controller.current?.abort();
    setBusy(false);
    setResult(null);
    setMessage(null);
    return () => { lease.current += 1; controller.current?.abort(); };
  }, [snapshotKey]);

  async function preview() {
    setMessage(null); setResult(null);
    if (!authenticated) {
      setMessage("An authenticated workspace is required; local JSON cannot request quantities.");
      return;
    }
    const csrf = document.querySelector<HTMLMetaElement>(
      'meta[name="planreader-csrf-token"]'
    )?.content;
    if (!csrf) { setMessage("Missing authenticated session CSRF token."); return; }
    let request;
    try {
      request = makeHeightBatch(scene, drafts, reason, () => crypto.randomUUID());
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Invalid source-bound batch");
      return;
    }
    controller.current?.abort();
    const c = new AbortController();
    controller.current = c;
    const id = ++lease.current;
    setBusy(true);
    try {
      const response = await fetch(
        `/api/editor/workspaces/${encodeURIComponent(scene.scope.workspaceId)}/commands/batch-preview`,
        {
          method: "POST", credentials: "include", cache: "no-store",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify(request), signal: c.signal,
        },
      );
      const raw: unknown = await response.json();
      if (!response.ok) {
        const detail = raw && typeof raw === "object" && "blockingReasons" in raw &&
          Array.isArray(raw.blockingReasons) ?
          raw.blockingReasons.filter((x): x is string => typeof x === "string").join("; ") :
          `Server rejected batch preview (${response.status})`;
        throw new Error(detail || "Preview unavailable");
      }
      const checked = verifyBatchPreview(raw, request);
      if (!c.signal.aborted && id === lease.current) setResult(checked);
    } catch (e) {
      if (!c.signal.aborted && id === lease.current)
        setMessage(e instanceof Error ? e.message : "Batch preview unavailable");
    } finally {
      if (id === lease.current) { setBusy(false); controller.current = null; }
    }
  }
  return (
    <div className="preview-section" aria-label="Authenticated batch impact">
      <span className="eyebrow">SOURCE-VERIFIED MULTI-WALL IMPACT · PREVIEW ONLY</span>
      <p className="muted">
        {eligible.length} proposed canonical heights eligible for source checks.
        Max 20 per request. All targets must independently pass original-source
        witness, tenant, canonical, revision and current snapshot validation.
      </p>
      <p className="muted">
        Each wall is independently previewed from the same original state.
        Effects are not cumulative. No prices, automatic edits or approved quotes.
      </p>
      <label htmlFor="vr-batch-reason">Drawing evidence / reason shared by proposed corrections</label>
      <textarea id="vr-batch-reason" rows={3} maxLength={1024}
        value={reason} onChange={e => setReason(e.target.value)}
        placeholder="Identify reviewed elevation, dimensions and source evidence..." />
      <button type="button" disabled={busy || !authenticated || !eligible.length || eligible.length > 20}
        onClick={() => void preview()}>
        {busy ? "Checking source witnesses…" : "Preview multiple wall quantities"}
      </button>
      {!authenticated && <p className="muted">Open an authenticated workspace to enable server checks.</p>}
      {message && <p className="error" role="alert">{message}</p>}
      {result && <div className="preview-results" role="status">
        <strong>REVIEW ONLY — {result.commands.length} source-checked independent previews</strong>
        <p>No rate estimate; no saving, approval or commercial publication.</p>
        <ul>{result.commands.map(c => <li key={c.commandId}>
          <strong>{c.targetObjectId}</strong> — {c.quantityImpacts.length} derived quantity impacts
          <ul>{c.quantityImpacts.map((q, i) => <li key={q.target + i}>
            {q.target}: {q.proposedValue === null ? "Manual review required" :
              `${q.proposedValue.toFixed(3)} ${q.unit}`} ({q.status})
          </li>)}</ul>
        </li>)}</ul>
        <p>Untrusted review receipt: <code>{result.receipt.slice(0, 16)}…</code></p>
      </div>}
    </div>
  );
}
