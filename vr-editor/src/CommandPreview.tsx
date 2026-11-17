import { useState } from "react";
import type { EditorObject, SceneManifest } from "./types";

type Props = {
  workspace: SceneManifest;
  object: EditorObject;
  authenticated: boolean;
};

type QuantityImpact = {
  target: string;
  status: string;
  oldValue: number | null;
  proposedValue: number | null;
  unit: string;
  reason: string | null;
};
type Preview = {
  accepted: boolean;
  validationState: string;
  persisted: boolean;
  commercialPublicationAllowed: boolean;
  quantityImpacts?: QuantityImpact[];
  blockingReasons?: string[];
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

export function CommandPreview({ workspace, object, authenticated }: Props) {
  const available = CONTROLS[object.objectType] || [];
  const [kind, setKind] = useState(available[0]?.command ?? "");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const control = available.find(c => c.command === kind) ?? available[0];
  const sourceReady = !!object.canonicalObjectId && !!object.objectRevision;
  const enabled = authenticated && sourceReady && !!control;

  async function sendPreview() {
    setError(null);
    setPreview(null);
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
    setWorking(true);
    try {
      const response = await fetch(
        `/api/editor/workspaces/${encodeURIComponent(workspace.scope.workspaceId)}/commands/preview`,
        {
          method: "POST",
          credentials: "include",
          cache: "no-store",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify(command),
        }
      );
      const result: unknown = await response.json();
      if (!result || typeof result !== "object") throw new Error("Invalid preview response");
      const data = result as Preview;
      if (!response.ok || data.accepted !== true
          || data.persisted !== false || data.commercialPublicationAllowed !== false) {
        const issues = Array.isArray(data.blockingReasons)
          ? data.blockingReasons.join("; ") : `Preview rejected (${response.status})`;
        throw new Error(issues || "Source authority rejected preview");
      }
      setPreview(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview unavailable");
    } finally {
      setWorking(false);
    }
  }

  if (!available.length) return null;
  return (
    <div className="preview-section">
      <span className="eyebrow">CONTROLLED CORRECTION PREVIEW</span>
      <p className="muted">Preview uses current PlanReader correction formulas. No change is saved or approved.</p>
      {!enabled && <p className="error">Requires an authenticated workspace with a proven canonical object identity. Local JSON imports cannot submit commands.</p>}
      <label htmlFor="correction-kind">Proposed correction</label>
      <select id="correction-kind" value={kind} disabled={!enabled}
        onChange={e => { setKind(e.target.value); setValue(""); setPreview(null); }}>
        {available.map(c =>
          <option key={c.command} value={c.command}>{c.label}</option>)}
      </select>
      <label htmlFor="correction-value">Proposed value</label>
      <input id="correction-value" disabled={!enabled}
        type={control?.numeric ? "number" : "text"} step={control?.numeric ? "any" : undefined}
        min={control?.numeric ? "0.000001" : undefined}
        value={value} onChange={e => setValue(e.target.value)}
        placeholder={control?.numeric ? "Measured value in metres" : "Finish schedule code"}
      />
      <label htmlFor="correction-reason">Evidence / correction reason</label>
      <textarea id="correction-reason" disabled={!enabled}
        maxLength={1024} value={reason} rows={3}
        onChange={e => setReason(e.target.value)}
        placeholder="Identify the drawing, dimension or reviewed observation…"
      />
      <button type="button" disabled={!enabled || working} onClick={() => void sendPreview()}>
        {working ? "Checking source authority…" : "Preview quantity impact"}
      </button>
      {error && <p role="alert" className="error">{error}</p>}
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
