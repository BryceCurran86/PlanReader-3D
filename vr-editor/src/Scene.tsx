import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { VRButton } from "three/addons/webxr/VRButton.js";
import type { EditorObject, SceneManifest } from "./types";
import { studyColor } from "./finishStudy";
import { safeDrafts } from "./reviewDraft";
import type { DraftHistory, WallDraft } from "./reviewDraft";
import { maxRenderPixelRatio, mayRenderWallFace, shadowMapSize, VISUAL_PRESETS } from "./visualRealism";
import type { LightingMood, RenderQuality } from "./visualRealism";
import { createPresentationRoughnessTile, sourceWallUV } from "./surfaceDetail";
import type { SurfaceDetail } from "./surfaceDetail";
import type { SourceSurface } from "./sourceSurfaces";
import { activeStart, buildGuide, newPlacementId, rotatedDraftWall,
  translatedDraftWall, validWallLength, viewRelativeNudge } from "./buildPlacement";
import type { WallAxis, WallRotationPivot } from "./buildPlacement";
import type { BuildAction, BuildHit, BuildSizes, BuildState, WallVisual } from "./buildPlacement";
import { aimBuild, beginDraftGesture, createBuildOverlay, displayCeilingDraft,
  displayWallDraft, draftGesturePreview, magneticDraftWalls } from "./buildScene";
import type { DraftGesture } from "./buildScene";
import { roofEdges } from "./roofComponents";
import { CATALOGUE_DRAG_TYPE, OPENING_DRAG_TYPE, CONSTRUCTION_STAGES } from "./constructionStages";
import type { ConstructionStage } from "./constructionStages";
import { getCatalogueItem } from "./itemCatalogue";
import type { ControlMode, HistoryAction } from "./editorControls";
import { createFootprintGizmo, footprintGeometry, projectSourceHost, renderFootprintGeometry } from "./footprintScene";
import { footprintHandlePoint, projectCeiling, projectPlacement, projectWall, projectPlan, resizeFromHandle } from "./footprintResize";
import type { FootprintBounds, FootprintHandle, FootprintProjection } from "./footprintResize";
import { catalogueWallHost, createCatalogueScene, demoCatalogueHosts, draftCatalogueHosts, draftSiteHost } from "./catalogueScene";
import type { CatalogueHost } from "./catalogueScene";
import { buildMenuLayout, EMPTY_ITEM_BROWSER, updateItemBrowser } from "./catalogueMenu";
import type { ItemAction, MenuAction, NumericDraftField } from "./catalogueMenu";
import { verifiedSourceWallAnchors } from "./vrDraftSourceSnaps";
import { createVrPlanOverview } from "./vrPlanOverview";
import { standardThumbstick, walkDelta, collisionLimitedStep, snapTurn, navigationOffset, identityNavOffset, composeNavigationOffset, navigationWallFace } from "./vrStationaryNavigation";
import type { NavigationWall, NavOffset } from "./vrStationaryNavigation";
import {doorKey,localNavigationWalls} from "./walkthroughDoors";
import { budgetHeadline } from "./vrAssemblyStudy";
import { defaultWallAssembly, wallAssembly, wallDimensionText, profileDetails } from "./wallProfiles";
import {chooseWallAim,wallAimWithin,MAGNET_RELEASE} from "./wallMagnet";
import type {WallAim,WallTarget} from "./wallMagnet";
import {displayedMenuAction,thumbstickSector} from "./toolWheelInput";
import {createWallTextureLibrary} from "./wallTextures";
import {layerVisible,surfaceLayerVisible,cycleLayer,itemLayerVisible} from "./constructionLayers";
import type {LayerOverrides} from "./constructionLayers";
import type { ImmersiveBudget } from "./vrAssemblyStudy";
import type { CatalogueItem } from "./itemCatalogue";
import { ceilingDraftHostId, itemGuide, makeItemHostId } from "./itemPlacement";
import type { ItemHit, PlacedItem } from "./itemPlacement";
import { evaluateSourceFloorTeleport,describeTeleportReason } from "./verifiedTeleport";
import { scopeKey } from "./reviewDraft";
import { safeWallMoves } from "./wallMoveStudy";
import type { MoveMode, WallMoveHistory } from "./wallMoveStudy";
import { PcVrSqueezeTracker, inspectPcVrController, standardSqueezePressed } from "./pcVr2Support";
import type { PcVrControllerInfo, PcVrInputSource } from "./pcVr2Support";
import type { PcVrSessionReport } from "./PcVr2SetupPanel";
import { drawReviewStamp, reviewStamp, safeCaptureSize } from "./reviewCapture";
import type { CameraView, FocusTarget, InspectionSettings } from "./reviewInspection";
import { sourceWallDimensions } from "./sourceDimensions";
import {reviewDimensions} from "./vrDesignReview";
import type {DraftShell} from "./connectedDraftShell";
import {reviewOpeningCorners} from "./sourceOpeningReview";

type Props = {
  manifest: SceneManifest;
  visibleIds: ReadonlySet<string>;
  level: string;
  levels: readonly string[];
  onLevel: (level: string) => void;
  mode: ControlMode;
  canUndo: boolean;
  canRedo: boolean;
  onHistory: (action: HistoryAction) => void;
  onDone: () => void;
  toolFeedback?:string;
  onToolMessage: (message: string) => void;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  draftState: DraftHistory | null;
  onCycleStudy: (objectId: string) => void;
  mood: LightingMood;
  onMood:(mood:LightingMood)=>void;
  previewLights:boolean;
  onPreviewLights:(enabled:boolean)=>void;
  quality: RenderQuality;
  detail: SurfaceDetail;
  moveMode: MoveMode;
  addedWallSketch: WallVisual | null;
  addedWallSketches: WallVisual[];
  buildState: BuildState;
  buildLevel: string | null;
  buildSizes: BuildSizes;
  stage: ConstructionStage;
  onStage: (stage: ConstructionStage) => void;
  layers:LayerOverrides;
  onLayers:(layers:LayerOverrides)=>void;
  allDimensions:boolean;
  shell:DraftShell|null;
  onAllDimensions:(value:boolean)=>void;
  footprint: {
    box: FootprintBounds | null;
    projection: FootprintProjection | null;
    enabled: boolean;
    hint: string;
    onToggle: () => void;
    onResize: (box: FootprintBounds | null, drag?: symbol) => void;
    onReset: () => void;
  };
  onBuildAction: (action: BuildAction) => void;
  onBuildHint: (hint: string) => void;
  onBuildSizes:(sizes:BuildSizes)=>void;
  catalogue: {
    active: CatalogueItem | undefined;
    items: readonly PlacedItem[];
    demo: boolean;
    canUndo: boolean;
    turn: number;
    onAction: (action: ItemAction) => void;
    onPlace: (itemId: string, hit: ItemHit) => void;
  };
  teleportMode: boolean;
  teleportAvailable:boolean;
  onTeleportToggle:(enabled:boolean)=>void;
  onExportLocalDraft:()=>void;
  onReviewLocalWall:(proposalId:string)=>void;
  budget:{summary:ImmersiveBudget;onCapture:()=>void;onClear:()=>void};
  onTeleportMessage: (message: string) => void;
  wallMoveState: WallMoveHistory | null;
  onMoveDelta: (objectId: string, dx: number, dz: number) => void;
  captureSerial: number;
  onCapture: (message:string)=>void;
  onPcVrSessionReport: (status: PcVrSessionReport) => void;
  inspection: InspectionSettings;
  cameraRequest: {mode: CameraView; focus: FocusTarget; serial: number};
};

function point2(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length === 2 &&
    value.every((v) => typeof v === "number" && Number.isFinite(v));
}

function displayObject(row: EditorObject, roughness: number): THREE.Object3D | null {
  const shape = row.geometry;
  if (!shape || !point2(shape.start) || !point2(shape.end)) return null;
  const a = new THREE.Vector3(shape.start[0], 0, shape.start[1]);
  const b = new THREE.Vector3(shape.end[0], 0, shape.end[1]);
  if (a.distanceTo(b) <= 1e-8) return null;
  const trustworthy = row.renderState === "verified" &&
    row.unresolvedIssues.length === 0;
  const color = trustworthy ? 0xe8e4dc : 0xd5a56d;
  const name = row.objectId;
  if (shape.kind === "wallFace" && mayRenderWallFace(shape.kind, shape.heightM)) {
    const h = shape.heightM;
    const data = new Float32Array([
      a.x, 0, a.z, b.x, 0, b.z, b.x, h, b.z,
      a.x, 0, a.z, b.x, h, b.z, a.x, h, a.z,
    ]);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(data, 3));
    const surfaceUV = sourceWallUV(a.distanceTo(b), h);
    if (surfaceUV) geometry.setAttribute("uv", new THREE.BufferAttribute(surfaceUV, 2));
    geometry.computeVertexNormals();
    const material = new THREE.MeshStandardMaterial({
      color,
      transparent: false,
      opacity: 1,
      side: THREE.DoubleSide,
      roughness,
      metalness: 0,
      depthWrite: true,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.objectId = name;
    // REVIEW surfaces may be incomplete; do not imply solid enclosure via shadows.
    mesh.castShadow = trustworthy;
    mesh.receiveShadow = trustworthy;
    mesh.userData.sourceWitnessedFace = trustworthy;
    return mesh;
  }
  // Unverified height is shown ONLY as source XY linework, never an extruded
  // "default 2.7m" wall or a user-billable surface.
  const lineGeometry = new THREE.BufferGeometry().setFromPoints([
    a.clone().add(new THREE.Vector3(0, 0.015, 0)),
    b.clone().add(new THREE.Vector3(0, 0.015, 0)),
  ]);
  const line = new THREE.Line(
    lineGeometry, new THREE.LineBasicMaterial({ color: 0xefb35d })
  );
  line.userData.objectId = name;
  return line;
}

/** Render exactly the server-backed triangles. No inferred room closures,
 * thicknesses, heights, opening cutouts or default slabs.
 */
function displaySourceSurface(surface: SourceSurface): THREE.Mesh {
  const coordinates = new Float32Array(surface.vertices.flat());
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(coordinates, 3));
  geometry.computeVertexNormals();
  const tint = surface.kind === "floor" ? 0xbbb4a2 :
    surface.kind === "ceiling" ? 0xebedf1 : 0x777f87;
  const material = new THREE.MeshStandardMaterial({
    color: tint, roughness: 0.9, metalness: 0,
    side: THREE.DoubleSide, transparent: false,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.userData.objectId = surface.objectId;
  mesh.userData.surfaceId = surface.surfaceId;
  mesh.userData.surfaceKind = surface.kind;
  mesh.userData.sourceWitnessedSurface = true;
  mesh.castShadow = surface.kind === "roof";
  mesh.receiveShadow = true;
  return mesh;
}

function labelSprite(value: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "rgba(16, 25, 32, 0.93)";
    ctx.fillRect(0, 0, 640, 128);
    ctx.strokeStyle = "#40c4b5";
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, 636, 124);
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 28px sans-serif";
    ctx.fillText(value.slice(0, 36), 22, 74);
  }
  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texture, depthTest: false,
  }));
  sprite.scale.set(2.9, 0.58, 1);
  return sprite;
}

export function SceneView({ manifest, visibleIds, level, levels, onLevel, mode, canUndo, canRedo, onHistory, onDone, onToolMessage, toolFeedback, selectedId, onSelect, draftState, onCycleStudy, mood, onMood, previewLights, onPreviewLights, quality, detail, inspection, cameraRequest, captureSerial, onCapture, onPcVrSessionReport, moveMode, wallMoveState, onMoveDelta, addedWallSketch, addedWallSketches, buildState, buildLevel, buildSizes, stage, onStage, layers, onLayers, allDimensions, onAllDimensions, shell, footprint, onBuildAction, onBuildHint, onBuildSizes, catalogue, teleportMode, teleportAvailable, onTeleportToggle,
  onExportLocalDraft, onReviewLocalWall, onTeleportMessage, budget }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const interaction = useRef({ visibleIds, level, levels, onLevel, mode, canUndo, canRedo, onHistory, onDone, onToolMessage, toolFeedback });
  interaction.current = { visibleIds, level, levels, onLevel, mode, canUndo, canRedo, onHistory, onDone, onToolMessage, toolFeedback };
  const [renderError, setRenderError] = useState<string | null>(null);
  const callback = useRef(onSelect);
  callback.current = onSelect;
  const cycleCallback = useRef(onCycleStudy);
  cycleCallback.current = onCycleStudy;
  const teleportSettings = useRef({teleportMode,teleportAvailable,onTeleportToggle,onTeleportMessage});
  teleportSettings.current = {teleportMode,teleportAvailable,onTeleportToggle,onTeleportMessage};
  const exportDraftCallback=useRef(onExportLocalDraft);
  exportDraftCallback.current=onExportLocalDraft;
  const reviewDraftCallback=useRef(onReviewLocalWall);
  reviewDraftCallback.current=onReviewLocalWall;
  const liveBudget=useRef(budget);
  liveBudget.current=budget;
  const addedWallRef = useRef(addedWallSketch);
  addedWallRef.current = addedWallSketch;
  const addedWallsRef = useRef(addedWallSketches);
  addedWallsRef.current = addedWallSketches;
  const build = useRef({ buildState, buildLevel, buildSizes, onBuildAction, onBuildHint, onBuildSizes });
  build.current = { buildState, buildLevel, buildSizes, onBuildAction, onBuildHint, onBuildSizes };
  const construction = useRef({ stage, onStage, layers, onLayers, allDimensions, onAllDimensions, shell });
  construction.current = { stage, onStage, layers, onLayers, allDimensions, onAllDimensions, shell };
  const resize = useRef(footprint);
  resize.current = footprint;
  const itemControls = useRef(catalogue);
  itemControls.current = catalogue;
  const moveSettings = useRef({ moveMode, wallMoveState, onMoveDelta });
  moveSettings.current = { moveMode, wallMoveState, onMoveDelta };
  const sessionReportCallback = useRef(onPcVrSessionReport);
  sessionReportCallback.current = onPcVrSessionReport;
  const visualSettings = useRef({ mood, onMood, previewLights, onPreviewLights, quality, detail, inspection, cameraRequest, captureSerial, onCapture });
  visualSettings.current = { mood, onMood, previewLights, onPreviewLights, quality, detail, inspection, cameraRequest, captureSerial, onCapture };
  const picked = useRef(selectedId);
  picked.current = selectedId;
  const mappedDrafts=useMemo(()=>new Map<string,WallDraft>((draftState?safeDrafts(draftState,manifest):[])
    .map(d=>[d.objectId,d])),[draftState,manifest]);
  const draftMap=useRef(mappedDrafts);
  draftMap.current=mappedDrafts;

  useEffect(() => {
    const parent = host.current;
    if (!parent) return;

    const scene = new THREE.Scene();
    const wallTextures=createWallTextureLibrary();
    const initialPreset = VISUAL_PRESETS[visualSettings.current.mood];
    scene.background = new THREE.Color(initialPreset.background);
    const ambient = new THREE.HemisphereLight(
      initialPreset.ambientSky, initialPreset.ambientGround, initialPreset.ambientIntensity,
    );
    scene.add(ambient);
    const sunlight = new THREE.DirectionalLight(initialPreset.sunColor, initialPreset.sunIntensity);
    sunlight.position.set(...initialPreset.sunPosition);
    const lightCenter = new THREE.Vector3();
    sunlight.castShadow = true;
    sunlight.shadow.mapSize.set(shadowMapSize(visualSettings.current.quality),
      shadowMapSize(visualSettings.current.quality));
    sunlight.shadow.bias = -0.0001;
    sunlight.shadow.normalBias = 0.03;
    sunlight.shadow.radius = 2;
    scene.add(sunlight);
    const grid = new THREE.GridHelper(50, 50, 0x72919f, 0x91a9b0);
    grid.position.y = 0.005;
    scene.add(grid);

    const camera = new THREE.PerspectiveCamera(65, 1, 0.01, 2500);
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      setRenderError("WebGL is unavailable. The source evidence inspector remains usable without 3D.");
      return;
    }
    setRenderError(null);
    renderer.domElement.tabIndex = 0;
    renderer.domElement.setAttribute(
      "aria-label", "Building scene. Use Escape to finish the current tool."
    );
    renderer.domElement.setAttribute("aria-describedby", "editor-instructions");
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1,
      maxRenderPixelRatio(visualSettings.current.quality, false)));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = initialPreset.exposure;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.xr.enabled = true;
    renderer.xr.setReferenceSpaceType("local-floor");
    renderer.xr.setFramebufferScaleFactor(0.8);
    parent.append(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.minDistance = 0.15;
    controls.maxDistance = 2000;

    // Shared, deterministic micro-roughness texture: strictly illustrative,
    // unrelated to source finish schedules, plaster specification or rates.
    const roughTile = new THREE.DataTexture(
      createPresentationRoughnessTile(), 64, 64, THREE.RGBAFormat,
    );
    roughTile.wrapS = THREE.RepeatWrapping;
    roughTile.wrapT = THREE.RepeatWrapping;
    roughTile.colorSpace = THREE.NoColorSpace;
    roughTile.needsUpdate = true;

    const itemView = createCatalogueScene(scene);
    const sourceItemHosts = itemControls.current.demo ? demoCatalogueHosts(scene) : [];
    sourceItemHosts.push(draftSiteHost(scene));
    let renderHosts = sourceItemHosts;
    const gizmo = createFootprintGizmo(scene);
    let draftItemHosts: CatalogueHost[] = [];
    let itemBrowser = EMPTY_ITEM_BROWSER;
    let stageMenuOpen = false;
    // All headset UX state is local to this viewer and resets on scene change.
    // The authenticated original scene and signed quantities never change.
    let selectedDraftId: string | null = null;
    let hoveredDraftId: string | null = null;
    let magnetic=true, multiSelect=false;
    let wallLock:WallAim|null=null;let hoveredSourceId:string|null=null;
    const selectedGroup=new Set<string>();
    function groupIds(){return build.current.buildState.walls.filter(w=>w.levelId===build.current.buildLevel&&selectedGroup.has(w.proposalId)).map(w=>w.proposalId);}
    let deleteArmed = false;
    let snapGrid: 0.05 | 0.1 | 0.25 = 0.05;
    let snapAxis: WallAxis = "auto";
    let nudgeStep: 0.05 | 0.1 | 0.25 = 0.05;
    let panelPinned = true;
    let helpOpen = false;
    let toolsOpen=false,wallProfilesOpen=false,dimensions=true,radial=true,layersOpen=false;
    let lastMenuSignature="",lastMenuDraw=0,menuPose:"radial"|"panel"|null=null,lastMenuHover=-2;
    // Only a layout actually displayed can authorize a menu action.
    let displayedMenuLayout: ReturnType<typeof menuLayout> | null = null;
    let stickNeedsNeutral=false;
    const closeTools=()=>{toolsOpen=false;displayedMenuLayout=null;menuPose=null;stickNeedsNeutral=true;radial=true;layersOpen=false;wallProfilesOpen=false;helpOpen=false;budgetOpen=false;stageMenuOpen=false;angleTools=false;openingTools=false;numberPad=null;deleteArmed=false;itemBrowser=EMPTY_ITEM_BROWSER;buildOverlay.hideMenu();};
    function toggleTools(){
      if(!renderer.xr.isPresenting)return;
      toolsOpen=!toolsOpen;
      if(toolsOpen){
        for(let i=0;i<xrPress.length;i++)if(xrPress[i]||xrGestures[i]||xrResize[i]){menuConsumed[i]=true;selectEnd(i);}
        activeGrip=null;radial=true;displayedMenuLayout=null;menuPose=null;lastMenuDraw=0;lastMenuHover=-2;
      }
      else closeTools();
    }
    let budgetOpen=false,budgetPage=0;
    let compactMenu = true;
    let overviewOpen=false;
    let elevatedReturn: NavOffset|null=null;
    let navBase:XRReferenceSpace|null=null,navOffset=identityNavOffset();
    function setNavOffset(offset:NavOffset){
      navBase??=renderer.xr.getReferenceSpace();
      if(!navBase)throw Error("No XR reference space");
      renderer.xr.setReferenceSpace(navBase.getOffsetReferenceSpace(new XRRigidTransform(offset.position,offset.orientation)));
      navOffset=offset;
    }
    function moveNavOffset(offset:NavOffset){setNavOffset(composeNavigationOffset(navOffset,offset));}
    let walkSpeed=1.2, turnArmed=true, lastNavTime=0;
    let ghostMode=false,openDoors=new Set<string>();
    const displaySurface=(stage:ConstructionStage,kind?:"floor"|"ceiling"|"roof")=>
      surfaceLayerVisible(stage,kind,construction.current.layers,!!elevatedReturn);
    let openingTools = false;
    let openingIndex = 0;
    let numberPad: {field:NumericDraftField;digits:string}|null = null;
    let rotationPivot:WallRotationPivot="start";
    let connectedRotation=true,angleTools=false;
    const nextStep = (value: 0.05 | 0.1 | 0.25): 0.05 | 0.1 | 0.25 =>
      value === 0.05 ? 0.1 : value === 0.1 ? 0.25 : 0.05;
    function selectedDraftWall() {
      return build.current.buildState.walls.find(wall =>
        wall.proposalId === selectedDraftId && wall.levelId === build.current.buildLevel) ?? null;
    }
    const toolsBusy = () => interaction.current.mode !== "inspect" || itemBrowser.open || stageMenuOpen || budgetOpen;
    const sourceVisible = (object: THREE.Object3D) => {
      const id = object.userData.objectId as string | undefined;
      return !id || interaction.current.visibleIds.has(id);
    };
    function pointerContext() {
      return [interaction.current.mode, build.current.buildState.tool, build.current.buildLevel,
        itemControls.current.active?.id, construction.current.stage, interaction.current.visibleIds,construction.current.layers,build.current.buildState.walls,resize.current.projection] as const;
    }
    type PointerContext = ReturnType<typeof pointerContext>;
    const samePointerContext = (expected: PointerContext) =>
      pointerContext().every((value, index) => value === expected[index]);
    const reportTool = (message: string) => interaction.current.onToolMessage(message);
    let anchorKey: readonly unknown[] = [];
    let cachedAnchors: ReturnType<typeof verifiedSourceWallAnchors> = [];
    let segmentTargets: readonly WallTarget[] | null = null;
    let cachedSegments: {start:WallTarget["start"];end:WallTarget["end"];objectId:string}[] = [];
    function snapOptions() {
      const targets = resize.current.projection ? null : visibleWallTargets();
      if (targets !== segmentTargets) {
        segmentTargets=targets;
        cachedSegments=targets?.filter(t=>t.kind==="source").map(t=>({start:t.start,end:t.end,objectId:t.id})) ?? [];
      }
      const key = [build.current.buildLevel, interaction.current.visibleIds, resize.current.projection];
      if (!key.every((v,i)=>v===anchorKey[i])) {
        anchorKey=key;
        cachedAnchors=resize.current.projection ? [] : verifiedSourceWallAnchors(manifest,build.current.buildLevel,interaction.current.visibleIds);
      }
      return {gridM:snapGrid,axis:snapAxis,magnetic,preferredDraftId:wallLock?.target.kind==="draft"?wallLock.target.id:null,
        wallSegments:cachedSegments,
        verifiedAnchors: cachedAnchors};
    }
    function menuLayout(hint: string) {
      const { buildState, buildLevel } = build.current;
      const { active, canUndo, turn } = itemControls.current;
      const layout=buildMenuLayout(buildState, buildLevel, itemBrowser, active, canUndo, turn, hint,
        construction.current.stage, stageMenuOpen, {
          available: !!resize.current.box, enabled: resize.current.enabled, changed: !!resize.current.projection,
        }, interaction.current, {
          selectedWall: selectedDraftWall(), rotationPivot, connectedRotation, angleTools, feedback:interaction.current.toolFeedback, gridM: snapGrid, axis: snapAxis,
          nudgeM: nudgeStep, pinned: panelPinned, help: helpOpen, deleteArmed,
          compact: compactMenu, openingTools, openingIndex, numeric: numberPad,
          canTeleport:teleportSettings.current.teleportAvailable,
          teleport:teleportSettings.current.teleportMode,overview:overviewOpen,
          elevatedView:!!elevatedReturn,walkSpeed,ghost:ghostMode,night:visualSettings.current.mood==="night",previewLights:visualSettings.current.previewLights,magnetic,multiSelect,selectedCount:groupIds().length,
          budget:liveBudget.current.summary,budgetOpen,budgetPage,
          wallProfilesOpen,nextWallAssembly:build.current.buildSizes.wallAssembly,dimensions,allDimensions:construction.current.allDimensions,
          radial,layersOpen,layers:construction.current.layers,
        });
      if(!layout.radial&&!angleTools&&!budgetOpen && !numberPad && !helpOpen && liveBudget.current.summary.status!=="disabled")layout.title+=" · "+budgetHeadline(liveBudget.current.summary);
      return layout;
    }
    function menuAction(choice: MenuAction) {
      reportTool("");
      if(choice.area==="layer"){construction.current.onLayers(cycleLayer(construction.current.layers,choice.layer));return;}
      if(choice.area==="wall-profile"){
        if(resize.current.enabled||resize.current.projection)return;
        const assembly=defaultWallAssembly(choice.profile),wall=selectedDraftWall();
        if(wall)build.current.onBuildAction({kind:"set-wall-assembly",proposalId:wall.proposalId,assembly});
        else build.current.onBuildSizes({...build.current.buildSizes,wallAssembly:assembly});
        wallProfilesOpen=false;return;
      }
      if(choice.area==="wall-angle"){
        if(resize.current.enabled||resize.current.projection||multiSelect)return;
        const wall=selectedDraftWall();if(!wall)return;
        if(choice.action==="panel"){angleTools=!angleTools;radial=!angleTools;openingTools=false;numberPad=null;deleteArmed=false;return;}
        if(choice.action==="connected"){connectedRotation=!connectedRotation;return;}
        if(choice.action==="pivot"){rotationPivot=rotationPivot==="start"?"centre":rotationPivot==="centre"?"end":"start";return;}
        if(choice.degrees!==undefined){
          build.current.onBuildAction({kind:"rotate-local-wall",previous:wall,angleDeg:choice.degrees,relative:true,pivot:rotationPivot,connected:connectedRotation});
          // App reports the validated result, not an optimistic success message.
        }
        return;
      }
      if (choice.area === "number") {
        if(resize.current.enabled || resize.current.projection) {
          numberPad=null;openingTools=false;return;
        }
        const wall=selectedDraftWall();
        if (choice.action === "start") {
          if (wall && choice.field && (!choice.field.startsWith("opening-") ||
            wall.openings[openingIndex%wall.openings.length])) {
            numberPad={field:choice.field,digits:""};
          }
        } else if (choice.action === "cancel") numberPad=null;
        else if (numberPad) {
          if (choice.action === "clear") numberPad={...numberPad,digits:""};
          else if (choice.action === "erase") numberPad={...numberPad,digits:numberPad.digits.slice(0,-1)};
          else if (choice.action === "digit") {
            const digit=choice.digit??"";
            const text=numberPad.digits;
            const negative=numberPad.field==="x"||numberPad.field==="z";
            if ((/^[0-9]$/.test(digit) && text.length<8) ||
               (digit==="-"&&negative&&!text)) numberPad={...numberPad,digits:text+digit};
          } else if (choice.action === "apply") {
            const number=Number(numberPad.digits), field=numberPad.field;
            if (wall && /^-?[0-9]+$/.test(numberPad.digits) && Number.isSafeInteger(number)) {
              if(field==="angle"){
                if(number<0||number>360){reportTool("Enter an angle from 0 to 360 degrees.");return;}
                build.current.onBuildAction({kind:"rotate-local-wall",previous:wall,angleDeg:number,pivot:rotationPivot,connected:connectedRotation});
              } else if (field.startsWith("opening-")) {
                const opening=wall.openings[openingIndex%wall.openings.length];
                if (opening) build.current.onBuildAction({kind:"exact-local-opening",
                  proposalId:wall.proposalId,openingId:opening.openingId,
                  field:field.slice(8) as "offset"|"width"|"height"|"sill",valueMm:number});
              } else build.current.onBuildAction({kind:"exact-local-wall",
                proposalId:wall.proposalId,field:field as "length"|"height"|"x"|"z",valueMm:number});
              if(field!=="angle")reportTool("Applied exact draft mm request. Invalid or conflicting geometry is rejected.");
              numberPad=null;
            } else reportTool(field==="angle"?"Enter a whole degree value.":"Enter a whole millimetre value to apply.");
          }
        }
      } else if (choice.area === "opening") {
        if(resize.current.enabled || resize.current.projection) {
          openingTools=false;return;
        }
        if(choice.action==="drag") {
          const wall=selectedDraftWall();
          const opening=wall?.openings[openingIndex%(wall.openings.length||1)];
          if(!opening)return;
          selectedDraftId=null;openingTools=false;numberPad=null;deleteArmed=false;
          build.current.onBuildAction({kind:"tool",tool:"opening-move"});
          reportTool("Aim at the door/window, hold trigger and slide along its draft wall.");
          return;
        }
        const wall=selectedDraftWall();
        const opening=wall?.openings[openingIndex%(wall.openings.length||1)];
        if (wall && opening) {
          const field=choice.action==="shift"?"offset":choice.action;
          const value=opening[choice.action==="shift"?"offsetM":
            choice.action==="width"?"widthM":"heightM"]*1000+choice.deltaMm;
          build.current.onBuildAction({kind:"exact-local-opening",
            proposalId:wall.proposalId,openingId:opening.openingId,
            field,valueMm:Math.round(value)});
          reportTool("Opening draft adjustment requested; collisions and invalid sizes are rejected.");
        }
      } else if (choice.area === "quest") {
        if(choice.action==="hide-tools"){closeTools();return;}
        if(choice.action==="more-tools"){radial=false;compactMenu=true;return;}
        if(choice.action==="layers"){layersOpen=!layersOpen;return;}
        if(choice.action==="reset-layers"){construction.current.onLayers({});return;}
        if(choice.action==="wall-profiles"){wallProfilesOpen=!wallProfilesOpen;return;}
        if(choice.action==="dimensions"){dimensions=!dimensions;return;}
        if(choice.action==="all-dimensions"){construction.current.onAllDimensions(!construction.current.allDimensions);return;}
        if(choice.action==="budget"){budgetOpen=!budgetOpen;budgetPage=0;return;}
        if(choice.action==="budget-baseline"){liveBudget.current.onCapture();return;}
        if(choice.action==="budget-clear"){liveBudget.current.onClear();return;}
        if(choice.action==="budget-page"){budgetPage=(budgetPage+1)%Math.max(1,Math.ceil(liveBudget.current.summary.trades.length/4));return;}
        if(choice.action==="magnetic"){magnetic=!magnetic;hoveredDraftId=null;hoveredSourceId=null;wallLock=null;return;}
        if(choice.action==="multi-select"){
          if(resize.current.enabled||resize.current.projection)return;
          multiSelect=!multiSelect;selectedGroup.clear();
          if(multiSelect&&selectedDraftId)selectedGroup.add(selectedDraftId);
          selectedDraftId=null;openingTools=false;numberPad=null;deleteArmed=false;
          if(multiSelect){build.current.onBuildAction({kind:"done"});select(null);}
          return;
        }
        if(choice.action==="clear-group"){selectedGroup.clear();deleteArmed=false;return;}
        if (choice.action === "grid") snapGrid = nextStep(snapGrid);
        if (choice.action === "nudge-size") nudgeStep = nextStep(nudgeStep);
        if (choice.action === "axis") {
          const axes: WallAxis[] = ["auto","free","horizontal","vertical"];
          snapAxis = axes[(axes.indexOf(snapAxis)+1)%axes.length];
        }
        if (choice.action === "compact") compactMenu=!compactMenu;
        if (choice.action === "overview") overviewOpen=!overviewOpen;
        if(choice.action==="ghost"){ghostMode=!ghostMode;closeTools();reportTool(ghostMode?"Ghost mode: walk through walls.":"Solid wall collision restored.");return;}
        if(choice.action==="lighting-night"){visualSettings.current.onMood(visualSettings.current.mood==="night"?"daylight":"night");closeTools();return;}
        if(choice.action==="lighting-on"){visualSettings.current.onPreviewLights(!visualSettings.current.previewLights);closeTools();return;}
        if (choice.action === "walk-speed") walkSpeed=walkSpeed===.6?1.2:walkSpeed===1.2?2:.6;
        if (choice.action === "elevated-view") {toggleElevatedView();closeTools();}
        if (choice.action === "teleport") {
          if(teleportSettings.current.teleportAvailable)
            teleportSettings.current.onTeleportToggle(!teleportSettings.current.teleportMode);
          else reportTool("Teleport requires a verified source-backed floor.");
        }
        if (choice.action === "save") exportDraftCallback.current();
        if (choice.action === "review") {
          const wall=selectedDraftWall();
          if(!wall)return;
          selectedDraftId=null;openingTools=false;numberPad=null;
          const session=renderer.xr.getSession();
          if(session) {
            void session.end().then(()=>reviewDraftCallback.current(wall.proposalId))
              .catch(()=>reportTool("Exit VR before starting authenticated assembly review."));
          } else reviewDraftCallback.current(wall.proposalId);
        }
        if (choice.action === "next-stage") {
          const current=CONSTRUCTION_STAGES.findIndex(entry=>entry.id===construction.current.stage);
          construction.current.onStage(CONSTRUCTION_STAGES[(current+1)%CONSTRUCTION_STAGES.length].id);
        }
        if (choice.action === "next-floor") {
          const levels=["all",...interaction.current.levels];
          const index=levels.indexOf(interaction.current.level);
          interaction.current.onLevel(levels[(index+1)%levels.length]);
          selectedDraftId=null;selectedGroup.clear();multiSelect=false;openingTools=false;numberPad=null;
        }
        if (choice.action === "openings") {
          openingTools=!openingTools;angleTools=false;openingIndex=0;numberPad=null;radial=!openingTools;
        }
        if (choice.action === "next-opening") {
          const count=selectedDraftWall()?.openings.length??0;
          if(count) openingIndex=(openingIndex+1)%count;
        }
        if (choice.action === "pin") panelPinned = !panelPinned;
        if (choice.action === "recenter" && renderer.xr.isPresenting)
          buildOverlay.positionMenu(renderer.xr.getCamera(),panelPinned,true);
        if (choice.action === "help") { helpOpen = !helpOpen; numberPad=null; openingTools=false;
          selectedDraftId = null; deleteArmed=false; }
        if (choice.action === "back") { selectedDraftId=null; deleteArmed=false; openingTools=false; numberPad=null; angleTools=false;radial=true; }
        reportTool(choice.action === "grid" ? "Draft grid: " + Math.round(snapGrid*1000) + " mm." :
          choice.action === "axis" ? "Wall alignment: " + snapAxis + "." : "");
      } else if (choice.area === "draft") {
        if (resize.current.enabled || resize.current.projection) {
          selectedDraftId=null; deleteArmed=false;
          reportTool("Finish or reset footprint resizing before editing draft walls.");
          return;
        }
        if(multiSelect){
          const proposalIds=groupIds();
          if(!proposalIds.length)return;
          if(choice.action==="delete"&&!deleteArmed){deleteArmed=true;reportTool("Confirm delete group. Undo restores all walls.");return;}
          deleteArmed=false;
          const facing=renderer.xr.getCamera().getWorldDirection(new THREE.Vector3());
          const delta=choice.direction?viewRelativeNudge(choice.direction,[facing.x,facing.z],nudgeStep):null;
          if(choice.action==="nudge"&&delta)build.current.onBuildAction({kind:"group-local-walls",proposalIds,operation:"translate",delta});
          else if(choice.action==="rotate")build.current.onBuildAction({kind:"group-local-walls",proposalIds,operation:"rotate"});
          else if(choice.action==="duplicate")build.current.onBuildAction({kind:"group-local-walls",proposalIds,operation:"duplicate",copyIds:proposalIds.map(()=>newPlacementId("wall-copy"))});
          else if(choice.action==="delete"){build.current.onBuildAction({kind:"group-local-walls",proposalIds,operation:"delete"});selectedGroup.clear();}
          return;
        }
        const wall = selectedDraftWall();
        if (!wall) { selectedDraftId=null; deleteArmed=false; return; }
        if (choice.action === "move" || choice.action === "stretch") {
          // Selecting a draft wall opens the edit tray; picking Grab or Stretch
          // switches straight into the existing verified trigger-drag workflow.
          // This never targets a signed/source wall.
          const tool = choice.action;
          selectedDraftId=null;
          deleteArmed=false;
          build.current.onBuildAction({kind:"tool",tool});
          reportTool(tool === "move" ?
            "Hold trigger on the purple wall and move your hand; release to apply." :
            "Aim at a draft wall endpoint, hold trigger and stretch; release to apply.");
          return;
        }
        if (choice.action === "delete") {
          if (!deleteArmed) { deleteArmed=true; reportTool("Pull Confirm delete to remove this local draft wall."); }
          else {
            build.current.onBuildAction({kind:"delete-local-wall",proposalId:wall.proposalId});
            selectedDraftId=null; deleteArmed=false;
            reportTool("Draft wall deleted. Undo restores it.");
          }
          return;
        }
        deleteArmed=false;
        if (choice.action === "duplicate") {
          const id = newPlacementId("wall-copy");
          build.current.onBuildAction({kind:"duplicate-local-wall",proposalId:wall.proposalId,id});
          selectedDraftId=id;
          reportTool("Draft wall duplicated 500 mm to the side. Undo restores.");
          return;
        }
        const facing = renderer.xr.getCamera().getWorldDirection(new THREE.Vector3());
        const vector = choice.direction ?
          viewRelativeNudge(choice.direction,[facing.x,facing.z],nudgeStep) : null;
        const edited = choice.action === "rotate" ? rotatedDraftWall(wall) :
          vector ? translatedDraftWall(wall,vector[0],vector[1]) : null;
        if (edited) {
          build.current.onBuildAction({kind:"adjust",previous:wall,wall:edited});
          reportTool(choice.action === "rotate" ? "Rotated draft wall 90°." :
            "Moved draft wall " + Math.round(nudgeStep*1000) + " mm.");
        } else reportTool("Cannot move or rotate this wall beyond valid draft limits.");
      } else if (choice.area === "history") interaction.current.onHistory(choice.action);
      else if (choice.area === "done") interaction.current.onDone();
      else if (choice.area === "level") interaction.current.onLevel(choice.id);
      else if (choice.area === "footprint") {
        if (choice.reset) resize.current.onReset();
        else resize.current.onToggle();
      } else if (choice.area === "view") {
        if (choice.stage) {
          construction.current.onStage(choice.stage);
          stageMenuOpen = false;
        } else stageMenuOpen = !stageMenuOpen;
      } else if (choice.area === "browse") itemBrowser = updateItemBrowser(itemBrowser, choice.action);
      else if (choice.area === "build") build.current.onBuildAction(choice.action);
      else {
        if (choice.action.kind === "choose") itemBrowser = { ...itemBrowser, open: false };
        itemControls.current.onAction(choice.action);
      }
    }
    const physical = new THREE.Group();
    scene.add(physical);
    const pickables: THREE.Object3D[] = [];
    const verifiedFloorMeshes: THREE.Object3D[] = [];
    const sourceById = new Map(manifest.objects.map(row => [row.objectId, row]));
    for (const row of manifest.objects) {
      const item = displayObject(row, initialPreset.materialRoughness);
      if (!item) continue;
      physical.add(item);
      pickables.push(item);
      // Keep the original review material as the fallback after any study clears.
      if (item instanceof THREE.Mesh && item.material instanceof THREE.MeshStandardMaterial) {
        item.userData.originalReviewColor = item.material.color.getHex();
        item.material.roughnessMap = item.userData.sourceWitnessedFace &&
          visualSettings.current.detail === "subtle" ? roughTile : null;
        item.userData.originalOpacity = item.material.opacity;
        const geometry = row.geometry;
        if (geometry?.kind === "wallFace") {
          item.userData.originalHeight = geometry.heightM;
          // Recorded opening outlines are review-only, not a verified wall cutout.
          const preview=new THREE.Group();preview.userData.openingReview=true;
          for(const o of row.openingReview?.positioned??[]){
            const points=reviewOpeningCorners(geometry,o).map(p=>new THREE.Vector3(...p));
            const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineDashedMaterial({color:0x58d9ef,dashSize:.08,gapSize:.04,depthWrite:false}));
            line.computeLineDistances();preview.add(line);
          }
          if(preview.children.length)item.add(preview);
          if (row.objectType === "wall") sourceItemHosts.push(catalogueWallHost(
            row.objectId, item, geometry.start, geometry.end, geometry.heightM,
          ));
        }
      }
    }
    // Optional verified room/ceiling/roof triangles are genuine existing
    // source-derived surface evidence, not the synthetic shadow ground plane.
    const edgesByRoof = roofEdges(manifest.sourceSurfaces ?? []);
    for (const surface of manifest.sourceSurfaces ?? []) {
      if (!sourceById.has(surface.objectId)) continue;
      const mesh = displaySourceSurface(surface);
      if(surface.kind==="floor")verifiedFloorMeshes.push(mesh);
      sourceItemHosts.push({ id: makeItemHostId(surface.kind, surface.surfaceId), target: surface.kind, mesh,
        roofEdges: edgesByRoof.get(surface.surfaceId) });
      physical.add(mesh);
      pickables.push(mesh);
      mesh.userData.originalReviewColor =
        (mesh.material as THREE.MeshStandardMaterial).color.getHex();
      mesh.userData.originalOpacity = 1;
    }
    const sourceGeometry = footprintGeometry([...new Set([
      ...pickables, ...sourceItemHosts.filter(host => host.target !== "site").map(host => host.mesh),
    ])]);
    let appliedProjection: FootprintProjection | null = null;
    function updateSourceLayout() {
      const next = resize.current.projection;
      if (next === appliedProjection) return;
      appliedProjection = next;
      itemView.clear();
      renderFootprintGeometry(sourceGeometry, next);
      renderHosts = next ? sourceItemHosts.map(host => projectSourceHost(host, next)) : sourceItemHosts;
    }
    // Source-independent wall proposals stay in a clearly tinted review layer.
    // Never insert them into pickables, original source witness, or quantity DTO.
    const wallAdditionLayer = new THREE.Group();
    wallAdditionLayer.name = "UnapprovedNewWallStudy";
    scene.add(wallAdditionLayer);
    const shellGroup=new THREE.Group();shellGroup.name="LocalDraftConnectedShell";scene.add(shellGroup);
    let currentShell:DraftShell|null=null;
    function refreshShell(){
      const next=construction.current.shell;
      if(next!==currentShell){
        currentShell=next;
        for(const child of [...shellGroup.children]){shellGroup.remove(child);if(child instanceof THREE.Mesh){child.geometry.dispose();child.material.dispose();}}
        for(const surface of next?.surfaces??[]){
          const geometry=new THREE.BufferGeometry();geometry.setAttribute("position",new THREE.Float32BufferAttribute(surface.vertices.flat(),3));geometry.computeVertexNormals();
          const material=new THREE.MeshStandardMaterial({color:surface.kind==="floor"?0xb4b1a8:surface.kind==="roof"?0x687783:0xf4f0e6,roughness:.85,side:THREE.DoubleSide});
          const mesh=new THREE.Mesh(geometry,material);mesh.userData.surfaceKind=surface.kind;shellGroup.add(mesh);
        }
      }
      for(const mesh of shellGroup.children)mesh.visible=displaySurface(construction.current.stage,mesh.userData.surfaceKind);
    }
    const buildOverlay = createBuildOverlay(scene);
    const planOverview=createVrPlanOverview(scene,manifest);
    const sceneScope = scopeKey(manifest);
    let lastAddedWall = "";
    let draftMeshes = new Map<string,{signature:string;object:THREE.Object3D}>();
    let lastBuildWalls = build.current.buildState.walls;
    let lastBuildCeilings = build.current.buildState.ceilings;
    let lastBuildLevel = build.current.buildLevel;
    let lastDraftProjection: FootprintProjection | null = null;
    let lastReviewSketch: WallVisual | null | undefined;
    let lastReviewWalls: WallVisual[] | undefined;
    function refreshWallAddition() {
      const { buildState, buildLevel } = build.current;
      if (lastBuildWalls === buildState.walls && lastBuildCeilings === buildState.ceilings &&
          lastBuildLevel === buildLevel && lastDraftProjection === appliedProjection &&
          lastReviewSketch === addedWallRef.current && lastReviewWalls === addedWallsRef.current) return;
      lastDraftProjection = appliedProjection;
      lastBuildWalls = buildState.walls;
      lastBuildCeilings = buildState.ceilings;
      lastBuildLevel = buildLevel;
      lastReviewSketch = addedWallRef.current;
      lastReviewWalls = addedWallsRef.current;
      const requested = [...lastReviewWalls, ...buildState.walls.filter(
        wall => !buildLevel || wall.levelId === buildLevel,
      )];
      if (lastReviewSketch) requested.push(lastReviewSketch);
      const byId = new Map<string, WallVisual>();
      for (const wall of requested) {
        const length = Math.hypot(wall.start[0] - wall.end[0], wall.start[1] - wall.end[1]);
        if (wall.scopeKey !== sceneScope || !validWallLength(length) ||
          !Number.isFinite(wall.heightM) || wall.heightM <= 0 || wall.heightM > 20) continue;
        byId.set(wall.proposalId, wall);
      }
      const active = [...byId.values()].map(wall => appliedProjection ? projectWall(wall, appliedProjection) : wall);
      const ceilings = buildState.ceilings.filter(ceiling => !buildLevel || ceiling.levelId === buildLevel)
        .map(ceiling => appliedProjection ? projectCeiling(ceiling, appliedProjection) : ceiling);
      const signature = JSON.stringify([active, ceilings]);
      if (lastAddedWall === signature) return;
      lastAddedWall = signature;
      itemView.clear();
      draftItemHosts = [];
      const nextMeshes=new Map<string,{signature:string;object:THREE.Object3D}>();
      const nextOpenDoors=new Set<string>();
      for (const wall of active) {
        const key="wall:"+wall.proposalId,signature=JSON.stringify(wall);
        const previous=draftMeshes.get(key);
        const reused=previous?.signature===signature;
        const group=reused && previous.object instanceof THREE.Group ? previous.object : displayWallDraft(wall,wallTextures);
        if(!reused){
          group.userData.reviewOnlyWallProposal = true;
          group.userData.proposalId = wall.proposalId;
          group.userData.wallDimensions=wallDimensionText(Math.hypot(wall.end[0]-wall.start[0],wall.end[1]-wall.start[1]),wall.heightM,wall.assembly);
          group.userData.wallProfile=profileDetails(wall.assembly).label;
          group.userData.masonryAssembly=profileDetails(wall.assembly).core==="masonry";
          wallAdditionLayer.add(group);
        }else for(const opening of wall.openings??[]){
          const id=doorKey(wall.proposalId,opening.openingId);
          if(openDoors.has(id))nextOpenDoors.add(id);
        }
        nextMeshes.set(key,{signature,object:group});
        draftItemHosts.push(...draftCatalogueHosts(wall, group));
      }
      for (const ceiling of ceilings) {
        const key="ceiling:"+ceiling.proposalId,signature=JSON.stringify(ceiling);
        const previous=draftMeshes.get(key);
        // Only ceiling entries are meshes; check before narrowing for the host.
        const mesh=previous?.signature===signature && previous.object instanceof THREE.Mesh
          ? previous.object : displayCeilingDraft(ceiling);
        if(mesh!==previous?.object){
          mesh.userData.surfaceKind = "ceiling";
          mesh.userData.ceilingDimensions=`${Math.round(Math.abs(ceiling.end[0]-ceiling.start[0])*1000)} × ${Math.round(Math.abs(ceiling.end[1]-ceiling.start[1])*1000)} mm · H ${Math.round(ceiling.heightM*1000)}`;
          wallAdditionLayer.add(mesh);
        }
        nextMeshes.set(key,{signature,object:mesh});
        draftItemHosts.push({ id: ceilingDraftHostId(ceiling.proposalId), target: "ceiling", mesh, ceilingDraft: ceiling });
      }
      for(const [key,entry] of draftMeshes){
        if(nextMeshes.get(key)?.object===entry.object)continue;
        wallAdditionLayer.remove(entry.object);
        entry.object.traverse(item=>{
          if(item instanceof THREE.Mesh || item instanceof THREE.Line){
            item.geometry.dispose();
            const materials=Array.isArray(item.material)?item.material:[item.material];
            materials.forEach(material=>material.dispose());
          }
        });
      }
      draftMeshes=nextMeshes;
      openDoors=nextOpenDoors;
    }

    // Presentation-only shadow-catching floor; never a sourced slab, floor finish or quantity.
    // It exists solely below existing linework and cannot be selected.
    const presentationFloor = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.ShadowMaterial({ color: 0x293440, opacity: 0.15 }),
    );
    presentationFloor.rotation.x = -Math.PI / 2;
    presentationFloor.position.y = -0.01;
    presentationFloor.receiveShadow = true;
    scene.add(presentationFloor);
    const bbox = new THREE.Box3().setFromObject(physical);
    if (!bbox.isEmpty()) {
      const center = bbox.getCenter(new THREE.Vector3());
      const radius = Math.max(bbox.getSize(new THREE.Vector3()).length(), 4);
      controls.target.copy(center);
      const size = bbox.getSize(new THREE.Vector3());
      const shadowExtent = Math.min(150, Math.max(12, size.x, size.z) * 1.4);
      sunlight.shadow.camera.left = -shadowExtent;
      sunlight.shadow.camera.right = shadowExtent;
      sunlight.shadow.camera.top = shadowExtent;
      sunlight.shadow.camera.bottom = -shadowExtent;
      sunlight.shadow.camera.near = 0.5;
      sunlight.shadow.camera.far = 180;
      sunlight.shadow.camera.updateProjectionMatrix();
      presentationFloor.scale.set(Math.min(300, Math.max(20, size.x * 1.5)),
        Math.min(300, Math.max(20, size.z * 1.5)), 1);
      presentationFloor.position.x = center.x;
      presentationFloor.position.z = center.z;
      lightCenter.copy(center);
      sunlight.target.position.copy(center);
      sunlight.position.add(center);
      scene.add(sunlight.target);
      camera.position.set(center.x + radius, center.y + radius * 0.7,
        center.z + radius);
      camera.near = Math.max(0.01, radius / 5000);
      camera.far = Math.max(300, radius * 50);
      camera.updateProjectionMatrix();
    } else {
      camera.position.set(8, 6, 8);
      controls.target.set(0, 0, 0);
    }
    controls.update();

    const raycaster = new THREE.Raycaster();
    raycaster.params.Line = { threshold: 0.2 };
    const mouse = new THREE.Vector2();
    let hoveringCanvas = false;
    let lastController = -1;
    let lastBuildHint = "";
    function setBuildHint(hint: string) {
      if (lastBuildHint === hint) return;
      lastBuildHint = hint;
      build.current.onBuildHint(hint);
    }
    function aim() {
      const { buildState, buildLevel, buildSizes } = build.current;
      return aimBuild(buildState, buildLevel, buildSizes, raycaster.ray,snapOptions());
    }
    function place(hit: BuildHit) {
      build.current.onBuildAction({ kind: "place", hit, id: newPlacementId(hit.kind) });
    }
    let lastVisible: ReadonlySet<string> | null = null;
    let lastHosts: readonly CatalogueHost[] | null = null;
    let visibleHosts: readonly CatalogueHost[] = [];
    let itemsAtSource: readonly PlacedItem[] | null = null;
    let itemProjection: FootprintProjection | null = null;
    let renderItems: readonly PlacedItem[] = [];
    let syncedVisible:readonly CatalogueHost[]|null=null,syncedDraft:readonly CatalogueHost[]|null=null,syncedItems:readonly PlacedItem[]|null=null,syncedStage:ConstructionStage|null=null;
    let syncedLayers:LayerOverrides|null=null,syncedCutaway=false;
    function syncItems() {
      updateSourceLayout();
      refreshWallAddition();
      const items = itemControls.current.items;
      if (itemsAtSource !== items || itemProjection !== appliedProjection) {
        itemsAtSource = items;
        itemProjection = appliedProjection;
        renderItems = appliedProjection ? items.map(item => projectPlacement(item, appliedProjection!)) : items;
      }
      if (lastVisible !== interaction.current.visibleIds || lastHosts !== renderHosts) {
        lastVisible = interaction.current.visibleIds;
        lastHosts = renderHosts;
        visibleHosts = renderHosts.filter(entry => sourceVisible(entry.mesh));
      }
      const stage=construction.current.stage;
      if(syncedVisible!==visibleHosts||syncedDraft!==draftItemHosts||syncedItems!==renderItems||syncedStage!==stage||syncedLayers!==construction.current.layers||syncedCutaway!==!!elevatedReturn){
        itemView.sync(visibleHosts,draftItemHosts,renderItems,stage,construction.current.layers,!!elevatedReturn);
        syncedVisible=visibleHosts;syncedDraft=draftItemHosts;syncedItems=renderItems;syncedStage=stage;syncedLayers=construction.current.layers;syncedCutaway=!!elevatedReturn;
      }
    }
    function placeSelectedItem(item: CatalogueItem) {
      syncItems();
      const { hit: target, reason } = itemView.candidate(raycaster, item, itemControls.current.turn);
      if (target) itemControls.current.onPlace(item.id, target);
      else reportTool(reason ?? itemGuide(item));
    }
    const select = (id: string | null) => callback.current(id);
    let targetKey:readonly unknown[]=[];let targets:WallTarget[]=[];
    function visibleWallTargets(){
      const {buildState,buildLevel}=build.current;
      const stage=construction.current.stage,layers=construction.current.layers,projection=resize.current.projection;
      const key=[buildState.walls,buildLevel,interaction.current.visibleIds,stage,layers,projection,resize.current.enabled,moveSettings.current.wallMoveState,multiSelect];
      // The source wall list is bounded by the current visible scene; never edit it.
      if(key.every((v,i)=>v===targetKey[i]))return targets;
      targetKey=key;targets=[];
      if(!resize.current.enabled&&!projection){
        for(const w of buildState.walls){
          if(w.scopeKey!==sceneScope||w.levelId!==buildLevel)continue;
          if(!layerVisible(layers,"wall",stage!=="slab"&&(stage!=="framing"&&stage!=="rough-in"||profileDetails(w.assembly).core==="masonry"))&&
            !layerVisible(layers,"framing",stage==="framing"))continue;
          targets.push({key:"draft:"+w.proposalId,kind:"draft",id:w.proposalId,start:w.start,end:w.end,heightM:w.heightM,halfThickness:wallAssembly(w.assembly).thicknessMm/2000});
        }
      }
      if(!multiSelect&&displaySurface(stage,undefined)){
        const moves=new Map((moveSettings.current.wallMoveState?safeWallMoves(moveSettings.current.wallMoveState,manifest):[]).map(m=>[m.objectId,m]));
        for(const row of manifest.objects){
          const g=row.geometry;
          if(row.objectType!=="wall"||g?.kind!=="wallFace"||!interaction.current.visibleIds.has(row.objectId))continue;
          const move=moves.get(row.objectId),dx=(move?.dx??0)*(projection?.scaleX??1),dz=(move?.dz??0)*(projection?.scaleZ??1);
          const a=projection?projectPlan(g.start,projection):g.start,b=projection?projectPlan(g.end,projection):g.end;
          targets.push({key:"source:"+row.objectId,kind:"source",id:row.objectId,start:[a[0]+dx,a[1]+dz],end:[b[0]+dx,b[1]+dz],heightM:g.heightM,halfThickness:0});
        }
      }
      return targets;
    }
    function targetWallAim(previous=wallLock?.target.key??null){
      return chooseWallAim(raycaster.ray,visibleWallTargets().filter(t=>!multiSelect||t.kind==="draft"),previous,magnetic);
    }
    function toggleAimedDoor(){
      if(multiSelect||resize.current.projection||elevatedReturn)return false;
      const leaves:THREE.Mesh[]=[];
      const blockers:THREE.Object3D[]=[];
      for(const group of wallAdditionLayer.children){
        if(!group.visible)continue;
        for(const child of group.children){
          if(child instanceof THREE.Mesh&&child.visible&&child.material instanceof THREE.MeshStandardMaterial&&child.material.visible){
            if(child.userData.catalogueDoorLeaf&&child.userData.doorHinge)leaves.push(child);
            else if(child.userData.catalogueWallFace)blockers.push(child);
          }
        }
      }
      const hit=raycaster.intersectObjects(leaves,false)[0];
      if(!hit||hit.distance>3)return false;
      const blocked=raycaster.intersectObjects([...blockers,...pickables.filter(o=>o instanceof THREE.Mesh&&sourceVisible(o)&&displaySurface(construction.current.stage,o.userData.surfaceKind)&&!o.userData.surfaceKind)],false)[0];
      if(blocked&&blocked.distance<hit.distance-.015)return false;
      const leaf=hit.object as THREE.Mesh;
      const key=doorKey(leaf.parent!.userData.proposalId,leaf.userData.catalogueDoorLeaf);
      const opening=!openDoors.has(key);
      const hinge=leaf.userData.doorHinge as THREE.Vector3;
      const angle=opening?Math.PI/2:0;
      // Rigid rotation around the original hinge while retaining the original mesh coordinates.
      leaf.rotation.y=angle;
      leaf.position.copy(hinge).sub(hinge.clone().applyAxisAngle(new THREE.Vector3(0,1,0),angle));
      leaf.updateMatrixWorld(true);
      const next=new Set(openDoors);
      if(opening)next.add(key);else next.delete(key);
      openDoors=next;
      reportTool(opening?"Door opened.":"Door closed.");
      return true;
    }
    function selectAtRay(pressedKey?:string|null) {
      if(renderer.xr.isPresenting&&magnetic&&!resize.current.enabled){
        const target=pressedKey?visibleWallTargets().find(t=>t.key===pressedKey):null;
        const aimed=pressedKey?(target?wallAimWithin(raycaster.ray,target,MAGNET_RELEASE):null):pressedKey===null?null:targetWallAim();
        if(pressedKey!==undefined&&!aimed){if(pressedKey===null&&!multiSelect){selectedDraftId=null;pick(true);}else reportTool("Wall lock released · aim again.");return;}
        if(aimed){
          wallLock=aimed;
          if(aimed.target.kind==="source"){
            selectedDraftId=null;openingTools=false;numberPad=null;deleteArmed=false;
            select(aimed.target.id);reportTool("Imported wall selected · source geometry is read-only.");return;
          }
          const id=aimed.target.id;
          if(multiSelect){if(selectedGroup.has(id))selectedGroup.delete(id);else selectedGroup.add(id);}
          else selectedDraftId=id;
          openingTools=false;openingIndex=0;numberPad=null;deleteArmed=false;
          select(null);reportTool(multiSelect?groupIds().length+" draft walls selected.":"Magnetic wall locked · open precision tools to edit.");return;
        }
        // No lock: do not cycle onto a different wall behind the aiming ray.
        if(multiSelect)return;
        selectedDraftId=null;openingTools=false;numberPad=null;deleteArmed=false;pick();return;
      }
      const walls = renderer.xr.isPresenting && !resize.current.enabled &&
        !resize.current.projection ?
        magneticDraftWalls(build.current.buildState, build.current.buildLevel, raycaster.ray, hoveredDraftId, magnetic ? 0.15 : 0) : [];
      if(multiSelect){
        const wall=walls[0];
        if(wall&&!itemBrowser.open&&!stageMenuOpen){
          if(selectedGroup.has(wall.proposalId))selectedGroup.delete(wall.proposalId);
          else selectedGroup.add(wall.proposalId);
          deleteArmed=false;select(null);reportTool(groupIds().length+" draft walls selected.");
        }
        return;
      }
      const index=walls.findIndex(wall=>wall.proposalId===selectedDraftId);
      const wall=walls.length?walls[(index+1)%walls.length]:null;
      if (wall && !itemBrowser.open && !stageMenuOpen) {
        selectedDraftId=wall.proposalId;
        openingTools=false;openingIndex=0;numberPad=null;
        deleteArmed=false;
        select(null);
        reportTool("Draft wall selected · use the precision controls to edit.");
        return;
      }
      selectedDraftId=null;openingTools=false;numberPad=null;
      deleteArmed=false;
      pick();
    }
    function pick(excludeWalls=false) {
      const hits=raycaster.intersectObjects(pickables.filter(object =>
        sourceVisible(object) && displaySurface(construction.current.stage, object.userData.surfaceKind)&&(!excludeWalls||sourceById.get(object.userData.objectId)?.objectType!=="wall")), false);
      const candidates=[...new Set(hits.map(hit=>hit.object.userData.objectId)
        .filter((id):id is string=>typeof id==="string"))];
      const current=candidates.indexOf(picked.current??"");
      const next=candidates.length?candidates[(current+1)%candidates.length]:null;
      select(next);
      if(candidates.length>1) reportTool("Overlapping source objects: trigger again to cycle.");
    }
    const resizePlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.06);
    type ResizeDrag = { box: FootprintBounds; corner: FootprintHandle; at: THREE.Vector3; token: symbol; last?: string };
    function startResize() {
      if (!resize.current.enabled || !resize.current.box) return null;
      gizmo.show(resize.current.box);
      const corner = gizmo.pick(raycaster);
      const at = raycaster.ray.intersectPlane(resizePlane, new THREE.Vector3());
      return corner && at ? { box: resize.current.box, corner, at, token: Symbol() } : null;
    }
    function resizeDrag(drag: ResizeDrag) {
      if (!resize.current.enabled) return;
      const at = raycaster.ray.intersectPlane(resizePlane, new THREE.Vector3());
      if (!at) return;
      const [x, z] = footprintHandlePoint(drag.box, drag.corner);
      const next = resizeFromHandle(drag.box, drag.corner, [x + at.x - drag.at.x, z + at.z - drag.at.z]);
      const key = JSON.stringify(next);
      if (drag.last === key) return;
      drag.last = key;
      resize.current.onResize(next, drag.token);
    }
    let startPointer: { id: number; x: number; y: number;
      gesture: DraftGesture | null; resize: ResizeDrag | null; context: PointerContext } | null = null;
    function draftGesture() {
      const { buildState, buildLevel } = build.current;
      if (interaction.current.mode !== "draw" || resize.current.projection) return null;
      return beginDraftGesture(buildState, buildLevel, raycaster.ray,snapOptions());
    }
    function previewDrag(gesture: DraftGesture, controllerIndex?: number) {
      const { buildState, buildLevel, buildSizes } = build.current;
      if (buildState.tool !== gesture.mode || buildLevel !== gesture.levelId) return null;
      const hand = controllerIndex === undefined ? undefined :
        controllers[controllerIndex].getWorldPosition(new THREE.Vector3());
      return draftGesturePreview(gesture, buildSizes, raycaster.ray, buildState,
        hand ? [hand.x, hand.z] : undefined,snapOptions());
    }
    function completeDrag(gesture: DraftGesture, controllerIndex?: number) {
      const preview = previewDrag(gesture, controllerIndex);
      if (!preview) return false;
      const { action } = preview;
      if (action?.kind === "drag") {
        build.current.onBuildAction({ ...action, id: newPlacementId(gesture.mode) });
      } else if (action) build.current.onBuildAction(action);
      else reportTool(preview.aim.hint);
      return true;
    }
    function pointerDown(e: PointerEvent) {
      if (renderer.xr.isPresenting || e.button !== 0 || !e.isPrimary ||
          e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || !trackPointer(e)) return;
      reportTool("");
      raycaster.setFromCamera(mouse, camera);
      const resizing = startResize();
      const gesture = resizing ? null : draftGesture();
      startPointer = { id: e.pointerId, x: e.clientX, y: e.clientY, gesture, resize: resizing, context: pointerContext() };
      if (gesture || resizing) {
        controls.enabled = false;
        renderer.domElement.setPointerCapture(e.pointerId);
      }
    }
    function trackPointer(e: MouseEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      if (!rect.width || !rect.height) return false;
      mouse.set(((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1);
      hoveringCanvas = Math.abs(mouse.x) <= 1 && Math.abs(mouse.y) <= 1;
      return hoveringCanvas;
    }
    function leaveCanvas() { hoveringCanvas = false; }
    function cancelPointer() {
      if (startPointer?.gesture || startPointer?.resize) controls.enabled = true;
      startPointer = null;
      leaveCanvas();
    }
    function pointerUp(e: PointerEvent) {
      const start = startPointer;
      if (!start || start.id !== e.pointerId) return;
      startPointer = null;
      if (start.gesture || start.resize) controls.enabled = true;
      if (renderer.xr.isPresenting || !samePointerContext(start.context) || !trackPointer(e)) return;
      raycaster.setFromCamera(mouse, camera);
      if (start.resize) {
        resizeDrag(start.resize);
        return;
      }
      if (Math.hypot(e.clientX - start.x, e.clientY - start.y) > 6) {
        if (start.gesture) completeDrag(start.gesture);
        return;
      }
      const active = itemControls.current.active;
      if (active) {
        placeSelectedItem(active);
        return;
      }
      if (build.current.buildState.tool) {
        const target = aim();
        if (target.hit) place(target.hit);
        else reportTool(target.hint);
        return;
      }
      if (!resize.current.enabled) selectAtRay();
    }
    function dragOver(event: DragEvent) {
      if (event.dataTransfer?.types.some(type => type === CATALOGUE_DRAG_TYPE || type === OPENING_DRAG_TYPE) &&
          trackPointer(event)) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
      }
    }
    function dropItem(event: DragEvent) {
      if (!trackPointer(event) || resize.current.enabled) return;
      reportTool("");
      const opening = event.dataTransfer?.getData(OPENING_DRAG_TYPE);
      raycaster.setFromCamera(mouse, camera);
      if (opening === "door" || opening === "frame" || opening === "window") {
        if (build.current.buildState.tool !== opening) return;
        event.preventDefault();
        const target = aim();
        if (target.hit?.kind === "opening") place(target.hit);
        else reportTool(target.hint);
        return;
      }
      const item = getCatalogueItem(event.dataTransfer?.getData(CATALOGUE_DRAG_TYPE) ?? null);
      if (!item || itemControls.current.active?.id !== item.id ||
          !itemLayerVisible(construction.current.stage,item,construction.current.layers)) return;
      event.preventDefault();
      placeSelectedItem(item);
    }
    renderer.domElement.addEventListener("dragover", dragOver);
    renderer.domElement.addEventListener("drop", dropItem);
    renderer.domElement.addEventListener("pointerdown", pointerDown, true);
    renderer.domElement.addEventListener("pointerup", pointerUp);
    renderer.domElement.addEventListener("pointermove", trackPointer);
    renderer.domElement.addEventListener("pointerleave", leaveCanvas);
    renderer.domElement.addEventListener("pointercancel", cancelPointer);
    renderer.domElement.addEventListener("lostpointercapture", cancelPointer);
    window.addEventListener("blur", cancelPointer);

    // Controller selection uses exactly the same pickables and canonical
    // object IDs as desktop. No headset state changes any building geometry.
    const tempMatrix = new THREE.Matrix4();
    const controllers = [renderer.xr.getController(0), renderer.xr.getController(1)];
    const grips=[renderer.xr.getControllerGrip(0),renderer.xr.getControllerGrip(1)];
    grips.forEach(grip=>scene.add(grip));
    function aimController(controller: THREE.Group) {
      controller.updateWorldMatrix(true, false);
      tempMatrix.identity().extractRotation(controller.matrixWorld);
      raycaster.ray.origin.setFromMatrixPosition(controller.matrixWorld);
      raycaster.ray.direction.set(0, 0, -1).applyMatrix4(tempMatrix);
    }
    // This marker is never a source object: only a validated raycast hit
    // from the authenticated existing floor may authorise teleportation.
    const teleportMarker = new THREE.Mesh(
      new THREE.RingGeometry(.18,.24,32),
      new THREE.MeshBasicMaterial({color:0x4ee0b8,side:THREE.DoubleSide,
        depthWrite:false,transparent:true,opacity:.9}),
    );
    teleportMarker.rotation.x=-Math.PI/2;
    teleportMarker.visible=false;
    scene.add(teleportMarker);

    function candidateTeleport(index:number) {
      aimController(controllers[index]);
      const hit=raycaster.intersectObjects(verifiedFloorMeshes.filter(sourceVisible), false)[0];
      if (!hit) return {accepted:false as const,reason:"no_verified_source_floor" as const};
      const id=hit.object.userData.surfaceId as string|undefined;
      if (!id) return {accepted:false as const,reason:"no_verified_source_floor" as const};
      const head=renderer.xr.getCamera().getWorldPosition(new THREE.Vector3());
      return evaluateSourceFloorTeleport(
        manifest,id,[hit.point.x,hit.point.y,hit.point.z],
        [head.x,head.y,head.z],
      );
    }
    const xrGestures: (DraftGesture | null)[] = [null, null];
    const xrResize: (ResizeDrag | null)[] = [null, null];
    const xrPress: ({ context: PointerContext; menu: string | null; wallKey?:string|null } | null)[] = [null, null];
    const menuConsumed=[false,false];
    function menuTarget(layout:ReturnType<typeof menuLayout>){
      if(!toolsOpen)return null;
      if(layout.radial){
        const right=inputSources.find(s=>s?.handedness==="right");
        const i=thumbstickSector(standardThumbstick(right));
        if(i>=0)return {index:i,action:layout.buttons[i]?.disabled?null:layout.buttons[i]?.action??null};
      }
      return buildOverlay.menuHit(raycaster,layout);
    }
    function activateMenu(choice:MenuAction){
      displayedMenuLayout=null;
      menuAction(choice);
      if(choice.area==="build"||choice.area==="done"||choice.area==="footprint"||(choice.area==="items"&&choice.action.kind==="choose")||(choice.area==="draft"&&(choice.action==="move"||choice.action==="stretch"))||(choice.area==="opening"&&choice.action==="drag"))closeTools();
    }
    function activateDisplayedMenu(current: ReturnType<typeof menuLayout>) {
      const shown=displayedMenuLayout;
      if(!shown)return;
      const hit=menuTarget(shown);
      if(!hit?.action)return;
      const action=displayedMenuAction(shown,current,hit.index);
      if(action)activateMenu(action);
    }
    function menuKey(layout: ReturnType<typeof menuLayout>) {
      const hit=menuTarget(layout);
      return hit ? JSON.stringify(hit.action) : null;
    }
    function beginXrGesture(index: number) {
      menuConsumed[index]=false;
      aimController(controllers[index]);
      const layout = menuLayout("");
      if(toolsOpen){
        menuConsumed[index]=true;
        // The first trigger press activates one button. Release never needs to hit it again.
        if(inputSources[index]?.handedness!=="left"||!inputSources.some(s=>s?.handedness==="right")){
          activateDisplayedMenu(layout);
        }
        return;
      }
      const menu = menuKey(layout);
      xrPress[index] = { context: pointerContext(), menu,wallKey:!menu&&magnetic&&!build.current.buildState.tool&&!itemControls.current.active&&!resize.current.enabled&&!teleportSettings.current.teleportMode?targetWallAim()?.target.key??null:undefined };
      if (toolsOpen && (itemBrowser.open || stageMenuOpen || budgetOpen || layersOpen || wallProfilesOpen || helpOpen || menu !== null)) return;
      xrResize[index] = startResize();
      if (!xrResize[index]) {
        const gesture = draftGesture();
        if (gesture && "previous" in gesture) {
          const hand = controllers[index].getWorldPosition(new THREE.Vector3());
          gesture.fromController = [hand.x, hand.z];
        }
        xrGestures[index] = gesture;
      }
    }
    const selectStart0 = () => beginXrGesture(0), selectStart1 = () => beginXrGesture(1);
    const selectEnd = (index: number) => {
      xrGestures[index] = null; xrResize[index] = null; xrPress[index] = null;
    };
    const selectEnd0 = () => selectEnd(0), selectEnd1 = () => selectEnd(1);
    const trigger=(index:number)=>{
      if (!renderer.xr.isPresenting) return;
      if(menuConsumed[index]){menuConsumed[index]=false;return;}
      lastController = index;
      aimController(controllers[index]);
      const layout = menuLayout("");
      const press = xrPress[index];
      if (press && (!samePointerContext(press.context) || press.menu !== menuKey(layout))) {
        selectEnd(index);
        return;
      }
      reportTool("");
      const { buildState } = build.current;
      const resizing = xrResize[index];
      if (resizing) {
        xrResize[index] = null;
        resizeDrag(resizing);
        return;
      }
      const gesture = xrGestures[index];
      xrGestures[index] = null;
      if (gesture && completeDrag(gesture, index)) return;
      // Menu actions dispatch exclusively on selectstart.
      if(toolsOpen)return;
      if ((toolsOpen&&(itemBrowser.open || stageMenuOpen || budgetOpen || layersOpen || wallProfilesOpen || helpOpen)) || resize.current.enabled) return;
      const item = itemControls.current.active;
      if (item) {
        placeSelectedItem(item);
        return;
      }
      if (buildState.tool) {
        const placement = aim();
        if (placement.hit) place(placement.hit);
        else reportTool(placement.hint);
        return;
      }
      if(!teleportSettings.current.teleportMode){
        const switchDistance=itemView.previewSwitchDistance(raycaster);
        if(switchDistance<=3&&!multiSelect&&!elevatedReturn){
          const hit=raycaster.intersectObjects(pickables.filter(o=>o.visible&&o instanceof THREE.Mesh&&sourceVisible(o)&&displaySurface(construction.current.stage,o.userData.surfaceKind)),false)[0];
          if(!hit||hit.distance>=switchDistance-.02){visualSettings.current.onPreviewLights(!visualSettings.current.previewLights);reportTool("Local preview lights toggled (not electrical circuit wiring).");return;}
        }
        if(!toggleAimedDoor())selectAtRay(press?.wallKey);return;
      }
      if(!renderer.xr.isPresenting){
        teleportSettings.current.onTeleportMessage("Start a VR session before teleporting.");
        return;
      }
      const target=candidateTeleport(index);
      if(!target.accepted || !target.destination){
        teleportSettings.current.onTeleportMessage(describeTeleportReason(target.reason));
        return;
      }
      const space=renderer.xr.getReferenceSpace();
      if(!space || typeof XRRigidTransform==="undefined"){
        teleportSettings.current.onTeleportMessage("SteamVR has no movable WebXR reference space.");
        return;
      }
      const head=renderer.xr.getCamera().getWorldPosition(new THREE.Vector3());
      const x=head.x-target.destination[0];
      const z=head.z-target.destination[2];
      try {
        // An incremental XR reference-space offset moves the virtual
        // observer without modifying any PlanReader source geometry.
        moveNavOffset({position:{x,y:0,z},orientation:{x:0,y:0,z:0,w:1}});
        teleportSettings.current.onTeleportMessage(
          `Moved ${(target.distanceM??0).toFixed(1)}m on verified floor (review navigation only)`,
        );
      } catch {
        teleportSettings.current.onTeleportMessage(
          "SteamVR declined the teleport reference-space change.",
        );
      }
    };
    function toggleElevatedView(){
      const space=renderer.xr.getReferenceSpace();
      if(!renderer.xr.isPresenting||!space||typeof XRRigidTransform==="undefined")return;
      try{
        if(elevatedReturn){setNavOffset(elevatedReturn);elevatedReturn=null;reportTool("Returned to walkthrough position.");return;}
        const box=resize.current.box;
        if(!box){reportTool("Open a bounded building scene to use 3D bird’s-eye.");return;}
        const width=box.maxX-box.minX,depth=box.maxZ-box.minZ;
        const head=renderer.xr.getCamera().getWorldPosition(new THREE.Vector3());
        const height=Math.min(100,Math.max(5,Math.hypot(width,depth)*.65+3));
        const target={x:(box.minX+box.maxX)/2,y:height,z:(box.minZ+box.maxZ)/2};
        const offset=navigationOffset(head,{x:target.x-head.x,y:target.y-head.y,z:target.z-head.z},0);
        const previous=navOffset;
        moveNavOffset(offset);
        elevatedReturn=previous;
        reportTool("Elevated cutaway: look down, use left stick to pan. Walkthrough restores your position.");
      }catch{reportTool("The XR runtime declined the view change.");}
    }
    let collisionKey:readonly unknown[]=[];let collisionWalls:NavigationWall[]=[];
    function cachedNavigationWalls(){
      const stage=construction.current.stage,layers=construction.current.layers;
      const key=[interaction.current.visibleIds,resize.current.projection,build.current.buildState.walls,build.current.buildLevel,moveSettings.current.wallMoveState,stage,layers,openDoors];
      if(key.every((v,i)=>v===collisionKey[i]))return collisionWalls;
      collisionKey=key;collisionWalls=[];
      const walls=collisionWalls;
      const sourceMoves=new Map((moveSettings.current.wallMoveState?safeWallMoves(moveSettings.current.wallMoveState,manifest):[]).map(m=>[m.objectId,m]));
        for(const row of manifest.objects){
          const g=row.geometry;
          if(row.objectType!=="wall"||!g||!point2(g.start)||!point2(g.end)||!navigationWallFace(g,interaction.current.visibleIds.has(row.objectId)&&displaySurface(stage,undefined)))continue;
          const projection=resize.current.projection;
          const w=projection?{start:projectPlan(g.start,projection),end:projectPlan(g.end,projection)}:g;
          const move=sourceMoves.get(row.objectId);
          const dx=(move?.dx??0)*(projection?.scaleX??1),dz=(move?.dz??0)*(projection?.scaleZ??1);
          walls.push({start:[w.start[0]+dx,w.start[1]+dz],end:[w.end[0]+dx,w.end[1]+dz]});
        }
        for(const raw of build.current.buildState.walls){
          if(build.current.buildLevel&&raw.levelId!==build.current.buildLevel)continue;
          if(!layerVisible(layers,"wall",stage!=="slab"&&(stage!=="framing"&&stage!=="rough-in"||profileDetails(raw.assembly).core==="masonry"))&&!layerVisible(layers,"framing",stage==="framing"))continue;
          const w=resize.current.projection?projectWall(raw,resize.current.projection):raw;
          const showDoors=layerVisible(layers,"openings",stage!=="slab"&&stage!=="framing"&&stage!=="rough-in");
          walls.push(...localNavigationWalls(w,openDoors,showDoors));
        }
      return walls;
    }
    function stationaryNavigation(now:number){
      const dt=lastNavTime?Math.min(.05,Math.max(0,(now-lastNavTime)/1000)):0;
      lastNavTime=now;
      if(!renderer.xr.isPresenting||!dt||toolsOpen||xrPress.some(Boolean)||xrGestures.some(Boolean)||xrResize.some(Boolean)||activeGrip||itemBrowser.open||(toolsOpen&&(stageMenuOpen||budgetOpen||layersOpen||wallProfilesOpen||helpOpen||numberPad))||resize.current.enabled||teleportSettings.current.teleportMode)return;
      const left=inputSources.find(s=>s?.handedness==="left"),right=inputSources.find(s=>s?.handedness==="right");
      const move=standardThumbstick(left),rightStick=standardThumbstick(right);
      if(stickNeedsNeutral){if(Math.hypot(...rightStick)<.2)stickNeedsNeutral=false;else return;}
      const turn=snapTurn(rightStick[0],turnArmed);
      turnArmed=turn.armed;
      if(!move[0]&&!move[1]&&!turn.angle)return;
      const space=renderer.xr.getReferenceSpace();
      if(!space||typeof XRRigidTransform==="undefined")return;
      const headCamera=renderer.xr.getCamera(),head=headCamera.getWorldPosition(new THREE.Vector3());
      const direction=headCamera.getWorldDirection(new THREE.Vector3());
      const forward:[number,number]=Math.hypot(direction.x,direction.z)>.05?[direction.x,direction.z]:[0,-1];
      let delta=walkDelta(move,forward,walkSpeed,dt);
      const box=resize.current.box;
      if(!box)return;
      // Local navigation only: stay within the displayed building plus a 3m perimeter.
      const bounded=(at:number,d:number,min:number,max:number)=>at<min?Math.max(0,d):at>max?Math.min(0,d):Math.max(min,Math.min(max,at+d))-at;
      delta=[bounded(head.x,delta[0],box.minX-3,box.maxX+3),bounded(head.z,delta[1],box.minZ-3,box.maxZ+3)];
      if(!elevatedReturn&&!ghostMode){
        delta=collisionLimitedStep([head.x,head.z],delta,cachedNavigationWalls());
      }
      if(!delta[0]&&!delta[1]&&!turn.angle)return;
      try{
        const offset=navigationOffset(head,{x:delta[0],y:0,z:delta[1]},turn.angle);
        moveNavOffset(offset);
      }catch{lastNavTime=0;}
    }
    const select0 = () => trigger(0);
    const select1 = () => trigger(1);
    // SteamVR presents Sony Sense controllers as standard XR input sources.
    // Do not rely on a proprietary profile name or guessed Sony button IDs:
    // WebXR 'select' aims with the trigger, 'squeeze' invokes the grip action.
    // Some OpenXR/browser combinations omit squeeze events, so xr-standard
    // Gamepad button #1 is an opt-in semantic fallback (one action per release).
    const inputSources: (PcVrInputSource | null)[] = [null, null];
    const squeezeTracker = new PcVrSqueezeTracker();
    const report = (presenting = renderer.xr.isPresenting, performance?: PcVrSessionReport["performance"]) => {
      const controllerInfos = inputSources.map(inspectPcVrController)
        .filter((item): item is PcVrControllerInfo => item !== null);
      sessionReportCallback.current({presenting, controllers: controllerInfos, ...(performance?{performance}:{})});
    };
    function applyFinishSqueeze() {
      if (toolsBusy() || teleportSettings.current.teleportMode) return;
      const id = picked.current;
      if (id && sourceById.has(id)) cycleCallback.current(id);
    }
    // Standard Sense grip actions start/finish a reversible wall translation.
    // Original geometry stays untouched: only renderer Object3D.position moves.
    let activeGrip: { index:number; objectId:string; from:THREE.Vector3 } | null = null;
    const nativeGripSeen = [false,false], fallbackGripDown = [false,false];
    const beginGrip = (index:number) => {
      if (interaction.current.mode !== "wall-move" || itemBrowser.open || stageMenuOpen || budgetOpen || activeGrip) return;
      const id = picked.current;
      const row = sourceById.get(id ?? "");
      if (!id || !row || row.objectType !== "wall" ||
          !row.geometry || !["wallFace","wallLine"].includes(row.geometry.kind)) return;
      activeGrip = {index,objectId:id,
        from:controllers[index].getWorldPosition(new THREE.Vector3())};
    };
    const endGrip = (index:number) => {
      const held=activeGrip;
      if (!held || held.index !== index) return;
      activeGrip=null;
      if (interaction.current.mode !== "wall-move" || itemBrowser.open || stageMenuOpen || budgetOpen) return;
      const p=controllers[index].getWorldPosition(new THREE.Vector3());
      const dx=p.x-held.from.x,dz=p.z-held.from.z;
      if (Number.isFinite(dx)&&Number.isFinite(dz))
        moveSettings.current.onMoveDelta(held.objectId,dx,dz);
    };
    function handleGripAction(index:number){
      if(inputSources[index]?.handedness==="left"){toggleTools();return;}
      if(moveSettings.current.moveMode!=="move")applyFinishSqueeze();
    }
    const nativeStart0 = () => {
      squeezeTracker.onNativeStart("0");
      nativeGripSeen[0] = true;
      if(inputSources[0]?.handedness!=="left")beginGrip(0);
    };
    const nativeStart1 = () => {
      squeezeTracker.onNativeStart("1");
      nativeGripSeen[1] = true;
      if(inputSources[1]?.handedness!=="left")beginGrip(1);
    };
    const nativeEnd0 = () => endGrip(0), nativeEnd1 = () => endGrip(1);
    const squeeze0 = () => {
      if (squeezeTracker.onNativeSqueeze("0"))handleGripAction(0);
    };
    const squeeze1 = () => {
      if (squeezeTracker.onNativeSqueeze("1"))handleGripAction(1);
    };
    const connected = (event: unknown, index: number) => {
      const source = event && typeof event === "object" && "data" in event
        ? (event as {data?: PcVrInputSource}).data ?? null : null;
      inputSources[index] = source;
      squeezeTracker.clear(String(index));
      nativeGripSeen[index]=false;
      fallbackGripDown[index]=false;
      if(activeGrip?.index===index)activeGrip=null;
      report();
    };
    const disconnect = (index: number) => {
      inputSources[index] = null;
      squeezeTracker.clear(String(index));
      selectEnd(index);
      menuConsumed[index]=false;
      nativeGripSeen[index]=false;
      fallbackGripDown[index]=false;
      if(activeGrip?.index===index)activeGrip=null;
      report();
    };
    const connected0 = (event: unknown) => connected(event, 0);
    const connected1 = (event: unknown) => connected(event, 1);
    const disconnected0 = () => disconnect(0);
    const disconnected1 = () => disconnect(1);
    const onSessionStart = () => {
      toolsOpen=false;ghostMode=false;displayedMenuLayout=null;menuPose=null;menuConsumed.fill(false);renderer.shadowMap.enabled=false;
      reportTool("Left grip opens tools. Aim or use right stick, then trigger. Left stick walks when tools are closed.");
      elevatedReturn=null;navBase=null;navOffset=identityNavOffset();turnArmed=true;lastNavTime=0;
      cancelPointer();
      lastController = -1;
      squeezeTracker.clear();
      nativeGripSeen.fill(false);
      fallbackGripDown.fill(false);
      activeGrip=null;
      report(true);
    };
    const onSessionEnd = () => {
      closeTools();ghostMode=false;renderer.shadowMap.enabled=true;
      budgetOpen=false;budgetPage=0;
      elevatedReturn=null;navBase=null;navOffset=identityNavOffset();turnArmed=true;lastNavTime=0;
      buildOverlay.hideMenu();
      itemBrowser = EMPTY_ITEM_BROWSER;
      stageMenuOpen = false;
      xrGestures.fill(null);
      xrResize.fill(null);
      xrPress.fill(null);menuConsumed.fill(false);
      inputSources[0] = null;
      inputSources[1] = null;
      squeezeTracker.clear();
      nativeGripSeen.fill(false);
      fallbackGripDown.fill(false);
      activeGrip=null;
      report(false);
    };
    renderer.xr.addEventListener("sessionstart", onSessionStart);
    renderer.xr.addEventListener("sessionend", onSessionEnd);
    controllers[0].addEventListener("connected", connected0);
    controllers[1].addEventListener("connected", connected1);
    controllers[0].addEventListener("disconnected", disconnected0);
    controllers[1].addEventListener("disconnected", disconnected1);
    controllers[0].addEventListener("squeezestart", nativeStart0);
    controllers[1].addEventListener("squeezestart", nativeStart1);
    controllers[0].addEventListener("squeezeend", nativeEnd0);
    controllers[1].addEventListener("squeezeend", nativeEnd1);
    controllers[0].addEventListener("squeeze", squeeze0);
    controllers[1].addEventListener("squeeze", squeeze1);
    controllers[0].addEventListener("select", select0);
    controllers[1].addEventListener("select", select1);
    controllers[0].addEventListener("selectstart", selectStart0);
    controllers[1].addEventListener("selectstart", selectStart1);
    controllers[0].addEventListener("selectend", selectEnd0);
    controllers[1].addEventListener("selectend", selectEnd1);
    for (const controller of controllers) {
      const pointer = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, -2)
        ]),
        new THREE.LineBasicMaterial({ color: 0x45c6b4 })
      );
      controller.add(pointer);
      scene.add(controller);
    }

    // Keep local-floor / bounded-floor optional for the SteamVR OpenXR runtime.
    // The browser remains responsible for opening the immersive session.
    const vrButton = VRButton.createButton(renderer, {
      optionalFeatures: ["local-floor", "bounded-floor"],
    });
    vrButton.setAttribute("aria-label", "Enter or exit VR");
    parent.append(vrButton);

    function onResize() {
      // The compositor owns the immersive framebuffer; desktop ResizeObserver
      // events must not resize the renderer while the headset is presenting.
      if(renderer.xr.isPresenting)return;
      const width = Math.max(parent?.clientWidth || 1, 1);
      const height = Math.max(parent?.clientHeight || 1, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }
    const resizeObserver = new ResizeObserver(onResize);
    resizeObserver.observe(parent);
    onResize();

    let selectedLabel: THREE.Sprite | null = null;
    let draftDimension:THREE.Sprite|null=null,draftDimensionKey="";
    let lastLabelId: string | null = null;
    const dimensionGroup=new THREE.Group();scene.add(dimensionGroup);
    let dimensionsKey:readonly unknown[]=[];
    function clearDimensions(){for(const child of [...dimensionGroup.children]){dimensionGroup.remove(child);if(child instanceof THREE.Sprite){child.material.map?.dispose();child.material.dispose();}}}
    function refreshDimensions(){
      const s=construction.current,visible=interaction.current.visibleIds,b=build.current.buildState,projection=resize.current.projection;
      const currentLevel=interaction.current.level,sourceMoves=moveSettings.current.wallMoveState;
      const key=[s.allDimensions,s.stage,s.layers,visible,b.walls,b.ceilings,currentLevel,projection,sourceMoves,!!elevatedReturn];
      if(key.every((v,i)=>v===dimensionsKey[i]))return;dimensionsKey=key;clearDimensions();
      if(!s.allDimensions)return;
      // Suppress original dimensions when source moves or footprint projection are active.
      const sourceVisibleIds=projection||sourceMoves?new Set<string>():visible;
      const geometry=projection?{walls:b.walls.map(w=>projectWall(w,projection)),ceilings:b.ceilings.map(c=>projectCeiling(c,projection))}:b;
      const entries=reviewDimensions(manifest,geometry,currentLevel,sourceVisibleIds).filter(d=>displaySurface(s.stage,d.kind==="wall"?undefined:d.kind));
      // Cap simultaneous sprites for standalone headset memory; selected dimensions remain available separately.
      for(const d of entries.slice(0,40)){const sprite=labelSprite(d.label);sprite.position.set(...d.position);sprite.scale.set(1.45,.29,1);dimensionGroup.add(sprite);}
    }
    let lastMood: LightingMood | null = null;
    let lastPreviewLighting=-Infinity;
    const lightEye=new THREE.Vector3();
    let lastQuality: RenderQuality | null = null;
    let lastPresenting=false;
    let lastDetail: SurfaceDetail | null = null;
    let lastCameraSerial: number | null = null;
    let lastCaptureSerial = visualSettings.current.captureSerial;
    let disposed = false;
    const gripPosition = new THREE.Vector3();
    let indexedMoveState: WallMoveHistory | null | undefined;
    const movesById = new Map<string, ReturnType<typeof safeWallMoves>[number]>();
    let frameStart=0,previousFrame=0,frameCount=0,worstFrame=0,slowWindows=0,fastWindows=0;
    let sourceAppearanceKey: readonly unknown[] = [];
    let surfaceVisibilityKey: readonly unknown[] = [];
    renderer.setAnimationLoop((now) => {
      stationaryNavigation(now);
      const { mood: activeMood, quality: activeQuality, detail: activeDetail,
        inspection: activeInspection, cameraRequest: requestedCamera } = visualSettings.current;
      // Fallback xr-standard grips when SteamVR omits native squeeze events.
      // Native grip events always take precedence. Neither path changes source.
      const { buildState, buildLevel } = build.current;
      if (interaction.current.mode !== "wall-move" || itemBrowser.open || stageMenuOpen || budgetOpen) activeGrip=null;
      if (renderer.xr.isPresenting) {
        for (let index=0;index<inputSources.length;index++) {
          const pressed=standardSqueezePressed(inputSources[index]);
          if (moveSettings.current.moveMode === "move" &&
              !nativeGripSeen[index] && pressed !== null && inputSources[index]?.handedness!=="left") {
            if (pressed && !fallbackGripDown[index]) beginGrip(index);
            if (!pressed && fallbackGripDown[index]) endGrip(index);
            fallbackGripDown[index] = pressed;
          }
          if (squeezeTracker.poll(String(index),pressed))handleGripAction(index);
        }
      }
      const moveState = moveSettings.current.wallMoveState;
      if (moveState !== indexedMoveState) {
        indexedMoveState = moveState;
        movesById.clear();
        for (const move of moveState ? safeWallMoves(moveState, manifest) : []) {
          if (!movesById.has(move.objectId)) movesById.set(move.objectId, move);
        }
      }
      let dragX=0,dragZ=0;
      if (activeGrip && moveSettings.current.moveMode === "move") {
        const p=controllers[activeGrip.index].getWorldPosition(gripPosition);
        dragX=p.x-activeGrip.from.x;dragZ=p.z-activeGrip.from.z;
      }
      const projectionX=resize.current.projection?.scaleX ?? 1;
      const projectionZ=resize.current.projection?.scaleZ ?? 1;
      for (const obj of pickables) {
        const id=obj.userData.objectId as string|undefined;
        const move=id === undefined ? undefined : movesById.get(id);
        const held=activeGrip?.objectId===id;
        const dx=(move?.dx??0)+(held?dragX:0);
        const dz=(move?.dz??0)+(held?dragZ:0);
        if (Number.isFinite(dx)&&Number.isFinite(dz)) {
          const x=dx*projectionX,z=dz*projectionZ;
          if(obj.position.x!==x||obj.position.y!==0||obj.position.z!==z)obj.position.set(x,0,z);
        }
      }
      if (startPointer && !samePointerContext(startPointer.context)) cancelPointer();
      syncItems();
      planOverview.update(build.current.buildState,interaction.current.level,
        interaction.current.visibleIds,renderer.xr.isPresenting?renderer.xr.getCamera():camera,
        renderer.xr.isPresenting&&overviewOpen);
      gizmo.show(resize.current.enabled ? resize.current.box : null);
      if (startPointer?.resize && hoveringCanvas && !renderer.xr.isPresenting) {
        raycaster.setFromCamera(mouse, camera);
        resizeDrag(startPointer.resize);
      }
      const currentStage = construction.current.stage;
      refreshDimensions();refreshShell();
      if(now-lastPreviewLighting>=150){(renderer.xr.isPresenting?renderer.xr.getCamera():camera).getWorldPosition(lightEye);itemView.updatePreviewLights(visualSettings.current.previewLights,lightEye);lastPreviewLighting=now;}
      const framing = currentStage === "framing" || currentStage === "rough-in";
      const visibilityKey=[currentStage,construction.current.layers,interaction.current.visibleIds,
        resize.current.projection,draftMap.current,!!elevatedReturn,lastAddedWall];
      if(!visibilityKey.every((v,i)=>v===surfaceVisibilityKey[i])){
      surfaceVisibilityKey=visibilityKey;
      for (const obj of pickables) {
        const kind = obj.userData.surfaceKind;
        const displayed = sourceVisible(obj);
        const visible = displaySurface(currentStage, kind);
        if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshStandardMaterial) {
          obj.visible = displayed;
          obj.material.visible = visible;
          obj.material.wireframe = !kind && framing;
          for(const child of obj.children)if(child.userData.openingReview)child.visible=visible&&!resize.current.projection&&layerVisible(construction.current.layers,"openings",currentStage!=="slab")&&!draftMap.current.get(obj.userData.objectId)?.heightM;
          if (kind === "roof") obj.castShadow = visible;
        } else obj.visible = displayed && visible;
      }
      for (const shape of wallAdditionLayer.children) {
        shape.visible = true;
        if (shape instanceof THREE.Mesh && shape.material instanceof THREE.MeshStandardMaterial) {
          shape.material.visible = displaySurface(currentStage, "ceiling");
        } else {
          for (const child of shape.children) {
            if (child.userData.illustrativeFraming) child.visible = layerVisible(construction.current.layers,"framing",currentStage==="framing");
            else if(child.userData.illustrativeInsulation)child.visible=layerVisible(construction.current.layers,"insulation",false);
            else if(child instanceof THREE.Mesh&&child.material instanceof THREE.MeshStandardMaterial){
              const showBody=layerVisible(construction.current.layers,"wall",currentStage!=="slab"&&(!framing||shape.userData.masonryAssembly===true));
              child.material.visible=child.userData.exteriorTexture?showBody&&layerVisible(construction.current.layers,"envelope",!framing):
                child.userData.catalogueDoorLeaf?layerVisible(construction.current.layers,"openings",currentStage!=="slab"&&!framing):showBody;
            } else if(child instanceof THREE.Line)child.visible=layerVisible(construction.current.layers,"wall",currentStage!=="slab");
          }
        }
      }
      }
      const origin = activeStart(buildState, buildLevel);
      const item = itemControls.current.active;
      const prompt = resize.current.enabled ? resize.current.hint || "Drag a green corner or gold edge handle." :
        item ? itemGuide(item) : buildGuide(buildState, buildLevel);
      let activeDimensionRay=false;
      if (renderer.xr.isPresenting) {
        const layout = toolsOpen ? menuLayout(prompt) : null;
        if(layout){
          buildOverlay.sizeMenu(layout);
          const pose=layout.radial?"radial":"panel";
          // Keep one world-space anchor through submenu transitions. Never
          // attach the tool surface to a moving controller during selection.
          if(menuPose===null)buildOverlay.positionMenu(renderer.xr.getCamera(),true,true);
          else if(!panelPinned)buildOverlay.positionMenu(renderer.xr.getCamera(),false);
          if(menuPose!==pose){menuPose=pose;lastMenuHover=-2;}
        }
        const isPointer = (source: PcVrInputSource | null | undefined) => source?.targetRayMode === "tracked-pointer";
        const favoured = !toolsOpen&&isPointer(inputSources[lastController]) ? lastController :
          inputSources.findIndex(source => isPointer(source) && source?.handedness === "right");
        const active = favoured >= 0 ? favoured : inputSources.findIndex(isPointer);
        if (active >= 0) aimController(controllers[active]);
        activeDimensionRay=active>=0&&!buildState.tool&&!item&&!toolsOpen;
        const hover=active>=0&&layout?menuTarget(layout):null;
        const hostTool=buildState.tool==="door"||buildState.tool==="window"||buildState.tool==="frame"||buildState.tool==="move"||buildState.tool==="stretch"||buildState.tool==="opening-move";
        const canLock=active>=0&&!hover&&(!buildState.tool||hostTool)&&!item&&!toolsOpen&&!resize.current.enabled&&!teleportSettings.current.teleportMode;
        if(canLock&&magnetic){
          const held=xrPress[active]?.wallKey;
          const target=held?visibleWallTargets().find(t=>t.key===held):null;
          wallLock=held?(target?wallAimWithin(raycaster.ray,target):null):hostTool?chooseWallAim(raycaster.ray,visibleWallTargets().filter(t=>t.kind==="draft"),wallLock?.target.key??null,true):targetWallAim();
        }else wallLock=null;
        hoveredSourceId=wallLock?.target.kind==="source"?wallLock.target.id:null;
        hoveredDraftId=wallLock?.target.kind==="draft"?wallLock.target.id:null;
        const heldResize = xrResize.findIndex(drag => drag !== null);
        if (heldResize >= 0 && xrPress[heldResize] && samePointerContext(xrPress[heldResize]!.context)) {
          aimController(controllers[heldResize]);
          resizeDrag(xrResize[heldResize]!);
        }
        const held = xrGestures.findIndex(gesture => gesture !== null);
        if (held >= 0) aimController(controllers[held]);
        const ready = active >= 0 && !toolsOpen && !hover && !itemBrowser.open && !stageMenuOpen && !budgetOpen && !layersOpen && !wallProfilesOpen &&
          !helpOpen && !resize.current.enabled;
        const itemPick = ready && item ? itemView.candidate(raycaster, item, itemControls.current.turn) : null;
        const drag = held >= 0 && xrPress[held] && samePointerContext(xrPress[held]!.context) ? xrGestures[held] : null;
        const dragPreview=drag ? previewDrag(drag, held) : null;
        const buildTarget = dragPreview?.aim ?? (ready&&!item?aim():null);
        const draftAction=dragPreview?.action;
        buildOverlay.showWallGhost(draftAction?.kind==="adjust" ? draftAction.wall :
          draftAction?.kind==="drag" && drag?.mode==="wall"
          ? {start:draftAction.from,end:draftAction.to,heightM:buildSizes.wallHeightM,assembly:buildSizes.wallAssembly} : null);
        itemView.aim(itemPick?.hit ?? null);
        buildOverlay.showAim(buildTarget, item || itemBrowser.open ? null : origin);
        if (layout && !itemBrowser.open && !stageMenuOpen && !budgetOpen && !layersOpen && !wallProfilesOpen && !helpOpen && !selectedDraftWall())
          layout.note = itemPick?.hit ? "Pull the trigger to place." :
          itemPick?.reason ?? buildTarget?.hint ?? prompt;
        if(layout){
          const signature=JSON.stringify(layout);
          if(signature!==lastMenuSignature||(hover?.index??-1)!==lastMenuHover){
            buildOverlay.drawMenu(layout,hover?.index??-1);
            lastMenuSignature=signature;
          }
          displayedMenuLayout=layout;
          lastMenuDraw=now;lastMenuHover=hover?.index??-1;
        }
      } else {
        hoveredDraftId=null;hoveredSourceId=null;wallLock=null;
        const drag = startPointer?.gesture;
        const canAim = !!(buildState.tool || item) && hoveringCanvas && (!startPointer || !!drag);
        if (canAim) raycaster.setFromCamera(mouse, camera);
        const itemPick = canAim && item ? itemView.candidate(raycaster, item, itemControls.current.turn) : null;
        const dragPreview=canAim&&!item&&drag?previewDrag(drag):null;
        const buildTarget=canAim&&!item ? dragPreview?.aim??aim() : null;
        const draftAction=dragPreview?.action;
        buildOverlay.showWallGhost(draftAction?.kind==="adjust" ? draftAction.wall :
          draftAction?.kind==="drag" && drag?.mode==="wall"
          ? {start:draftAction.from,end:draftAction.to,heightM:buildSizes.wallHeightM,assembly:buildSizes.wallAssembly} : null);
        itemView.aim(itemPick?.hit ?? null);
        buildOverlay.showAim(buildTarget, item ? null : origin);
        setBuildHint(item ? (itemPick?.hit ? "Click to place " + item.label + "." :
          itemPick?.reason ?? itemGuide(item)) : buildTarget?.hint ?? "");
      }
      // Local draft-only selection/hover highlight. No source mesh or priced
      // quantity is modified; original colours are restored when deselected.
      for (const group of wallAdditionLayer.children) {
        if (!group.userData.reviewOnlyWallProposal) continue;
        const id = group.userData.proposalId as string;
        const selected = id === selectedDraftId || (multiSelect&&selectedGroup.has(id));
        const hovered = id === hoveredDraftId;
        const highlightState=selected ? 2 : hovered ? 1 : 0;
        if(group.userData.lastDraftHighlight===highlightState)continue;
        group.userData.lastDraftHighlight=highlightState;
        for (const part of group.children) {
          if (!(part instanceof THREE.Mesh || part instanceof THREE.Line)) continue;
          const material = part.material;
          if (!(material instanceof THREE.MeshBasicMaterial || material instanceof THREE.MeshStandardMaterial ||
                material instanceof THREE.LineBasicMaterial)) continue;
          if (part.userData.originalDraftColor === undefined)
            part.userData.originalDraftColor=material.color.getHex();
          const base = part.userData.originalDraftColor as number;
          if (material instanceof THREE.MeshStandardMaterial) {
            material.emissive.setHex(selected ? 0x16ad83 : hovered ? 0xe5a324 : 0);
            material.emissiveIntensity=selected||hovered ? .65 : 0;
          } else material.color.setHex(selected ? 0x40eed8 : hovered ? 0xf2dc80 : base);
        }
      }
      // One reusable on-model dimension sprite; no per-frame texture allocation.
      let target:THREE.Object3D|undefined;
      if(dimensions&&renderer.xr.isPresenting&&!toolsOpen){
        const id=hoveredDraftId??selectedDraftId;
        target=wallAdditionLayer.children.find(o=>o.visible&&o.userData.proposalId===id&&id);
        if(!target&&activeDimensionRay&&currentStage!=="slab"&&!elevatedReturn){
          target=raycaster.intersectObjects(wallAdditionLayer.children.filter(o=>o.visible&&o.userData.ceilingDimensions&&displaySurface(currentStage,"ceiling")),false)[0]?.object;
        }
      }
      const dimText=target?(target.userData.wallDimensions??target.userData.ceilingDimensions):"";
      const dimKey=dimText?String(dimText)+"|"+target!.uuid:"";
      if(dimKey!==draftDimensionKey){
        if(draftDimension){scene.remove(draftDimension);draftDimension.material.map?.dispose();draftDimension.material.dispose();draftDimension=null;}
        draftDimensionKey=dimKey;
        if(target&&dimText){
          draftDimension=labelSprite(dimText);
          const box=new THREE.Box3().setFromObject(target);
          draftDimension.position.copy(box.getCenter(new THREE.Vector3()));
          draftDimension.position.y=box.max.y+.18;
          draftDimension.scale.set(1.65,.33,1);
          scene.add(draftDimension);
        }
      }
      // Aiming at source-backed floor is visible only in immersive VR.
      // Never display this marker over an invented presentation floor.
      teleportMarker.visible=false;
      if(renderer.xr.isPresenting && interaction.current.mode === "teleport" &&
          !itemBrowser.open && !stageMenuOpen && !budgetOpen && !layersOpen && !wallProfilesOpen && teleportSettings.current.teleportMode) {
        for(let index=0;index<controllers.length;index++) {
          const source=inputSources[index];
          if(!source || source.targetRayMode!=="tracked-pointer")continue;
          const target=candidateTeleport(index);
          if(target.accepted && target.destination){
            const [x,y,z]=target.destination;
            teleportMarker.position.set(x,y+.02,z);
            teleportMarker.visible=true;
            break;
          }
        }
      }
      grid.visible = activeInspection.showGrid;
      sunlight.castShadow = activeInspection.showShadows&&!renderer.xr.isPresenting;
      presentationFloor.visible = activeInspection.showShadows&&!renderer.xr.isPresenting;
      if (lastMood !== activeMood) {
        const preset = VISUAL_PRESETS[activeMood];
        scene.background = new THREE.Color(preset.background);
        ambient.color.setHex(preset.ambientSky);
        ambient.groundColor.setHex(preset.ambientGround);
        ambient.intensity = preset.ambientIntensity;
        sunlight.color.setHex(preset.sunColor);
        sunlight.intensity = preset.sunIntensity;
        sunlight.position.set(...preset.sunPosition).add(lightCenter);
        renderer.toneMappingExposure = preset.exposure;
        for (const item of pickables) {
          if (item instanceof THREE.Mesh && item.material instanceof THREE.MeshStandardMaterial) {
            item.material.roughness = preset.materialRoughness;
          }
        }
        lastMood = activeMood;
      }
      if (lastDetail !== activeDetail) {
        for (const item of pickables) {
          if (!(item instanceof THREE.Mesh) ||
              !(item.material instanceof THREE.MeshStandardMaterial)) continue;
          const nextMap = activeDetail === "subtle" && item.userData.sourceWitnessedFace
            ? roughTile : null;
          if (item.material.roughnessMap !== nextMap) {
            item.material.roughnessMap = nextMap;
            item.material.needsUpdate = true;
          }
        }
        lastDetail = activeDetail;
      }
      if (lastQuality !== activeQuality||lastPresenting!==renderer.xr.isPresenting) {
        const size = shadowMapSize(activeQuality);
        sunlight.shadow.mapSize.set(size, size);
        if (sunlight.shadow.map) {
          sunlight.shadow.map.dispose();
          sunlight.shadow.map = null;
        }
        if(!renderer.xr.isPresenting){
          renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1,
            maxRenderPixelRatio(activeQuality,false)));
          onResize();
        }
        lastQuality = activeQuality;
        lastPresenting=renderer.xr.isPresenting;
      }
      if (requestedCamera.serial !== lastCameraSerial && !renderer.xr.isPresenting) {
        const focus = requestedCamera.focus === "selected" ?
          pickables.find(obj => sourceVisible(obj) && obj.userData.objectId === picked.current) : null;
        const bounds = new THREE.Box3();
        const displayed = pickables.filter(object => sourceVisible(object) &&
          displaySurface(currentStage, object.userData.surfaceKind));
        for (const object of focus ? [focus] : [...displayed, ...wallAdditionLayer.children.filter(object => object.visible)])
          bounds.expandByObject(object);
        if (!bounds.isEmpty()) {
          const center = bounds.getCenter(new THREE.Vector3());
          const diagonal = Math.max(3, bounds.getSize(new THREE.Vector3()).length());
          const distance = Math.max(4, diagonal * 1.15);
          const offset = new THREE.Vector3();
          switch (requestedCamera.mode) {
            case "plan": offset.set(0.0001, distance, 0); break;
            case "north": offset.set(0, diagonal * 0.3, distance); break;
            case "east": offset.set(distance, diagonal * 0.3, 0); break;
            default: offset.set(distance * 0.75, distance * 0.6, distance * 0.75);
          }
          controls.target.copy(center);
          camera.position.copy(center).add(offset);
          camera.up.set(0, requestedCamera.mode === "plan" ? 0 : 1,
            requestedCamera.mode === "plan" ? -1 : 0);
          camera.lookAt(center);
          controls.update();
        }
        lastCameraSerial = requestedCamera.serial;
      }
      // Render-only proposals; underlying source geometry and manifest are untouched.
      // Ghost heights may only modify an EXISTING display wall-face mesh.
      const appearanceKey=[draftMap.current,moveState,activeGrip?.objectId,picked.current,
        hoveredSourceId,activeInspection.showGhosts,appliedProjection];
      if(!appearanceKey.every((v,i)=>v===sourceAppearanceKey[i])){
      sourceAppearanceKey=appearanceKey;
      for (const item of pickables) {
        if (!(item instanceof THREE.Mesh) || !(item.material instanceof THREE.MeshStandardMaterial)) continue;
        const id = item.userData.objectId as string;
        const row = sourceById.get(id);
        if (!row) continue;
        const draft = draftMap.current.get(id);
        const swatch = studyColor(row, draft?.swatch ? { objectId: id, swatch: draft.swatch } : null);
        const originalHeight = item.userData.originalHeight as number | undefined;
        const ghostHeight = draft?.heightM;
        const moved=movesById.has(id) ||
          activeGrip?.objectId===id;
        const ghost=(activeInspection.showGhosts && ghostHeight !== null &&
          ghostHeight !== undefined && originalHeight !== undefined) || moved;
        const colour = swatch ?? (ghost ? 0xb899de : item.userData.originalReviewColor as number);
        if (item.material.color.getHex() !== colour) item.material.color.setHex(colour);
        const originalOpacity = item.userData.originalOpacity as number;
        item.material.opacity = ghost ? 0.30 : originalOpacity;
        item.material.transparent = ghost || originalOpacity < 1;
        item.material.depthWrite = !ghost && originalOpacity >= 0.9;
        // Highlight selection without repainting the verified/source-study colour.
        const selected = picked.current === id;
        const hovered=hoveredSourceId===id;
        item.material.emissive.setHex(selected ? 0x16ad83 : hovered ? 0xe5a324 : 0);
        item.material.emissiveIntensity = selected||hovered ? .65 : 0;
        if (originalHeight !== undefined) {
          const height=activeInspection.showGhosts && ghostHeight !== null &&
            ghostHeight !== undefined ? ghostHeight : originalHeight;
          const position = item.geometry.getAttribute("position");
          if (position instanceof THREE.BufferAttribute && position.getY(2) !== Math.fround(height)) {
            // Triangle vertices 2, 4 and 5 are the upper face vertices.
            position.setY(2, height); position.setY(4, height); position.setY(5, height);
            position.needsUpdate = true;
            item.geometry.computeVertexNormals();
            item.geometry.computeBoundingBox();
            item.geometry.computeBoundingSphere();
          }
        }
      }
      }
      const labelVisible = picked.current && pickables.some(object => sourceVisible(object) && object.userData.objectId === picked.current &&
        displaySurface(currentStage, object.userData.surfaceKind));
      const labelKey = labelVisible && activeInspection.showLabels && !appliedProjection
        ? `${picked.current}|${activeInspection.showDimensions}` : null;
      if (labelKey !== lastLabelId) {
        if (selectedLabel) {
          scene.remove(selectedLabel);
          selectedLabel.material.map?.dispose();
          selectedLabel.material.dispose();
          selectedLabel = null;
        }
        lastLabelId = labelKey;
        if (picked.current && labelKey) {
          const id = picked.current;
          const sourceObject = pickables.find(x => x.userData.objectId === id);
          const row = sourceById.get(id);
          if (sourceObject && row) {
            const dims = activeInspection.showDimensions
              ? sourceWallDimensions(row) : null;
            selectedLabel = labelSprite(dims ? dims.label : id);
            const bounds = new THREE.Box3().setFromObject(sourceObject);
            selectedLabel.position.copy(bounds.getCenter(new THREE.Vector3()));
            selectedLabel.position.y += 1.2;
            scene.add(selectedLabel);
          }
        }
      }
      if(!renderer.xr.isPresenting)controls.update();
      renderer.render(scene, camera);
      // Frame callback cadence is diagnostic, not a compositor/GPU time measurement.
      // Adjust only WebXR foveation (when supported), never geometry or source authority.
      if(renderer.xr.isPresenting){
        if(!frameStart){frameStart=now;previousFrame=now;}
        else{
          worstFrame=Math.max(worstFrame,now-previousFrame);previousFrame=now;frameCount++;
          const elapsed=now-frameStart;
          if(elapsed>=2000&&frameCount>0){
            const fps=frameCount*1000/elapsed;
            const target=(renderer.xr.getSession() as (XRSession & {frameRate?:number})|null)?.frameRate||72;
            slowWindows=fps<target*.85?slowWindows+1:0;
            fastWindows=fps>=target*.97?fastWindows+1:0;
            const foveation=renderer.xr.getFoveation();
            if(typeof foveation==="number"&&Number.isFinite(foveation)){
              if(slowWindows>=2){renderer.xr.setFoveation(Math.min(1,foveation+.15));slowWindows=0;}
              else if(fastWindows>=5){renderer.xr.setFoveation(Math.max(.25,foveation-.1));fastWindows=0;}
            }
            report(true,{fps:Math.round(fps),frameMs:elapsed/frameCount,worstMs:worstFrame,
              drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,
              geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures,
              foveation:renderer.xr.getFoveation()??0});
            frameStart=now;frameCount=0;worstFrame=0;
          }
        }
      }else{frameStart=0;previousFrame=0;frameCount=0;worstFrame=0;slowWindows=0;fastWindows=0;}
      const request = visualSettings.current;
      if (request.captureSerial !== lastCaptureSerial) {
        lastCaptureSerial = request.captureSerial;
        if (renderer.xr.isPresenting) {
          request.onCapture("Exit headset mode before exporting a desktop review image.");
        } else {
          try {
            const size = safeCaptureSize(renderer.domElement.width, renderer.domElement.height);
            if (!size) throw Error("Invalid capture canvas dimensions.");
            const copy = document.createElement("canvas");
            copy.width = size[0]; copy.height = size[1];
            const context = copy.getContext("2d");
            if (!context) throw Error("Canvas image export is unsupported.");
            // Copy within the same rendered frame: WebGL draw buffer is not
            // required to be preserved after this callback.
            context.drawImage(renderer.domElement, 0, 0, copy.width, copy.height);
            const stamp = reviewStamp(manifest, interaction.current.visibleIds.size);
            drawReviewStamp(context, copy.width, copy.height, stamp);
            copy.toBlob(blob => {
              if (disposed) return;
              if (!blob) {
                request.onCapture("Browser could not encode the review image."); return;
              }
              const url = URL.createObjectURL(blob);
              const link = document.createElement("a");
              link.href = url; link.download = stamp.filename; link.click();
              URL.revokeObjectURL(url);
              request.onCapture("Exported a visual review image. This is not a measurement.");
            }, "image/png");
          } catch {
            request.onCapture("Review image export failed in this browser.");
          }
        }
      }
    });

    return () => {
      disposed = true;
      renderer.setAnimationLoop(null);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("dragover", dragOver);
      renderer.domElement.removeEventListener("drop", dropItem);
      renderer.domElement.removeEventListener("pointerdown", pointerDown, true);
      renderer.domElement.removeEventListener("pointerup", pointerUp);
      renderer.domElement.removeEventListener("pointermove", trackPointer);
      renderer.domElement.removeEventListener("pointerleave", leaveCanvas);
      renderer.domElement.removeEventListener("pointercancel", cancelPointer);
      renderer.domElement.removeEventListener("lostpointercapture", cancelPointer);
      window.removeEventListener("blur", cancelPointer);
      renderer.xr.removeEventListener("sessionstart", onSessionStart);
      renderer.xr.removeEventListener("sessionend", onSessionEnd);
      controllers[0].removeEventListener("connected", connected0);
      controllers[1].removeEventListener("connected", connected1);
      controllers[0].removeEventListener("disconnected", disconnected0);
      controllers[1].removeEventListener("disconnected", disconnected1);
      controllers[0].removeEventListener("squeezestart", nativeStart0);
      controllers[1].removeEventListener("squeezestart", nativeStart1);
      controllers[0].removeEventListener("squeezeend", nativeEnd0);
      controllers[1].removeEventListener("squeezeend", nativeEnd1);
      controllers[0].removeEventListener("squeeze", squeeze0);
      controllers[1].removeEventListener("squeeze", squeeze1);
      squeezeTracker.clear();
      sessionReportCallback.current({presenting:false,controllers:[]});
      controllers[0].removeEventListener("select", select0);
      controllers[1].removeEventListener("select", select1);
      controllers[0].removeEventListener("selectstart", selectStart0);
      controllers[1].removeEventListener("selectstart", selectStart1);
      controllers[0].removeEventListener("selectend", selectEnd0);
      controllers[1].removeEventListener("selectend", selectEnd1);
      controls.dispose();
      if (selectedLabel) {
        scene.remove(selectedLabel);
        selectedLabel.material.map?.dispose();
        selectedLabel.material.dispose();
      }
      if(draftDimension){scene.remove(draftDimension);draftDimension.material.map?.dispose();draftDimension.material.dispose();}
      clearDimensions();scene.remove(dimensionGroup);
      itemView.clear();
      scene.traverse((o) => {
        if (o instanceof THREE.Mesh || o instanceof THREE.Line) {
          o.geometry.dispose();
          const materials = Array.isArray(o.material) ? o.material : [o.material];
          materials.forEach(m => m.dispose());
        }
      });
      roughTile.dispose();wallTextures.dispose();
      buildOverlay.dispose();
      planOverview.dispose();
      presentationFloor.geometry.dispose();
      presentationFloor.material.dispose();
      sunlight.shadow.dispose();
      const session = renderer.xr.getSession();
      if (session) void session.end().catch(() => undefined);
      renderer.dispose();
      vrButton.remove();
      renderer.domElement.remove();
    };
  }, [manifest]);

  return <div className={"scene-canvas" + (mode === "draw" || mode === "place" || mode === "resize" ? " is-building" : "")} ref={host}
    aria-label="3D building scene">
    {renderError && <div className="scene-loading" role="alert">{renderError}</div>}
  </div>;
}
