import { useEffect, useRef, useState } from "react";
import type { EditorObject, SceneManifest } from "./types";
import { verifyPreviewResponse } from "./previewProtocol";
import type { VerifiedPreview } from "./previewProtocol";
import { verifyLiveCostingResponse } from "./liveCostingProtocol";
import type { VerifiedCostPreview } from "./liveCostingProtocol";
import { verifySavedPlanRevision } from "./planRevisionProtocol";
import type { SavedPlanRevision } from "./planRevisionProtocol";

type Props = {
  workspace: SceneManifest;
  object: EditorObject;
  authenticated: boolean;
  suggestion?: { command: "SET_WALL_HEIGHT"; value: string; objectRevision: string } | null;
};

const CONTROLS: Record<string, { command: string; label: string; numeric: boolean }[]> = {
  wall: [
    { command: "SET_WALL_HEIGHT", label: "Wall height (m)", numeric: true },
    { command: "SET_WALL_LENGTH", label: "Wall length (m)", numeric: true },
    { command: "ASSIGN_WALL_FINISH", label: "Finish code", numeric: false },
  ],
  surface: [
    { command: "ASSIGN_SURFACE_FINISH", label: "Finish code", numeric: false },
  ],
};

export function CommandPreview({ workspace, object, authenticated, suggestion }: Props) {
  const available = CONTROLS[object.objectType] || [];
  const [kind, setKind] = useState(available[0]?.command ?? "");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<VerifiedPreview | null>(null);
  const [costPreview, setCostPreview] = useState<VerifiedCostPreview | null>(null);
  const [autoLive, setAutoLive] = useState(false);
  const [previewedCommand, setPreviewedCommand] = useState<Record<string, unknown> | null>(null);
  const [savingRevision, setSavingRevision] = useState(false);
  const [savedRevision, setSavedRevision] = useState<SavedPlanRevision | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const pendingSave = useRef<AbortController | null>(null);
  const previewRequestId = useRef(0);
  const pendingPreview = useRef<AbortController | null>(null);
  const control = available.find(c => c.command === kind) ?? available[0];
  const sourceReady = !!object.canonicalObjectId && !!object.objectRevision;
  const enabled = authenticated && sourceReady && !!control;

  function invalidatePreview() {
    previewRequestId.current += 1;
    pendingPreview.current?.abort();
    setWorking(false);
    setPreview(null);
    setCostPreview(null);
    setPreviewedCommand(null);
    setSaveError(null);
  }

  useEffect(() => {
    previewRequestId.current += 1;
    pendingPreview.current?.abort();
    setWorking(false);
    // A local visual study can only prefill this unsubmitted form, never
    // supply server authority, a reason, pricing or an approval.
    if (suggestion?.objectRevision === object.objectRevision &&
        available.some(c => c.command === suggestion.command)) {
      setKind(suggestion.command);
      setValue(suggestion.value);
    } else {
      setKind(available[0]?.command ?? "");
      setValue("");
    }
    setPreview(null);
    setCostPreview(null);
    setPreviewedCommand(null);
    setSavedRevision(null);
    setSaveError(null);
    return () => {
      previewRequestId.current += 1;
      pendingPreview.current?.abort();
      pendingSave.current?.abort();
    };
  }, [suggestion?.command, suggestion?.value, suggestion?.objectRevision, object.objectRevision]);

  // Opt-in, debounced LIVE repricing: never dispatch incomplete corrections,
  // and every typed change aborts the prior source/rate request.
  useEffect(() => {
    if (!autoLive || !enabled || reason.trim().length < 8 || !control) return;
    const trimmed = value.trim();
    if (!trimmed || (control.numeric &&
      (!Number.isFinite(Number(trimmed)) || Number(trimmed) <= 0))) return;
    const timer = window.setTimeout(() => { void sendPreview(true); }, 650);
    return () => window.clearTimeout(timer);
  }, [autoLive, enabled, kind, value, reason,
      object.objectRevision, workspace.scope.snapshotId, control?.numeric]);

  async function sendPreview(withCost: boolean) {
    setError(null);
    setPreview(null);
    setCostPreview(null);
    setPreviewedCommand(null);
    if (!enabled || !control) return;
    const csrf = document.querySelector<HTMLMetaElement>('meta[name="planreader-csrf-token"]')?.content;
    if (!csrf) {
      setError("An authenticated PlanReader CSRF token is required. Preview unavailable.");
      return;
    }
    const trimmed = value.trim();
    const newValue = control.numeric ? Number(trimmed) : trimmed;
    if (!trimmed || (control.numeric && (!Number.isFinite(newValue) || Number(newValue) <= 0))) {
      setError("Enter a positive finite measurement or a valid finish code.");
      return;
    }
    if (reason.trim().length < 8) {
      setError("Enter an evidence-based correction reason (at least 8 characters).");
      return;
    }
    const command = {
      commandId: crypto.randomUUID(),
      idempotencyKey: crypto.randomUUID(),
      workspaceId: workspace.scope.workspaceId,
      projectId: workspace.scope.projectId,
      documentId: workspace.scope.documentId,
      revisionId: workspace.scope.revisionId,
      snapshotId: workspace.scope.snapshotId,
      sourceSha256: workspace.scope.sourceSha256,
      baseModelRevision: workspace.scope.modelRevision,
      targetObjectId: object.objectId,
      targetRevisionHash: object.objectRevision,
      targetCanonicalId: object.canonicalObjectId,
      commandType: control.command,
      payload: { newValue },
      reason: reason.trim(),
    };
    const requestId = ++previewRequestId.current;
    pendingPreview.current?.abort();
    const controller = new AbortController();
    pendingPreview.current = controller;
    setWorking(true);
    try {
      const response = await fetch(
        `/api/editor/workspaces/${encodeURIComponent(workspace.scope.workspaceId)}/${withCost ? "costing/preview" : "commands/preview"}`,
        {
          method: "POST",
          credentials: "include",
          cache: "no-store",
          signal: controller.signal,
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify(command),
        }
      );
      const result: unknown = await response.json();
      if (!response.ok) {
        const issues = result && typeof result === "object" &&
          "blockingReasons" in result && Array.isArray(result.blockingReasons)
          ? result.blockingReasons.filter((issue): issue is string => typeof issue === "string").join("; ")
          : `Preview rejected (${response.status})`;
        throw new Error(issues || "Source authority rejected preview");
      }
      const live = withCost ? verifyLiveCostingResponse(
        result, {
          ...command, targetRevisionHash: object.objectRevision,
          workspaceId: workspace.scope.workspaceId,
          snapshotId: workspace.scope.snapshotId,
        }
      ) : null;
      const validated = live?.quantityPreview ?? verifyPreviewResponse(result, command);
      if (requestId === previewRequestId.current && !controller.signal.aborted) {
        setPreview(validated);
        setCostPreview(live?.costingPreview ?? null);
        setPreviewedCommand(command);
      }
    } catch (e) {
      if (requestId === previewRequestId.current && !controller.signal.aborted)
        setError(e instanceof Error ? e.message : "Preview unavailable");
    } finally {
      if (requestId === previewRequestId.current) {
        pendingPreview.current = null;
        setWorking(false);
      }
    }
  }

  async function saveRevision() {
    if (!preview || !previewedCommand || !enabled || savingRevision) return;
    const csrf = document.querySelector<HTMLMetaElement>('meta[name="planreader-csrf-token"]')?.content;
    if (!csrf) {
      setSaveError("Authenticated workspace CSRF token required.");
      return;
    }
    pendingSave.current?.abort();
    const controller = new AbortController();
    pendingSave.current = controller;
    setSavingRevision(true);
    setSaveError(null);
    try {
      const response = await fetch(
        `/api/editor/workspaces/${encodeURIComponent(workspace.scope.workspaceId)}/revisions`,
        {
          method: "POST", credentials: "include", cache: "no-store",
          signal: controller.signal,
          headers: {"Content-Type":"application/json","X-CSRF-Token":csrf},
          body: JSON.stringify(previewedCommand),
        }
      );
      const body: unknown = await response.json();
      if (!response.ok) {
        const issue = body && typeof body === "object" && "error" in body &&
          typeof body.error === "string" ? body.error : "revision_save_rejected";
        throw new Error(`Could not save a complete, source-verified drawing revision: ${issue}`);
      }
      const saved = verifySavedPlanRevision(body, workspace);
      if (!controller.signal.aborted) {
        setSavedRevision(saved);
        setPreviewedCommand(null);
        setPreview(null);
        setCostPreview(null);
        setAutoLive(false);
        setError(null);
      }
    } catch (e) {
      if (!controller.signal.aborted)
        setSaveError(e instanceof Error ? e.message : "Revision save unavailable");
    } finally {
      if (!controller.signal.aborted) {
        pendingSave.current = null;
        setSavingRevision(false);
      }
    }
  }

  if (!available.length) return null;
  return (
    <div className="preview-section">
      <span className="eyebrow">CONTROLLED CORRECTION PREVIEW</span>
      <p className="muted">Preview uses current PlanReader correction formulas. No change is saved or approved.</p>
      {suggestion && <p className="muted">Illustrative VR height prefilled for review; explicitly submit with a source-based reason to request a server-side impact preview.</p>}
      {!enabled && <p className="error">Requires an authenticated workspace with a proven canonical object identity. Local JSON imports cannot submit commands.</p>}
      <label htmlFor="correction-kind">Proposed correction</label>
      <select id="correction-kind" value={kind} disabled={!enabled}
        onChange={e => { invalidatePreview(); setKind(e.target.value); setValue(""); }}>
        {available.map(c =>
          <option key={c.command} value={c.command}>{c.label}</option>)}
      </select>
      <label htmlFor="correction-value">Proposed value</label>
      <input id="correction-value" disabled={!enabled}
        type={control?.numeric ? "number" : "text"} step={control?.numeric ? "any" : undefined}
        min={control?.numeric ? "0.000001" : undefined}
        value={value} onChange={e => { invalidatePreview(); setValue(e.target.value); }}
        placeholder={control?.numeric ? "Measured value in metres" : "Finish schedule code"}
      />
      <label htmlFor="correction-reason">Evidence / correction reason</label>
      <textarea id="correction-reason" disabled={!enabled}
        maxLength={1024} value={reason} rows={3}
        onChange={e => { invalidatePreview(); setReason(e.target.value); }}
        placeholder="Identify the drawing, dimension or reviewed observation…"
      />
      <label className="live-cost-auto">
        <input type="checkbox" disabled={!enabled} checked={autoLive}
          onChange={e => {
            invalidatePreview();
            setAutoLive(e.target.checked);
          }}/>
        Live update after changes (650 ms pause, verified source and company rates required)
      </label>
      <div className="live-cost-actions">
        <button type="button" disabled={!enabled || working}
          onClick={() => void sendPreview(false)}>
          {working ? "Checking source authority…" : "Preview quantity only"}
        </button>
        <button type="button" disabled={!enabled || working}
          onClick={() => void sendPreview(true)}>
          {working ? "Calculating source-checked costs…" : "Recalculate live costs"}
        </button>
      </div>
      <p className="muted">Live costs use the logged-in company's current server-owned rate book. Prices cannot be supplied by the browser; missing rates remain unpriced.</p>
      {preview && previewedCommand && !savedRevision && (
        <div className="plan-edit-save-panel">
          <strong>Save an updated drawing set</strong>
          <p className="muted">
            Save a new immutable PDF version. Every independently verified
            related sheet receives a review revision annotation; original
            geometry is not automatically redrawn, and every page still
            requires drawing coordination. Unverified links block the save.
          </p>
          <button type="button" disabled={working || savingRevision || !enabled}
            onClick={() => void saveRevision()}>
            {savingRevision ? "Saving verified related pages…" :
              "Save new plan revision and linked pages"}
          </button>
        </div>
      )}
      {saveError && <p role="alert" className="error">{saveError}</p>}
      {savedRevision && (
        <div className="plan-edit-saved" role="status">
          <strong>Saved {savedRevision.revisionLabel} · review copy</strong>
          <p>Updated {savedRevision.pagesRevised.length} source-verified page(s).
            Existing source PDF preserved; geometry was NOT redrawn.</p>
          <ul>{savedRevision.pagesRevised.map(page =>
            <li key={page.pageIndex}>Page {page.pageLabel} · {page.sheet}
              · {page.relationship === "origin" ? "edited source" : "verified cross-sheet link"}
            </li>)}</ul>
          <a href={savedRevision.downloadPath} download>
            Download saved revised PDF
          </a>
          <p className="muted">
            Correction history and revised PDF committed together. Reload
            the workspace to load the new model revision before another edit.
            Commercial approval remains separate.
          </p>
        </div>
      )}
      {error && <p role="alert" className="error">{error}</p>}
      {costPreview && (
        <div role="status" className="preview-results live-cost-results" aria-label="Unapproved live cost preview">
          <strong>WHAT-IF COSTING — NOT AN APPROVED QUOTE</strong>
          <p className="muted">
            Company rate revision: {costPreview.rateBookRevision} · {costPreview.currency}
            · Tax: {costPreview.taxPct}% · Contingency: {costPreview.contingencyPct}%.
          </p>
          <p className="muted">
            {costPreview.pricedComplete
              ? "All recalculated impacts have explicit rates. The correction is still unapproved."
              : "PARTIAL COST TOTALS — unresolved targets or missing rates prevent a complete estimate."}
          </p>
          <div className="live-cost-summary">
            <div><span>Before (inc. tax)</span><strong>{costPreview.lines.length ? `${costPreview.currency} ${costPreview.totals.before.sellIncTax}` : "UNPRICED"}</strong></div>
            <div><span>After (inc. tax)</span><strong>{costPreview.lines.length ? `${costPreview.currency} ${costPreview.totals.after.sellIncTax}` : "UNPRICED"}</strong></div>
            <div><span>Change (inc. tax)</span><strong>{costPreview.lines.length ? `${costPreview.currency} ${costPreview.totals.delta.sellIncTax}` : "UNPRICED"}</strong></div>
            <div><span>Direct cost change</span><strong>{costPreview.currency} {costPreview.totals.delta.direct}</strong></div>
            <div><span>Margin change</span><strong>{costPreview.currency} {costPreview.totals.delta.margin}</strong></div>
            <div><span>Tax change</span><strong>{costPreview.currency} {costPreview.totals.delta.tax}</strong></div>
          </div>
          {costPreview.lines.length > 0 && <div>
            <strong>Source-priced quantity impacts</strong>
            <ul>{costPreview.lines.map(line => <li key={line.target}>
              <strong>{line.target}</strong> · {line.previousQuantity} → {line.proposedQuantity} {line.unit}
              · Rate: {line.rateKey}
              <p>Before {costPreview.currency} {line.before.sellIncTax}
                · After {costPreview.currency} {line.after.sellIncTax}
                · Delta {costPreview.currency} {line.deltaIncTax}</p>
            </li>)}</ul>
          </div>}
          {costPreview.unpriced.length > 0 && <div>
            <strong>Not priced — manual review or rate binding required</strong>
            <ul>{costPreview.unpriced.map(item =>
              <li key={item.target}>{item.target}: {item.reason.replace(/_/g, " ")}</li>)}</ul>
          </div>}
          <p className="muted">Rate snapshot {costPreview.rateBookRevision} · Receipt {costPreview.costPreviewReceiptSha256.slice(0,16)}…</p>
          <p className="muted">No original drawing, canonical measurement, approved quote, invoice or JobHub price has been changed.</p>
        </div>
      )}
      {preview && (
        <div role="status" className="preview-results">
          <strong>Proposal only — not persisted or commercially approved</strong>
          {preview.quantityImpacts?.length ? (
            <ul>{preview.quantityImpacts.map((q, i) =>
              <li key={q.target + i}><strong>{q.target}</strong>: {
                q.proposedValue === null ? "Needs manual review" : `${q.proposedValue.toFixed(3)} ${q.unit}`
              } ({q.status})</li>)}</ul>
          ) : <p>No supported quantity formula; manual review required.</p>}
        </div>
      )}
    </div>
  );
}
