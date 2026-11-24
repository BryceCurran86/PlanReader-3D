import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CommandPreview } from "./CommandPreview";
import { isSceneManifest } from "./types";
import { downgradeLocalManifest } from "./localManifestSafety";
import { nextStudy } from "./finishStudy";
import { ReviewWorkbench } from "./ReviewWorkbench";
import { ReviewNotesPanel } from "./ReviewNotesPanel";
import { PlanRevisionHistory } from "./PlanRevisionHistory";
import { WallAdditionPanel } from "./WallAdditionPanel";
import { BuildTools } from "./BuildTools";
import { VrDraftReviewPanel } from "./VrDraftReviewPanel";
import { AssemblyStudyPanel, useAssemblyStudy } from "./AssemblyStudyPanel";
import { saveVrReview, restoreVrReview } from "./vrDraftSave";
import { ConstructionView, ConstructionLayerPanel, StandardsPanel } from "./ConstructionView";
import type {LayerOverrides} from "./constructionLayers";
import {itemLayerVisible,itemLayer} from "./constructionLayers";
import { activeControl, EMPTY_RESIZE_HISTORY, historyShortcut, historyTarget, recordResize, stepResize } from "./editorControls";
import type { ControlMode, HistoryAction, HistoryTarget, ResizeHistory } from "./editorControls";
import { FootprintTools } from "./FootprintTools";
import { footprintBounds, footprintDepth, footprintWidth, originalPlacement, previewFootprint, sameFootprint, projectWall, projectCeiling } from "./footprintResize";
import type { FootprintBounds } from "./footprintResize";
import { CataloguePricingPanel } from "./CataloguePricingPanel";
import { isRoughIn } from "./constructionStages";
import type { ConstructionStage } from "./constructionStages";
import { ItemCataloguePanel } from "./ItemCataloguePanel";
import { getCatalogueItem, itemCanRotate } from "./itemCatalogue";
import { currentItemPlacements, emptyItemDraft, itemGuide, placeItem, redoItem, removeItem, undoItem } from "./itemPlacement";
import type { ItemDraft, ItemHit, PlacedItem } from "./itemPlacement";
import type { ItemAction } from "./catalogueMenu";
import { activeStart, buildGuide, EMPTY_BUILD, newPlacementId, STARTING_SIZES, updateBuild } from "./buildPlacement";
import type { BuildAction, BuildState, WallVisual } from "./buildPlacement";
import { LocalOutlinePanel } from "./LocalOutlinePanel";
import { PcVr2SetupPanel } from "./PcVr2SetupPanel";
import type { PcVrSessionReport } from "./PcVr2SetupPanel";
import { freshReviewNotes } from "./reviewNotes";
import type { ReviewNotesState } from "./reviewNotes";
import { applyDraft, draftHeightSuggestion, freshDrafts, redoDraft, safeDrafts, scopeKey, undoDraft } from "./reviewDraft";
import type { DraftHistory } from "./reviewDraft";
import { applyWallMove, freshWallMoves, redoWallMove, resetWallMoves, safeWallMoves, undoWallMove } from "./wallMoveStudy";
import type { MoveMode, WallMoveHistory } from "./wallMoveStudy";
import type { SceneManifest } from "./types";
import { VISUAL_PRESETS } from "./visualRealism";
import type { LightingMood, RenderQuality } from "./visualRealism";
import type { SurfaceDetail } from "./surfaceDetail";
import { DEFAULT_INSPECTION, filterEvidence, nextReview, sourceSheets, summarizeEvidence } from "./reviewInspection";
import { sourceDimensionCount } from "./sourceDimensions";
import type { CameraView, FocusTarget, InspectionSettings, ReviewFilter } from "./reviewInspection";

// Three.js/WebXR is optional. Keep the initial evidence inspector lightweight.
const SceneView = lazy(() => import("./Scene").then(m => ({ default: m.SceneView })));

type CatalogueSession = { scene: SceneManifest; itemId: string | null; turn: number; draft: ItemDraft };
const NO_ITEMS: readonly PlacedItem[] = [];

export function App() {
  const [manifest, setManifest] = useState<SceneManifest | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Source-scoped, bounded, local-only visual proposals. No persistence or pricing.
  const [draftState, setDraftState] = useState<DraftHistory | null>(null);
  const [addedWallSketch, setAddedWallSketch] = useState<WallVisual | null>(null);
  const [addedWallBatchSketches, setAddedWallBatchSketches] = useState<WallVisual[]>([]);
  const [placed, setPlaced] = useState<{ scene: SceneManifest; build: BuildState } | null>(null);
  const [buildSizes, setBuildSizes] = useState(STARTING_SIZES);
  const [buildHint, setBuildHint] = useState("");
  const [vrRate,setVrRate]=useState("");
  const [vrDraftStatus,setVrDraftStatus]=useState("");
  const [toolMessage, setToolMessage] = useState("");
  const [lastEdit, setLastEdit] = useState<HistoryTarget>("source");
  const [demoScene, setDemoScene] = useState<SceneManifest | null>(null);
  const [panel, setPanel] = useState<"plan" | "items" | "review" | "settings">("plan");
  const catalogueOpen = panel === "items";
  const [stage, setStage] = useState<ConstructionStage>("finished");
  const [layers,setLayers]=useState<LayerOverrides>({});
  const [resize, setResize] = useState<{
    scene: SceneManifest; enabled: boolean; hint: string;
  } & ResizeHistory | null>(null);
  const [catalogueSession, setCatalogueSession] = useState<CatalogueSession | null>(null);
  const [wallReview, setWallReview] = useState<{ scene: SceneManifest; proposalId: string; request: number } | null>(null);
  const wallReviewPanel = useRef<HTMLDetailsElement>(null);
  const planFile = useRef<HTMLInputElement>(null);
  const [wallMoveState, setWallMoveState] = useState<WallMoveHistory | null>(null);
  const [moveMode, setMoveMode] = useState<MoveMode>("inspect");
  const [moveError, setMoveError] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState<ReviewNotesState | null>(null);
  const [level, setLevel] = useState("all");
  const [lightingMood, setLightingMood] = useState<LightingMood>("daylight");
  const [renderQuality, setRenderQuality] = useState<RenderQuality>("balanced");
  const [surfaceDetail, setSurfaceDetail] = useState<SurfaceDetail>("smooth");
  const [inspection, setInspection] = useState<InspectionSettings>({ ...DEFAULT_INSPECTION });
  const [sourceSheet, setSourceSheet] = useState("");
  const [cameraRequest, setCameraRequest] = useState<{mode: CameraView; focus: FocusTarget; serial: number}>({mode:"isometric",focus:"scene",serial:0});
  const [clipboardMessage, setClipboardMessage] = useState<string | null>(null);
  const [captureSerial,setCaptureSerial]=useState(0);
  const [captureStatus,setCaptureStatus]=useState<string|null>(null);
  const [pcVrSession, setPcVrSession] = useState<PcVrSessionReport>({presenting:false,controllers:[]});
  const [teleportMode,setTeleportMode] = useState(false);
  const [teleportMessage,setTeleportMessage] = useState<string|null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [authenticatedSource, setAuthenticatedSource] = useState(false);
  const pendingLoad = useRef<AbortController | null>(null);
  const latestManifest = useRef(manifest);
  latestManifest.current=manifest;
  const handleSelect = useCallback((id: string | null) => {
    setSelectedId(id);
    setClipboardMessage(null);
    if (!id) setInspection(current => current.isolateSelected ? { ...current, isolateSelected: false } : current);
  }, []);
  const inspect = (patch: Partial<InspectionSettings>) =>
    setInspection(current => ({ ...current, ...patch }));
  const requestCamera = (mode: CameraView, focus: FocusTarget = "scene") =>
    setCameraRequest(current => ({ mode, focus, serial: current.serial + 1 }));
  async function copySelectedRef() {
    const row = manifest?.objects.find(o => o.objectId === selectedId);
    if (!row) return;
    const value = [
      manifest!.scope.projectId, manifest!.scope.documentId,
      manifest!.scope.revisionId, manifest!.scope.snapshotId,
      row.objectId, row.source.sheet ?? "unknown-sheet",
      row.source.page ?? "unknown-page",
      row.source.originalGeometryRef ?? "unresolved-source",
    ].join(" | ");
    try {
      await navigator.clipboard.writeText(value);
      setClipboardMessage("Copied source reference (not measurement authority).");
    } catch { setClipboardMessage("Clipboard permission denied."); }
  }
  const handleCycleStudy = useCallback((objectId: string) => {
    if (!manifest) return;
    setLastEdit("source");
    const row = manifest.objects.find(o => o.objectId === objectId) ?? null;
    setDraftState(current => {
      const state = current?.scopeKey === scopeKey(manifest) ? current : freshDrafts(manifest);
      const existing = safeDrafts(state, manifest).find(d => d.objectId === objectId);
      const next = nextStudy(row, existing?.swatch ? { objectId, swatch: existing.swatch } : null);
      return applyDraft(state, manifest, objectId, { swatch: next?.swatch ?? null });
    });
  }, [manifest]);

  const handleMoveDelta = useCallback((id: string, dx: number, dz: number) => {
    if (!manifest || moveMode !== "move") return;
    setLastEdit("wall-move");
    setWallMoveState(current => {
      const state = current?.scopeKey === scopeKey(manifest) ? current : freshWallMoves(manifest);
      const old = safeWallMoves(state, manifest).find(m => m.objectId === id);
      const proposed = applyWallMove(state, manifest, id,
        (old?.dx ?? 0) + dx, (old?.dz ?? 0) + dz);
      setMoveError(proposed.reason);
      return proposed.state;
    });
  }, [manifest, moveMode]);

  const startLoad = useCallback(() => {
    pendingLoad.current?.abort();
    const request = new AbortController();
    pendingLoad.current = request;
    setError(null);
    setBusy(true);
    return request;
  }, []);

  const finishLoad = useCallback((request: AbortController, result: SceneManifest | Error,
    origin: "workspace" | "local" | "demo",
  ) => {
    if (pendingLoad.current !== request || request.signal.aborted) return;
    pendingLoad.current = null;
    setBusy(false);
    if (result instanceof Error) {
      setError(result.message);
      return;
    }
    setManifest(result);
    setAuthenticatedSource(origin === "workspace");
    setDemoScene(origin === "demo" ? result : null);
    setDraftState(freshDrafts(result)); setReviewNotes(freshReviewNotes(result));
    setWallMoveState(freshWallMoves(result)); setMoveMode("inspect"); setMoveError(null);
    setTeleportMode(false); setTeleportMessage(null);
    setPlaced(null); setCatalogueSession(null); setResize(null);
    setAddedWallSketch(null); setAddedWallBatchSketches([]); setWallReview(null);
    setSelectedId(null); setClipboardMessage(null); setCaptureStatus(null);
    setInspection({ ...DEFAULT_INSPECTION }); setSourceSheet(""); setLevel("all");
    setStage("finished"); setPanel("plan"); setLastEdit("source");
    setBuildHint(""); setToolMessage("");setVrRate("");setVrDraftStatus("");
    setCameraRequest(current => ({ mode: "isometric", focus: "scene", serial: current.serial + 1 }));
  }, []);

  useEffect(() => {
    const workspace = new URLSearchParams(window.location.search).get("workspace");
    if (!workspace) return () => pendingLoad.current?.abort();
    const request = startLoad();
    void (async () => {
      try {
        const response = await fetch(`/api/editor/workspaces/${encodeURIComponent(workspace)}/manifest`, {
          credentials: "include", headers: { Accept: "application/json" },
          cache: "no-store", signal: request.signal,
        });
        if (!response.ok) {
          throw new Error(response.status === 401 || response.status === 403
            ? "Sign in to PlanReader to open this workspace, or open a local scene."
            : `Could not open the workspace (HTTP ${response.status}).`);
        }
        const data: unknown = await response.json();
        if (!isSceneManifest(data) || data.scope.workspaceId !== workspace)
          throw new Error("The workspace returned an invalid scene or different workspace ID.");
        finishLoad(request, data, "workspace");
      } catch (error) {
        finishLoad(request, error instanceof Error ? error : new Error("Workspace failed to load."), "workspace");
      }
    })();
    return () => { pendingLoad.current?.abort(); };
  }, [startLoad, finishLoad]);

  async function importManifest(file: File | undefined) {
    if (!file) return;
    const request = startLoad();
    try {
      if (file.size > 25 * 1024 * 1024) throw new Error("Choose a scene JSON file under 25 MB.");
      const data: unknown = JSON.parse(await file.text());
      if (!isSceneManifest(data)) throw new Error("Choose a valid PlanReader scene JSON file.");
      finishLoad(request, downgradeLocalManifest(data), "local");
    } catch (error) {
      const message = error instanceof SyntaxError ? "This file is not valid JSON." :
        error instanceof Error ? error.message : "Could not open this scene file.";
      finishLoad(request, new Error(message), "local");
    }
  }

  async function openSyntheticDemo() {
    const request = startLoad();
    try {
      const response = await fetch(new URL("synthetic-review-scene.json", window.location.href), {
        cache: "no-store", signal: request.signal,
      });
      if (!response.ok) throw new Error("The example scene could not be opened.");
      const data: unknown = await response.json();
      if (!isSceneManifest(data)) throw new Error("The example scene could not be read.");
      finishLoad(request, { ...data, objects: data.objects.map(object => ({
        ...object, renderState: "review",
        unresolvedIssues: [...new Set([...object.unresolvedIssues, "synthetic_fixture_only"])],
      })) }, "demo");
    } catch (error) {
      finishLoad(request, error instanceof Error ? error : new Error("The example scene is unavailable."), "demo");
    }
  }

  const levels = useMemo(() => [...new Set(
    (manifest?.objects ?? []).map(o => o.levelId).filter((id): id is string => !!id)
  )].sort(), [manifest]);
  const buildLevel = level === "all" ? (levels.length === 1 ? levels[0] : null) :
    levels.includes(level) ? level : null;
  const buildState = placed && placed.scene === manifest ? placed.build : EMPTY_BUILD;
  const catalogue = catalogueSession?.scene === manifest ? catalogueSession : null;
  const activeItem = getCatalogueItem(catalogue?.itemId ?? null);
  const isDemo = manifest !== null && manifest === demoScene;
  const baseFootprint = useMemo(() => manifest && footprintBounds(manifest, isDemo), [manifest, isDemo]);
  const scopedResize = resize?.scene === manifest ? resize : null;
  const projection = scopedResize?.projection ?? null;
  const studyGeometry=useMemo(()=>projection?{walls:buildState.walls.map(w=>projectWall(w,projection)),ceilings:buildState.ceilings.map(w=>projectCeiling(w,projection))}:{walls:buildState.walls,ceilings:buildState.ceilings},[projection,buildState.walls,buildState.ceilings]);
  const assemblyStudy=useAssemblyStudy(studyGeometry,manifest?JSON.stringify(manifest.scope):null);
  const resizeEnabled = scopedResize?.enabled ?? false;
  const activeFootprint = projection?.draft ?? baseFootprint;
  const sourceCommandsEnabled = authenticatedSource && !projection && !resizeEnabled;
  const mode = activeControl({ resize: resizeEnabled, place: !!activeItem, draw: !!buildState.tool,
    wallMove: moveMode === "move", teleport: teleportMode && sourceCommandsEnabled });
  const undoTarget = historyTarget(mode, lastEdit, !!projection);
  const canMoveSource = !projection && !resizeEnabled;

  function changeCatalogue(update: (previous: CatalogueSession) => CatalogueSession) {
    if (!manifest) return;
    setCatalogueSession(previous => update(previous?.scene === manifest ? previous : {
      scene: manifest, itemId: null, turn: 0, draft: emptyItemDraft(scopeKey(manifest)),
    }));
  }
  function exportLocalVrDraft() {
    if(!manifest)return;
    try {
      const text=saveVrReview(manifest,buildState,catalogue?.draft??null);
      const blob=new Blob([text],{type:"application/json"});
      const url=URL.createObjectURL(blob);
      const anchor=document.createElement("a");
      const safe=manifest.scope.projectId.replace(/[^a-zA-Z0-9_-]/g,"_").slice(0,64);
      anchor.href=url;anchor.download="planreader-vr-draft-"+safe+".json";
      document.body.append(anchor);anchor.click();anchor.remove();
      setTimeout(()=>URL.revokeObjectURL(url),30000);
      setVrDraftStatus("Local draft download requested. The original source and customer quantities were not modified.");
    } catch {
      setVrDraftStatus("Could not create a local draft download.");
    }
  }
  async function reopenLocalVrDraft(file:File) {
    const source=manifest;
    if(!source)return;
    if(file.size>3*1024*1024) {
      setVrDraftStatus("Draft file exceeds the 3 MB review limit.");return;
    }
    try {
      const data:unknown=JSON.parse(await file.text());
      if(latestManifest.current!==source)
        throw Error("The open source scene changed. Reopen this draft against its original snapshot.");
      const restored=restoreVrReview(source,data);
      setPlaced({scene:source,build:restored.build});
      setCatalogueSession({scene:source,itemId:null,turn:0,draft:restored.itemDraft});
      setLastEdit("draw");
      setVrDraftStatus("Review-only draft reopened for the exact original source snapshot. No customer records changed.");
    } catch(error) {
      setVrDraftStatus(error instanceof Error?error.message:"Could not read local VR draft.");
    }
  }
  function applyBuild(action: BuildAction) {
    if (!manifest) return;
    setPlaced(previous => {
      const current = previous?.scene === manifest ? previous.build : EMPTY_BUILD;
      const build = updateBuild(current, action, scopeKey(manifest), buildLevel, buildSizes);
      return build === current ? previous : { scene: manifest, build };
    });
  }

  function enterMode(next: ControlMode) {
    if (next !== "draw" && buildState.tool) applyBuild({ kind: "done" });
    if (next !== "place" && activeItem)
      changeCatalogue(current => ({ ...current, itemId: null }));
    if (next !== "resize" && resizeEnabled)
      setResize(current => current?.scene === manifest ? { ...current, enabled: false, drag: null } : current);
    if (next !== "wall-move" && moveMode === "move") setMoveMode("inspect");
    if (next !== "teleport" && teleportMode) setTeleportMode(false);
    setBuildHint(""); setToolMessage(""); setMoveError(null); setTeleportMessage(null);
  }

  function cancelTool() {
    if (mode === "inspect") handleSelect(null);
    else enterMode("inspect");
  }

  function openPanel(next: typeof panel) {
    if (next !== "items" && mode === "place") enterMode("inspect");
    setPanel(next);
  }

  function onItemAction(action: ItemAction) {
    if (action.kind === "choose") {
      const item = getCatalogueItem(action.itemId);
      if (!item) return;
      enterMode("place");
      if(layers[itemLayer(item)]==="hide")setLayers(current=>({...current,[itemLayer(item)]:"auto"}));
      if (!itemLayerVisible(stage,item,layers)) setStage(isRoughIn(item) ? "rough-in" : "finished");
      setPanel("items");
      setLastEdit("place");
      changeCatalogue(current => ({ ...current, itemId: item.id, turn: 0 }));
    } else if (action.kind === "undo" || action.kind === "redo") {
      setLastEdit("place");
      changeCatalogue(current => ({ ...current, draft: action.kind === "undo" ? undoItem(current.draft) : redoItem(current.draft) }));
    } else if (action.kind === "rotate") {
      if (activeItem && itemCanRotate(activeItem))
        changeCatalogue(current => ({ ...current, turn: (current.turn + 1) % 4 }));
    } else if (mode === "place") enterMode("inspect");
  }

  function placeSelectedItem(itemId: string, hit: ItemHit) {
    if (mode !== "place" || activeItem?.id !== itemId) return;
    if (projection) {
      const wall = hit.anchor?.kind === "wall" ? [...buildState.walls, ...activeBatchSketches,
        ...(activeAddedWallSketch ? [activeAddedWallSketch] : [])].find(row => "draft-wall:" + row.proposalId === hit.hostId) : undefined;
      hit = originalPlacement(hit, projection, wall);
    }
    const id = newPlacementId("item");
    const draft = catalogue && placeItem(catalogue.draft, scopeKey(catalogue.scene), id, itemId, hit, catalogue.turn);
    if (catalogue && draft === catalogue.draft) {
      setToolMessage(catalogue.draft.items.length >= 300 ? "This draft already has 300 placements." : "Choose a new location or a different item.");
      return;
    }
    setToolMessage("");
    setLastEdit("place");
    changeCatalogue(current => current.itemId === itemId ? { ...current,
      draft: placeItem(current.draft, scopeKey(current.scene), id, itemId, hit, current.turn),
    } : current);
  }

  function onBuildAction(action: BuildAction) {
    if (!manifest || ((projection || resizeEnabled) && action.kind !== "done" && action.kind !== "saved")) return;
    if(action.kind==="edit-local-outline" && (catalogue?.draft.items.length || catalogue?.draft.history.length || catalogue?.draft.future?.length)) return;
    if(action.kind==="rotate-local-wall"){
      const next=updateBuild(buildState,action,scopeKey(manifest),buildLevel,buildSizes);
      if(next===buildState){setToolMessage("Wall rotation rejected or unchanged. Check junctions, angle and opening clearance.");return;}
      if(catalogue?.draft.items.length){
        const collect=(walls:typeof buildState.walls)=>currentItemPlacements(catalogue.draft.items,manifest,
          [...activeBatchSketches,...walls,...(activeAddedWallSketch?[activeAddedWallSketch]:[])],isDemo,buildState.ceilings);
        const retained=new Set(collect(next.walls).map(i=>i.id));
        if(collect(buildState.walls).some(i=>!retained.has(i.id))){
          setToolMessage("Rotation blocked: a hosted item would no longer fit its wall. Move the item first.");return;
        }
      }
    }
    if (action.kind === "tool") {
      if (!buildLevel) return;
      if (buildState.tool === action.tool) {
        enterMode("inspect");
        return;
      }
      enterMode("draw");
      if (action.tool === "ceiling" && stage !== "finished") setStage("finished");
      else if (stage === "slab") setStage("framing");
    } else {
      setBuildHint(""); setToolMessage("");
    }
    if (action.kind !== "done") setLastEdit("draw");
    applyBuild(action);
  }

  function toggleFootprint() {
    if (!manifest || !baseFootprint) return;
    if (resizeEnabled) {
      enterMode("inspect");
      return;
    }
    enterMode("resize");
    requestCamera("plan");
    setLastEdit("resize");
    setResize(current => ({ ...(current?.scene === manifest ? current : EMPTY_RESIZE_HISTORY),
      scene: manifest, enabled: true, hint: "", drag: null }));
  }

  function resizeFootprint(bounds: FootprintBounds | null, drag?: symbol) {
    if (!manifest || !baseFootprint || !resizeEnabled) return;
    if (bounds && activeFootprint && sameFootprint(bounds, activeFootprint)) return;
    const walls = [...buildState.walls, ...activeBatchSketches, ...(activeAddedWallSketch ? [activeAddedWallSketch] : [])];
    const next = bounds ? previewFootprint(manifest, baseFootprint, bounds, walls, buildState.ceilings) :
      { projection: null, error: "Keep the corners separated and enter a positive width and depth." };
    const hint = next.error ?? "";
    setResize(previous => {
      if (previous?.scene !== manifest || !previous.enabled) return previous;
      const current = hint ? previous : recordResize(previous, next.projection, drag);
      return current.hint === hint ? current : { ...current, hint };
    });
  }

  function resetFootprint() {
    setLastEdit("resize");
    setResize(previous => previous?.scene === manifest ? { ...recordResize(previous, null), hint: "" } : previous);
  }

  function onStage(next: ConstructionStage) {
    if (next === stage) return;
    if ((activeItem && !itemLayerVisible(next,activeItem,layers)) || next === "slab" ||
        buildState.tool === "ceiling" && next !== "finished") enterMode("inspect");
    setStage(next);
  }

  function changeLevel(id: string) {
    if (id === level) return;
    enterMode("inspect");
    setLevel(id || "all");
    handleSelect(null);
    requestCamera(cameraRequest.mode);
  }

  function reviewWall(proposalId: string) {
    if (!manifest) return;
    enterMode("inspect");
    setPanel("review");
    setWallReview(previous => ({ scene: manifest, proposalId, request: (previous?.request ?? 0) + 1 }));
    requestAnimationFrame(() => {
      if (!wallReviewPanel.current) return;
      wallReviewPanel.current.open = true;
      wallReviewPanel.current.scrollIntoView({ block: "nearest" });
    });
  }
  const reviewDraft = wallReview && wallReview.scene === manifest
    ? buildState.walls.find(wall => wall.proposalId === wallReview.proposalId) ?? null : null;
  const allForLevel = useMemo(() => manifest ? filterEvidence(manifest, level, null, {
    ...DEFAULT_INSPECTION, reviewFilter: inspection.reviewFilter, search: inspection.search,
  }).filter(object => !sourceSheet || object.source.sheet === sourceSheet) : [],
  [manifest, level, inspection.reviewFilter, inspection.search, sourceSheet]);
  const selected = allForLevel.find(object => object.objectId === selectedId) ?? null;
  const isolateId = inspection.isolateSelected ? selected?.objectId : null;
  const visible = useMemo(() => manifest ? {
    ...manifest, objects: isolateId ? allForLevel.filter(object => object.objectId === isolateId) : allForLevel,
  } : null, [manifest, allForLevel, isolateId]);
  const visibleIds = useMemo(() => new Set(visible?.objects.map(object => object.objectId)), [visible]);
  const summaries = summarizeEvidence(visible?.objects ?? []);
  const sheets = sourceSheets(manifest?.objects ?? []);
  useEffect(() => {
    if (selectedId && !selected) handleSelect(null);
  }, [selectedId, selected, handleSelect]);
  const activeNotes = manifest && reviewNotes?.scopeKey === scopeKey(manifest)
    ? reviewNotes : manifest ? freshReviewNotes(manifest) : null;
  const activeDraftState = manifest && draftState?.scopeKey === scopeKey(manifest)
    ? draftState : manifest ? freshDrafts(manifest) : null;
  const activeWallMoves = manifest && wallMoveState?.scopeKey === scopeKey(manifest)
    ? wallMoveState : manifest ? freshWallMoves(manifest) : null;
  const currentMove = activeWallMoves && manifest
    ? safeWallMoves(activeWallMoves, manifest).find(m => m.objectId === selectedId)
    : undefined;
  const activeAddedWallSketch = visible && addedWallSketch?.scopeKey === scopeKey(visible)
    ? addedWallSketch : null;
  const activeBatchSketches = useMemo(() => visible ? addedWallBatchSketches.filter(
    sketch => sketch.scopeKey === scopeKey(visible),
  ) : [], [visible, addedWallBatchSketches]);
  const placedItems = useMemo(() => {
    if (!manifest || !catalogue) return NO_ITEMS;
    const drafts = [...activeBatchSketches, ...buildState.walls];
    if (activeAddedWallSketch) drafts.push(activeAddedWallSketch);
    return currentItemPlacements(catalogue.draft.items, manifest, drafts, isDemo, buildState.ceilings);
  }, [manifest, catalogue?.draft.items, activeBatchSketches, buildState.walls, buildState.ceilings, activeAddedWallSketch, isDemo]);
  const reviewCount = manifest?.objects.filter(o => o.unresolvedIssues.length > 0).length ?? 0;
  const movements = undoTarget === "wall-move" ? activeWallMoves :
    undoTarget === "source" ? activeDraftState : null;
  const canUndo = undoTarget === "draw" ? !projection && (!!buildState.history.length || !!activeStart(buildState, buildLevel)) :
    undoTarget === "place" ? !!catalogue?.draft.history.length :
    undoTarget === "resize" ? !!scopedResize?.past.length : !!movements?.past.length;
  const canRedo = undoTarget === "draw" ? !projection && !!buildState.future?.length :
    undoTarget === "place" ? !!catalogue?.draft.future?.length :
    undoTarget === "resize" ? !!scopedResize?.future.length : !!movements?.future.length;

  function stepHistory(action: HistoryAction) {
    if (!manifest || (action === "undo" ? !canUndo : !canRedo)) return;
    setToolMessage("");
    if (undoTarget === "draw") return onBuildAction({ kind: action });
    if (undoTarget === "place") return onItemAction({ kind: action });
    if (undoTarget === "resize") {
      setResize(current => current?.scene === manifest ? { ...stepResize(current, action), hint: "" } : current);
    } else if (undoTarget === "wall-move") {
      setWallMoveState(current => current?.scopeKey === scopeKey(manifest) ?
        (action === "undo" ? undoWallMove(current) : redoWallMove(current)) : current);
      setMoveError(null);
    } else {
      setDraftState(current => current?.scopeKey === scopeKey(manifest) ?
        (action === "undo" ? undoDraft(current) : redoDraft(current)) : current);
    }
  }

  const controlKeys = useRef<((event: KeyboardEvent) => void) | null>(null);
  controlKeys.current = event => {
    const target = event.target;
    if (!manifest || event.defaultPrevented ||
        (target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)))) return;
    if (event.key === "Escape") {
      event.preventDefault();
      cancelTool();
      return;
    }
    if (mode === "wall-move" && selected?.objectType === "wall" && selected.geometry &&
        !event.ctrlKey && !event.metaKey && !event.altKey) {
      const step = event.shiftKey ? 0.5 : 0.05;
      const offset = event.key === "ArrowUp" ? [0, -step] : event.key === "ArrowDown" ? [0, step] :
        event.key === "ArrowLeft" ? [-step, 0] : event.key === "ArrowRight" ? [step, 0] : null;
      if (offset) {
        event.preventDefault();
        handleMoveDelta(selected.objectId, offset[0], offset[1]);
        return;
      }
    }
    const action = historyShortcut(event);
    if (action) {
      event.preventDefault();
      stepHistory(action);
    }
  };
  useEffect(() => {
    const keyDown = (event: KeyboardEvent) => controlKeys.current?.(event);
    window.addEventListener("keydown", keyDown);
    return () => window.removeEventListener("keydown", keyDown);
  }, []);

  const canTeleport = sourceCommandsEnabled && !!manifest?.sourceSurfaces?.some(
    surface => surface.kind === "floor" && visibleIds.has(surface.objectId),
  );
  function toggleTeleport(enabled: boolean) {
    enterMode(enabled ? "teleport" : "inspect");
    setTeleportMode(enabled && canTeleport);
  }
  function reportHeadset(session: PcVrSessionReport) {
    if (pcVrSession.presenting && !session.presenting && teleportMode) toggleTeleport(false);
    setPcVrSession(session);
  }

  useEffect(() => {
    if (!canTeleport && teleportMode) setTeleportMode(false);
  }, [canTeleport, teleportMode]);

  const unresolved = allForLevel.some(object => object.unresolvedIssues.length > 0);
  const canMoveSelected = !!selected?.geometry && selected.objectType === "wall";
  const historyLabel = { draw: "draft geometry", place: "item placement", resize: "footprint resize",
    "wall-move": "wall position", source: "source study" }[undoTarget];
  const hint = toolMessage || (mode === "resize" ? "Drag a corner or enter a size." :
    mode === "place" && activeItem ? buildHint || itemGuide(activeItem) :
    mode === "draw" ? buildHint || buildGuide(buildState, buildLevel) :
    mode === "wall-move" ? "Select a source wall. Use the arrow keys or hold the headset grip to move it." :
    mode === "teleport" ? "In VR, point the trigger at a verified floor." :
    !buildLevel && levels.length > 1 ? "Choose a level to draw. Drag to orbit." :
    "Drag to orbit. Choose a tool to draw or place items.");
  const planKind = isDemo ? "Example plan" : authenticatedSource ? "PlanReader workspace" : "Local scene";
  const cameraOptions: readonly [CameraView, string][] = [
    ["isometric", "3D"], ["plan", "Plan"], ["north", "Front"], ["east", "Side"],
  ];
  const panels = manifest ? [["plan", "Plan"], ["items", "Items"], ["review", "Review"], ["settings", "Settings"]] as const :
    [["plan", "Plan"], ["settings", "Settings"]] as const;

  return <div className="app-shell">
    <header className="app-header">
      <h1>PlanReader 3D &amp; VR</h1>
      <div className="project-actions">
        {manifest && <span className="header-state">{planKind}</span>}
        <button type="button" onClick={() => planFile.current?.click()}>Open scene</button>
        <input ref={planFile} type="file" accept="application/json,.json" hidden
          onChange={event => { void importManifest(event.currentTarget.files?.[0]); event.currentTarget.value = ""; }} />
      </div>
    </header>
    {busy && <p className="load-message" role="status">Opening scene…</p>}
    {error && <p className="load-message error" role="alert">{error}</p>}

    <main className="workspace-layout">
      <section className="viewer-panel" aria-label="Building scene">
        {manifest ? <>
          <div className="view-toolbar" aria-label="Scene views">
            <ConstructionView stage={stage} onStage={onStage} />
            <ConstructionLayerPanel layers={layers} onLayers={setLayers}/>
            {levels.length > 1 && <label>Level
              <select value={level} onChange={event => changeLevel(event.currentTarget.value)}>
                <option value="all">All levels</option>
                {levels.map(id => <option key={id} value={id}>{id}</option>)}
              </select>
            </label>}
            <div className="tool-group" role="group" aria-label="Camera view">
              {cameraOptions.map(([orientation, label]) => <button key={orientation} type="button"
                aria-pressed={cameraRequest.mode === orientation && cameraRequest.focus === "scene"}
                onClick={() => requestCamera(orientation)}>{label}</button>)}
              <button type="button" disabled={!selected} onClick={() => requestCamera(cameraRequest.mode, "selected")}>
                Focus selection
              </button>
            </div>
            {activeFootprint && <button type="button" aria-expanded={resizeEnabled} onClick={toggleFootprint}>
              {projection ? "Edit footprint draft" : "Resize footprint"}
            </button>}
          </div>

          {activeFootprint && resizeEnabled && <FootprintTools box={activeFootprint} changed={!!projection}
            hint={scopedResize?.hint ?? ""} onApply={resizeFootprint} onReset={resetFootprint} onDone={toggleFootprint} />}
          {projection && activeFootprint && <p className="draft-notice" role="status">
            Footprint draft · {footprintWidth(activeFootprint).toFixed(2)} × {footprintDepth(activeFootprint).toFixed(2)} m
            {!resizeEnabled && <button type="button" onClick={resetFootprint}>Return to source size</button>}
          </p>}

          {buildLevel && <LocalOutlinePanel key={scopeKey(manifest)+":"+buildLevel}
            walls={buildState.walls.filter(w=>w.levelId===buildLevel&&w.scopeKey===scopeKey(manifest))}
            blocked={!!(projection||resizeEnabled||catalogue?.draft.items.length||catalogue?.draft.history.length||catalogue?.draft.future?.length)}
            onEdit={(expected,edit)=>{enterMode("inspect");onBuildAction({kind:"edit-local-outline",expected,edit});}} />}
          <BuildTools state={buildState} sizes={buildSizes} levelId={buildLevel}
            layoutEnabled={!projection && !resizeEnabled} hint={hint} onAction={onBuildAction} onSizes={setBuildSizes}
            onReview={reviewWall} catalogueOpen={catalogueOpen} busy={mode !== "inspect"}
            undoLabel={historyLabel} canUndo={canUndo} canRedo={canRedo}
            onUndo={() => stepHistory("undo")} onRedo={() => stepHistory("redo")} onDone={cancelTool}
            onCatalogueToggle={() => openPanel(catalogueOpen ? "review" : "items")} />
          {toolMessage && <span className="sr-only" role="status">{toolMessage}</span>}

          <div className="viewport">
            <Suspense fallback={<div className="scene-loading" role="status">Loading 3D viewer…</div>}>
              <SceneView manifest={manifest} visibleIds={visibleIds} level={level} levels={levels} onLevel={changeLevel}
                selectedId={selected?.objectId ?? null}
                onSelect={handleSelect} draftState={activeDraftState} onCycleStudy={handleCycleStudy}
                mood={lightingMood} quality={renderQuality} detail={surfaceDetail} inspection={inspection}
                cameraRequest={cameraRequest} captureSerial={captureSerial} onCapture={setCaptureStatus}
                mode={mode} canUndo={canUndo} canRedo={canRedo} onHistory={stepHistory} onDone={cancelTool}
                moveMode={canMoveSource ? moveMode : "inspect"} wallMoveState={activeWallMoves} onMoveDelta={handleMoveDelta}
                addedWallSketch={activeAddedWallSketch} addedWallSketches={activeBatchSketches}
                buildState={buildState} buildLevel={buildLevel} buildSizes={buildSizes} stage={stage} onStage={onStage} layers={layers} onLayers={setLayers}
                footprint={{ box: activeFootprint, projection, enabled: resizeEnabled, hint: scopedResize?.hint ?? "",
                  onToggle: toggleFootprint, onResize: resizeFootprint, onReset: resetFootprint }}
                onBuildAction={onBuildAction} onBuildHint={setBuildHint} onBuildSizes={setBuildSizes} onToolMessage={setToolMessage}
                catalogue={{ active: activeItem, items: placedItems, demo: isDemo,
                  canUndo: !!catalogue?.draft.history.length, turn: catalogue?.turn ?? 0,
                  onAction: onItemAction, onPlace: placeSelectedItem }}
                teleportMode={mode === "teleport" && canTeleport}
                teleportAvailable={canTeleport} onTeleportToggle={toggleTeleport}
                onTeleportMessage={setTeleportMessage}
                onPcVrSessionReport={reportHeadset} onExportLocalDraft={exportLocalVrDraft}
                onReviewLocalWall={reviewWall} budget={{summary:assemblyStudy.summary,onCapture:assemblyStudy.capture,onClear:assemblyStudy.clear}} />
            </Suspense>
          </div>
          <div className="viewer-footer">
            <span>Alt + drag to orbit with a tool active · Esc to finish · Ctrl/⌘ + Z to undo</span>
            <span>VR · trigger to select or place, hold to drag</span>
          </div>
        </> : <div className="viewer-empty">
          <h2>Open a scene to start</h2>
          <p>Choose a PlanReader scene JSON file or try the example plan.</p>
          <div className="empty-actions">
            <button type="button" onClick={() => planFile.current?.click()}>Open scene JSON</button>
            <button type="button" className="demo-button" onClick={() => void openSyntheticDemo()}>Open example</button>
          </div>
        </div>}
      </section>

      <aside className="inspector" aria-label="Plan tools">
        <div className="inspector-nav" role="group" aria-label="Plan tools sections">
          {panels.map(([id, title]) => <button key={id} type="button" aria-pressed={panel === id}
            aria-controls={"panel-" + id} onClick={() => openPanel(id)}>{title}</button>)}
        </div>

        <section id="panel-plan" hidden={panel !== "plan"} aria-label="Plan and revisions">
          <div className="section-block">
            <h2>{manifest ? planKind : "Scene files"}</h2>
            {manifest ? <div className="scope-info">
              <div><span>Project</span><strong>{manifest.scope.projectId}</strong></div>
              <div><span>Revision</span><strong>{manifest.scope.revisionId}</strong></div>
              <div><span>Snapshot</span><strong>{manifest.scope.snapshotId}</strong></div>
              <div><span>Objects</span><strong>{manifest.objects.length}</strong></div>
              <div><span>Needs review</span><strong>{reviewCount}</strong></div>
              {authenticatedSource && <div><span>Source SHA</span><code title={manifest.scope.sourceSha256}>{manifest.scope.sourceSha256.slice(0, 14)}…</code></div>}
            </div> : <p className="muted">Open a workspace from PlanReader or inspect a scene saved as JSON.</p>}
            {manifest && !isDemo && <button type="button" onClick={() => void openSyntheticDemo()}>Open example</button>}
          </div>
          {manifest && <div className="section-block">
            <PlanRevisionHistory key={manifest.scope.workspaceId + manifest.scope.snapshotId}
              workspace={manifest} authenticated={sourceCommandsEnabled} />
          </div>}
        </section>

        {manifest && <section id="panel-items" hidden={!catalogueOpen} aria-label="Items">
          <div className="section-block catalogue-section">
            <ItemCataloguePanel key={manifest.scope.snapshotId} active={activeItem} items={placedItems}
              canUndo={!!catalogue?.draft.history.length} turn={catalogue?.turn ?? 0}
              onChoose={itemId => onItemAction({ kind: "choose", itemId })}
              onCancel={() => onItemAction({ kind: "done" })}
              onRotate={() => onItemAction({ kind: "rotate" })}
              onUndo={() => onItemAction({ kind: "undo" })}
              onRemove={id => { setLastEdit("place"); changeCatalogue(current => ({ ...current, draft: removeItem(current.draft, id) })); }} />
          </div>
          <div className="section-block">
            <CataloguePricingPanel scene={manifest} items={placedItems} authenticated={sourceCommandsEnabled} />
          </div>
        </section>}

        {manifest && visible && <section id="panel-review" hidden={panel !== "review"} aria-label="Source and draft review">
          <VrDraftReviewPanel build={buildState} rate={vrRate} onRate={setVrRate}
            onSave={exportLocalVrDraft} onRestore={file=>{void reopenLocalVrDraft(file);}}
            status={vrDraftStatus}/>
          <AssemblyStudyPanel controller={assemblyStudy}/>
          <div className="section-block">
            <h2>Review source objects</h2>
            <label htmlFor="review-search">Find an object</label>
            <input id="review-search" type="search" value={inspection.search} maxLength={128}
              placeholder="Object ID, drawing or source reference" onChange={event => inspect({ search: event.currentTarget.value })} />
            <div className="review-fields">
              <label htmlFor="review-status">Evidence status
                <select id="review-status" value={inspection.reviewFilter}
                  onChange={event => inspect({ reviewFilter: event.currentTarget.value as ReviewFilter })}>
                  <option value="all">All objects</option><option value="verified">Verified only</option>
                  <option value="review">Needs review</option><option value="source-lines">Unknown-height walls</option>
                </select>
              </label>
              <label htmlFor="review-sheet">Drawing sheet
                <select id="review-sheet" value={sourceSheet} onChange={event => setSourceSheet(event.currentTarget.value)}>
                  <option value="">All sheets</option>{sheets.map(sheet => <option key={sheet} value={sheet}>{sheet}</option>)}
                </select>
              </label>
            </div>
            <div className="review-control-grid">
              <button type="button" disabled={!unresolved} onClick={() => handleSelect(nextReview(allForLevel, selectedId, -1))}>Previous issue</button>
              <button type="button" disabled={!unresolved} onClick={() => handleSelect(nextReview(allForLevel, selectedId, 1))}>Next issue</button>
              <button type="button" disabled={!selected} aria-pressed={!!isolateId}
                onClick={() => inspect({ isolateSelected: !isolateId })}>{isolateId ? "Clear isolation" : "Isolate selection"}</button>
              <button type="button" onClick={() => {
                inspect({ reviewFilter: "all", search: "", isolateSelected: false });
                setSourceSheet(""); handleSelect(null);
              }}>Clear filters</button>
            </div>
            <p className="muted">{summaries.total} shown · {summaries.verified} verified · {summaries.review} for review</p>
            {allForLevel.length > 0 && <label htmlFor="review-object">Selected object
              <select id="review-object" value={selected?.objectId ?? ""} onChange={event => handleSelect(event.currentTarget.value || null)}>
                <option value="">Select an object</option>
                {allForLevel.map(object => <option key={object.objectId} value={object.objectId}>{object.objectId} · {object.objectType}</option>)}
              </select>
            </label>}
            {!allForLevel.length && <p>No objects match the current filters.</p>}
          </div>

          {selected && <div className="section-block detail">
            <h2>{selected.objectId}</h2>
            <p><span className={selected.renderState === "verified" ? "pill verified" : "pill review"}>
              {selected.renderState === "verified" ? "Verified geometry" : "Requires review"}
            </span></p>
            <details>
              <summary>Source details</summary>
              <dl>
                <dt>Canonical ID</dt><dd>{selected.canonicalObjectId ?? "Unresolved"}</dd>
                <dt>Object revision</dt><dd>{selected.objectRevision || "Missing"}</dd>
                <dt>Type</dt><dd>{selected.objectType}</dd><dt>Level</dt><dd>{selected.levelId ?? "Unresolved"}</dd>
                <dt>Source drawing</dt><dd>{selected.source.sheet ?? "Missing"} / p. {selected.source.page ?? "?"}</dd>
                <dt>Source primitive</dt><dd>{selected.source.originalGeometryRef ?? "Unresolved"}</dd>
                {Object.entries(selected.dimensions).map(([key, value]) =>
                  <div key={key} className="dlrow"><dt>{key}</dt><dd>{value.toFixed(3)}</dd></div>)}
              </dl>
              <button className="review-source-copy" type="button" onClick={() => void copySelectedRef()}>Copy source reference</button>
              {clipboardMessage && <p role="status" className="muted">{clipboardMessage}</p>}
              <p className="quantity-links">Quantity references · {selected.quantityLinks.join(", ") || "None"}</p>
            </details>
            {selected.unresolvedIssues.length > 0 && <div className="issues">
              <strong>Unresolved evidence</strong>
              <ul>{selected.unresolvedIssues.map(issue => <li key={issue}>{issue.replace(/_/g, " ")}</li>)}</ul>
            </div>}
            <details>
              <summary>Source studies and verified edits</summary>
              {activeDraftState && <ReviewWorkbench key={manifest.scope.snapshotId} scene={manifest} selected={selected}
                selectedLevel={level} state={activeDraftState} onChange={state => { setLastEdit("source"); setDraftState(state); }} />}
              <CommandPreview key={`${visible.scope.snapshotId}:${selected.objectId}:${selected.objectRevision}`}
                workspace={visible} object={selected} authenticated={sourceCommandsEnabled}
                suggestion={activeDraftState ? draftHeightSuggestion(selected, activeDraftState, manifest) : null} />
            </details>
          </div>}

          <details className="section-block" ref={wallReviewPanel}>
            <summary>Wall construction drafts</summary>
            <WallAdditionPanel scene={manifest} authenticated={sourceCommandsEnabled}
              onSketch={setAddedWallSketch} reviewDraft={reviewDraft} reviewRequest={wallReview?.request ?? 0}
              onSaved={proposalId => onBuildAction({ kind: "saved", proposalId })}
              onExactDraft={(previous, wall) => onBuildAction({ kind: "adjust", previous, wall })}
              onBatchSketches={setAddedWallBatchSketches} />
          </details>

          {activeWallMoves && <details className="section-block vr-move-panel">
            <summary>Source wall position study</summary>
            <p className="muted">Drag a selected source wall with the headset grip, or nudge it with the arrow keys.</p>
            <label><input type="checkbox" checked={moveMode === "move"} disabled={!canMoveSource}
              onChange={event => {
                if (event.currentTarget.checked) {
                  enterMode("wall-move"); setMoveMode("move"); setLastEdit("wall-move");
                } else enterMode("inspect");
              }} /> Move source walls in a draft</label>
            {moveMode === "move" && <>
              <div className="review-control-grid">
                {([["Forward", 0, -.05], ["Back", 0, .05], ["Left", -.05, 0], ["Right", .05, 0]] as const).map(([label, x, z]) =>
                  <button type="button" key={label} disabled={!canMoveSelected}
                    onClick={() => selected && handleMoveDelta(selected.objectId, x, z)}>{label}</button>)}
                <button type="button" disabled={!activeWallMoves.moves.length}
                  onClick={() => { setWallMoveState(resetWallMoves(activeWallMoves)); setMoveError(null); setLastEdit("wall-move"); }}>
                  Reset wall positions
                </button>
              </div>
              {currentMove && <p className="muted">Offset · {currentMove.dx.toFixed(2)} m X / {currentMove.dz.toFixed(2)} m Z</p>}
              {moveError && <p className="error" role="alert">{moveError}</p>}
            </>}
          </details>}
          {activeNotes && <details className="section-block">
            <summary>Review notes</summary>
            <ReviewNotesPanel scene={manifest} selectedId={selected?.objectId ?? null}
              state={activeNotes} onChange={setReviewNotes}
              onSelect={id => {
                enterMode("inspect"); setInspection({ ...DEFAULT_INSPECTION });
                setLevel("all"); setSourceSheet(""); handleSelect(id);
                requestCamera(cameraRequest.mode, "selected");
              }} />
          </details>}
          <div className="section-block">
            <button type="button" disabled={!!projection || pcVrSession.presenting}
              onClick={() => { setCaptureStatus(null); setCaptureSerial(value => value + 1); }}>Export review image</button>
            {captureStatus && <p role="status" className="muted">{captureStatus}</p>}
          </div>
        </section>}

        <section id="panel-settings" hidden={panel !== "settings"} aria-label="Display and headset settings">
          <details className="section-block" open>
            <summary>Headset setup</summary>
            <PcVr2SetupPanel session={pcVrSession} />
            {manifest && <div className="vr-teleport-panel">
              <label className="vr-teleport-toggle">
                <input type="checkbox" checked={mode === "teleport" && canTeleport} disabled={!canTeleport}
                  onChange={event => toggleTeleport(event.currentTarget.checked)} />
                Teleport to verified floors in VR
              </label>
              {!canTeleport && <p className="muted">Open an authenticated plan and show a verified floor to use teleport.</p>}
              {teleportMessage && <p role="status" className="muted">{teleportMessage}</p>}
            </div>}
          </details>
          <div className="section-block">
            <h2>Display</h2>
            <label htmlFor="lighting-mood">Lighting
              <select id="lighting-mood" value={lightingMood} onChange={event => setLightingMood(event.currentTarget.value as LightingMood)}>
                {Object.entries(VISUAL_PRESETS).map(([id, preset]) => <option key={id} value={id}>{preset.label}</option>)}
              </select>
            </label>
            <label htmlFor="render-quality">Render quality
              <select id="render-quality" value={renderQuality} onChange={event => setRenderQuality(event.currentTarget.value as RenderQuality)}>
                <option value="balanced">Balanced</option><option value="high">High fidelity</option>
              </select>
            </label>
            <label htmlFor="surface-detail">Wall surface detail
              <select id="surface-detail" value={surfaceDetail} onChange={event => setSurfaceDetail(event.currentTarget.value as SurfaceDetail)}>
                <option value="smooth">Smooth</option><option value="subtle">Subtle texture</option>
              </select>
            </label>
            <div className="review-control-toggles">
              {([["showGrid", "Grid"], ["showShadows", "Shadows"], ["showLabels", "Selected label"],
                ["showGhosts", "Ghost heights"], ["showDimensions", "Source dimensions"]] as const)
                .map(([key, label]) => <label key={key}><input type="checkbox" checked={inspection[key]}
                  onChange={event => inspect({ [key]: event.currentTarget.checked })} /> {label}</label>)}
            </div>
            {manifest && <p className="muted">{sourceDimensionCount(visible?.objects ?? [])} source dimension labels available.</p>}
          </div>
          <div className="section-block"><StandardsPanel /></div>
        </section>
      </aside>
    </main>
  </div>;
}
