import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CommandPreview } from "./CommandPreview";
import { isSceneManifest } from "./types";
import { nextStudy } from "./finishStudy";
import { ReviewWorkbench } from "./ReviewWorkbench";
import { applyDraft, draftHeightSuggestion, freshDrafts, redoDraft, safeDrafts, scopeKey, undoDraft } from "./reviewDraft";
import type { DraftHistory } from "./reviewDraft";
import type { SceneManifest } from "./types";

// Three.js/WebXR is optional. Keep the initial evidence inspector lightweight.
const SceneView = lazy(() => import("./Scene").then(m => ({ default: m.SceneView })));

export function App() {
  const [manifest, setManifest] = useState<SceneManifest | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Source-scoped, bounded, local-only visual proposals. No persistence or pricing.
  const [draftState, setDraftState] = useState<DraftHistory | null>(null);
  const [level, setLevel] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [authenticatedSource, setAuthenticatedSource] = useState(false);
  const pendingWorkspaceRequest = useRef<AbortController | null>(null);
  const handleSelect = useCallback((id: string | null) => setSelectedId(id), []);
  const handleCycleStudy = useCallback((objectId: string) => {
    if (!manifest) return;
    const row = manifest.objects.find(o => o.objectId === objectId) ?? null;
    setDraftState(current => {
      const state = current?.scopeKey === scopeKey(manifest) ? current : freshDrafts(manifest);
      const existing = safeDrafts(state, manifest).find(d => d.objectId === objectId);
      const next = nextStudy(row, existing?.swatch ? { objectId, swatch: existing.swatch } : null);
      return applyDraft(state, manifest, objectId, { swatch: next?.swatch ?? null });
    });
  }, [manifest]);

  // A production backend must authenticate this same-origin endpoint and
  // build the scope from the session, never from user-supplied model JSON.
  useEffect(() => {
    const workspace = new URLSearchParams(window.location.search).get("workspace");
    if (!workspace) return;
    let cancelled = false;
    const controller = new AbortController();
    pendingWorkspaceRequest.current = controller;
    setBusy(true);
    fetch(`/api/editor/workspaces/${encodeURIComponent(workspace)}/manifest`, {
      credentials: "include", headers: { Accept: "application/json" },
      cache: "no-store", signal: controller.signal,
    }).then(async response => {
      if (!response.ok) throw new Error(`Workspace API returned ${response.status}`);
      const data: unknown = await response.json();
      if (!isSceneManifest(data)) throw new Error("Invalid or untrusted scene manifest");
      if (data.scope.workspaceId !== workspace) throw new Error("Workspace identity mismatch");
      if (!cancelled && !controller.signal.aborted) {
        setManifest(data); setAuthenticatedSource(true); setError(null);
        setDraftState(freshDrafts(data)); setSelectedId(null);
      }
    }).catch(e => {
      if (!cancelled && !controller.signal.aborted)
        setError(e instanceof Error ? e.message : "Workspace failed to load");
    }).finally(() => {
      if (!cancelled && !controller.signal.aborted) setBusy(false);
    });
    return () => { cancelled = true; controller.abort(); };
  }, []);

  async function importManifest(file: File | undefined) {
    if (!file) return;
    // An in-flight authenticated fetch must not overwrite a user's explicitly
    // selected local review file after its response eventually arrives.
    pendingWorkspaceRequest.current?.abort();
    setBusy(false);
    setError(null);
    if (file.size > 25 * 1024 * 1024) {
      setError("The scene manifest exceeds the 25 MB local preview limit");
      return;
    }
    try {
      const data: unknown = JSON.parse(await file.text());
      if (!isSceneManifest(data)) throw new Error("Manifest failed source/scope validation");
      // Local files are user-supplied previews, NOT server-attested evidence.
      // Never render their claimed "verified" status as trusted green/FIRM.
      const localPreview: SceneManifest = {
        ...data,
        objects: data.objects.map(o => ({
          ...o, renderState: "review" as const,
          unresolvedIssues: [...new Set([...o.unresolvedIssues, "local_manifest_not_authenticated"])],
        })),
      };
      setManifest(localPreview);
      setDraftState(freshDrafts(localPreview));
      setAuthenticatedSource(false);
      setSelectedId(null);
      setLevel("all");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid JSON scene manifest");
    }
  }

  async function openSyntheticDemo() {
    pendingWorkspaceRequest.current?.abort();
    setBusy(false);
    setError(null);
    try {
      const response = await fetch("/synthetic-review-scene.json", { cache: "no-store" });
      if (!response.ok) throw new Error("Synthetic demo fixture unavailable");
      const result: unknown = await response.json();
      if (!isSceneManifest(result)) throw new Error("Synthetic manifest invalid");
      const syntheticPreview: SceneManifest = {
        ...result,
        objects: result.objects.map(o => ({
          ...o, renderState: "review" as const,
          unresolvedIssues: [...new Set([...o.unresolvedIssues, "synthetic_fixture_only"])],
        })),
      };
      setManifest(syntheticPreview);
      setDraftState(freshDrafts(syntheticPreview));
      setAuthenticatedSource(false);
      setSelectedId(null);
      setLevel("all");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Synthetic demo unavailable");
    }
  }

  const levels = useMemo(() => [...new Set(
    (manifest?.objects ?? []).map(o => o.levelId).filter((id): id is string => !!id)
  )].sort(), [manifest]);
  const visible = useMemo<SceneManifest | null>(() => manifest ? {
    ...manifest,
    objects: manifest.objects.filter(o => level === "all" || o.levelId === level),
  } : null, [manifest, level]);
  const selected = visible?.objects.find(o => o.objectId === selectedId) ?? null;
  const activeDraftState = manifest && draftState?.scopeKey === scopeKey(manifest)
    ? draftState : manifest ? freshDrafts(manifest) : null;
  const reviewCount = manifest?.objects.filter(o => o.unresolvedIssues.length > 0).length ?? 0;
  // Keyboard undo/redo works only outside editable fields and never changes PlanReader source.
  useEffect(() => {
    function keyDown(event: KeyboardEvent) {
      const target = event.target;
      if (target instanceof HTMLElement && (target.isContentEditable ||
          ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))) return;
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z") return;
      if (!manifest) return;
      event.preventDefault();
      setDraftState(current => {
        const state = current?.scopeKey === scopeKey(manifest) ? current : freshDrafts(manifest);
        return event.shiftKey ? redoDraft(state) : undoDraft(state);
      });
    }
    window.addEventListener("keydown", keyDown);
    return () => window.removeEventListener("keydown", keyDown);
  }, [manifest]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <span className="eyebrow">PLANREADER / BUILDING EVIDENCE</span>
          <h1>3D + VR Review</h1>
          <p>One building model. Source-owned identities. No unapproved quantities.</p>
        </div>
        <div className="header-state">
          <span className="state-dot" />
          <span>READ-ONLY EVIDENCE SCENE</span>
        </div>
      </header>

      <main className="workspace-layout">
        <section className="viewer-panel" aria-label="Building scene">
          {visible ? (
            <Suspense fallback={<div className="scene-loading" role="status">Loading 3D renderer…</div>}>
              <SceneView manifest={visible} selectedId={selectedId} onSelect={handleSelect} draftState={activeDraftState} onCycleStudy={handleCycleStudy} />
            </Suspense>
          ) : (
            <div className="viewer-empty">
              <div className="outline-icon">⌁</div>
              <h2>No source-bound workspace loaded</h2>
              <p>Open an authenticated workspace or import a local scene manifest generated by the PlanReader Python backend.</p>
              <p>Local files stay in your browser and are not submitted to any server.</p>
              <button className="demo-button" type="button" onClick={() => void openSyntheticDemo()}>
                Open synthetic 3D / VR example
              </button>
              <p>This demonstration contains no real construction source or measured quantities.</p>
            </div>
          )}
          <div className="viewer-footer">
            <span>Desktop: drag to orbit · scroll to zoom · click to inspect</span>
            <span>VR: HTTPS + headset · trigger selects · squeeze cycles temporary finish colours</span>
          </div>
        </section>

        <aside className="inspector" aria-label="Evidence inspector">
          <div className="section-block">
            <span className="eyebrow">WORKSPACE</span>
            <label className="file-upload">
              <span>Import scene manifest (local preview)</span>
              <input type="file" accept="application/json,.json"
                onChange={e => { void importManifest(e.currentTarget.files?.[0]); e.currentTarget.value = ""; }} />
            </label>
            {busy && <p className="muted">Loading authenticated workspace…</p>}
            {error && <p role="alert" className="error">{error}</p>}
            {manifest && (
              <div className="scope-info">
                <div><span>Project</span><strong>{manifest.scope.projectId}</strong></div>
                <div><span>Revision</span><strong>{manifest.scope.revisionId}</strong></div>
                <div><span>Snapshot</span><strong>{manifest.scope.snapshotId}</strong></div>
                <div><span>Objects</span><strong>{manifest.objects.length}</strong></div>
                <div><span>Needs review</span><strong>{reviewCount}</strong></div>
                <div><span>Source SHA</span><code title={manifest.scope.sourceSha256}>{manifest.scope.sourceSha256.slice(0, 14)}…</code></div>
              </div>
            )}
          </div>

          {manifest && (
            <div className="section-block">
              <label htmlFor="level-filter" className="eyebrow">LEVEL FILTER</label>
              <select id="level-filter" value={level}
                onChange={e => { setLevel(e.target.value); setSelectedId(null); }}>
                <option value="all">All source levels</option>
                {levels.map(id => <option value={id} key={id}>{id}</option>)}
              </select>
            </div>
          )}

          <div className="section-block detail">
            <span className="eyebrow">OBJECT INSPECTOR</span>
            {visible && visible.objects.length > 0 && (
              <select aria-label="Select building object" value={selectedId ?? ""}
                onChange={e => setSelectedId(e.target.value || null)}>
                <option value="">Select an object…</option>
                {visible.objects.map(o =>
                  <option value={o.objectId} key={o.objectId}>{o.objectId} · {o.objectType}</option>)}
              </select>
            )}
            {selected ? (
              <>
                <h2>{selected.objectId}</h2>
                <p><span className={selected.renderState === "verified" ? "pill verified" : "pill review"}>
                  {selected.renderState === "verified" ? "Verified geometry" : "Requires review"}
                </span></p>
                <dl>
                  <dt>Physical / canonical ID</dt><dd>{selected.canonicalObjectId ?? "Unresolved"}</dd>
                  <dt>Object revision</dt><dd>{selected.objectRevision || "Missing"}</dd>
                  <dt>Type</dt><dd>{selected.objectType}</dd>
                  <dt>Level</dt><dd>{selected.levelId ?? "Unresolved"}</dd>
                  <dt>Source drawing</dt><dd>{selected.source.sheet ?? "Missing"} / p. {selected.source.page ?? "?"}</dd>
                  <dt>Source primitive</dt><dd>{selected.source.originalGeometryRef ?? "Unresolved"}</dd>
                  {Object.entries(selected.dimensions).map(([key, value]) =>
                    <div key={key} className="dlrow"><dt>{key}</dt><dd>{value.toFixed(3)}</dd></div>)}
                </dl>
                {selected.unresolvedIssues.length > 0 &&
                  <div className="issues"><strong>Unresolved evidence</strong>
                    <ul>{selected.unresolvedIssues.map(issue => <li key={issue}>{issue.replace(/_/g, " ")}</li>)}</ul>
                  </div>}
                <div className="quantity-links">
                  Quantity references: {selected.quantityLinks.length
                    ? selected.quantityLinks.join(", ") : "None source-linked"}
                </div>
                {visible && activeDraftState && <ReviewWorkbench
                  key={visible.scope.snapshotId}
                  scene={manifest!} selected={selected} selectedLevel={level}
                  state={activeDraftState} onChange={setDraftState} />}
                <CommandPreview
                  key={`${visible!.scope.snapshotId}:${selected.objectId}:${selected.objectRevision}`}
                  workspace={visible!}
                  object={selected}
                  authenticated={authenticatedSource}
                  suggestion={activeDraftState && manifest
                    ? draftHeightSuggestion(selected, activeDraftState, manifest) : null}
                />
              </>
            ) : <p className="muted">Select a wall face or source line to inspect its identity, dimensions and unresolved evidence.</p>}
          </div>

          <div className="section-block caution">
            <strong>Commercial safety</strong>
            <p>This scene is for inspection only. Meshes do not establish wall thickness, scale, area or billable quantities. Corrections, approval and pricing remain in the existing authenticated PlanReader workflow.</p>
          </div>
        </aside>
      </main>
    </div>
  );
}
