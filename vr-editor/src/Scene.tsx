import { useEffect, useRef, useState } from "react";
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
import { activeStart, buildGuide, newPlacementId, validWallLength } from "./buildPlacement";
import type { BuildAction, BuildHit, BuildSizes, BuildState, WallVisual } from "./buildPlacement";
import { aimBuild, beginDraftGesture, createBuildOverlay, displayCeilingDraft, displayWallDraft, draftGesturePreview } from "./buildScene";
import type { DraftGesture } from "./buildScene";
import { roofEdges } from "./roofComponents";
import { CATALOGUE_DRAG_TYPE, OPENING_DRAG_TYPE, showConstructionItem, showConstructionSurface } from "./constructionStages";
import type { ConstructionStage } from "./constructionStages";
import { getCatalogueItem } from "./itemCatalogue";
import type { ControlMode, HistoryAction } from "./editorControls";
import { createFootprintGizmo, footprintGeometry, projectSourceHost, renderFootprintGeometry } from "./footprintScene";
import { footprintCorner, projectCeiling, projectPlacement, projectWall, resizeFromCorner } from "./footprintResize";
import type { FootprintBounds, FootprintCorner, FootprintProjection } from "./footprintResize";
import { catalogueWallHost, createCatalogueScene, demoCatalogueHosts, draftCatalogueHosts, draftSiteHost } from "./catalogueScene";
import type { CatalogueHost } from "./catalogueScene";
import { buildMenuLayout, EMPTY_ITEM_BROWSER, updateItemBrowser } from "./catalogueMenu";
import type { ItemAction, MenuAction } from "./catalogueMenu";
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
  onToolMessage: (message: string) => void;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  draftState: DraftHistory | null;
  onCycleStudy: (objectId: string) => void;
  mood: LightingMood;
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
      transparent: !trustworthy,
      opacity: trustworthy ? 0.92 : 0.4,
      side: THREE.DoubleSide,
      roughness,
      metalness: 0,
      depthWrite: trustworthy,
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

export function SceneView({ manifest, visibleIds, level, levels, onLevel, mode, canUndo, canRedo, onHistory, onDone, onToolMessage, selectedId, onSelect, draftState, onCycleStudy, mood, quality, detail, inspection, cameraRequest, captureSerial, onCapture, onPcVrSessionReport, moveMode, wallMoveState, onMoveDelta, addedWallSketch, addedWallSketches, buildState, buildLevel, buildSizes, stage, onStage, footprint, onBuildAction, onBuildHint, catalogue, teleportMode, onTeleportMessage }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const interaction = useRef({ visibleIds, level, levels, onLevel, mode, canUndo, canRedo, onHistory, onDone, onToolMessage });
  interaction.current = { visibleIds, level, levels, onLevel, mode, canUndo, canRedo, onHistory, onDone, onToolMessage };
  const [renderError, setRenderError] = useState<string | null>(null);
  const callback = useRef(onSelect);
  callback.current = onSelect;
  const cycleCallback = useRef(onCycleStudy);
  cycleCallback.current = onCycleStudy;
  const teleportSettings = useRef({teleportMode,onTeleportMessage});
  teleportSettings.current = {teleportMode,onTeleportMessage};
  const addedWallRef = useRef(addedWallSketch);
  addedWallRef.current = addedWallSketch;
  const addedWallsRef = useRef(addedWallSketches);
  addedWallsRef.current = addedWallSketches;
  const build = useRef({ buildState, buildLevel, buildSizes, onBuildAction, onBuildHint });
  build.current = { buildState, buildLevel, buildSizes, onBuildAction, onBuildHint };
  const construction = useRef({ stage, onStage });
  construction.current = { stage, onStage };
  const resize = useRef(footprint);
  resize.current = footprint;
  const itemControls = useRef(catalogue);
  itemControls.current = catalogue;
  const moveSettings = useRef({ moveMode, wallMoveState, onMoveDelta });
  moveSettings.current = { moveMode, wallMoveState, onMoveDelta };
  const sessionReportCallback = useRef(onPcVrSessionReport);
  sessionReportCallback.current = onPcVrSessionReport;
  const visualSettings = useRef({ mood, quality, detail, inspection, cameraRequest, captureSerial, onCapture });
  visualSettings.current = { mood, quality, detail, inspection, cameraRequest, captureSerial, onCapture };
  const picked = useRef(selectedId);
  picked.current = selectedId;
  const draftMap = useRef<Map<string, WallDraft>>(new Map());
  draftMap.current = new Map((draftState ? safeDrafts(draftState, manifest) : [])
    .map(d => [d.objectId, d]));

  useEffect(() => {
    const parent = host.current;
    if (!parent) return;

    const scene = new THREE.Scene();
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
    const toolsBusy = () => interaction.current.mode !== "inspect" || itemBrowser.open || stageMenuOpen;
    const sourceVisible = (object: THREE.Object3D) => {
      const id = object.userData.objectId as string | undefined;
      return !id || interaction.current.visibleIds.has(id);
    };
    function pointerContext() {
      return [interaction.current.mode, build.current.buildState.tool, build.current.buildLevel,
        itemControls.current.active?.id, construction.current.stage, interaction.current.visibleIds] as const;
    }
    type PointerContext = ReturnType<typeof pointerContext>;
    const samePointerContext = (expected: PointerContext) =>
      pointerContext().every((value, index) => value === expected[index]);
    const reportTool = (message: string) => interaction.current.onToolMessage(message);
    function menuLayout(hint: string) {
      const { buildState, buildLevel } = build.current;
      const { active, canUndo, turn } = itemControls.current;
      return buildMenuLayout(buildState, buildLevel, itemBrowser, active, canUndo, turn, hint,
        construction.current.stage, stageMenuOpen, {
          available: !!resize.current.box, enabled: resize.current.enabled, changed: !!resize.current.projection,
        }, interaction.current);
    }
    function menuAction(choice: MenuAction) {
      reportTool("");
      if (choice.area === "history") interaction.current.onHistory(choice.action);
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
    const buildOverlay = createBuildOverlay(scene);
    const sceneScope = scopeKey(manifest);
    let lastAddedWall = "";
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
      for (const child of [...wallAdditionLayer.children]) {
        wallAdditionLayer.remove(child);
        child.traverse(item => {
          if (item instanceof THREE.Mesh || item instanceof THREE.Line) {
            item.geometry.dispose();
            const materials = Array.isArray(item.material) ? item.material : [item.material];
            materials.forEach(material => material.dispose());
          }
        });
      }
      for (const wall of active) {
        const group = displayWallDraft(wall);
        group.userData.reviewOnlyWallProposal = true;
        group.userData.proposalId = wall.proposalId;
        wallAdditionLayer.add(group);
        draftItemHosts.push(...draftCatalogueHosts(wall, group));
      }
      for (const ceiling of ceilings) {
        const mesh = displayCeilingDraft(ceiling);
        mesh.userData.surfaceKind = "ceiling";
        wallAdditionLayer.add(mesh);
        draftItemHosts.push({ id: ceilingDraftHostId(ceiling.proposalId), target: "ceiling", mesh, ceilingDraft: ceiling });
      }
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
      return aimBuild(buildState, buildLevel, buildSizes, raycaster.ray);
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
      itemView.sync(visibleHosts, draftItemHosts, renderItems, construction.current.stage);
    }
    function placeSelectedItem(item: CatalogueItem) {
      syncItems();
      const { hit: target, reason } = itemView.candidate(raycaster, item, itemControls.current.turn);
      if (target) itemControls.current.onPlace(item.id, target);
      else reportTool(reason ?? itemGuide(item));
    }
    const select = (id: string | null) => callback.current(id);
    function pick() {
      const hits = raycaster.intersectObjects(pickables.filter(object =>
        sourceVisible(object) && showConstructionSurface(construction.current.stage, object.userData.surfaceKind)), false);
      const hit = hits[0];
      select(typeof hit?.object.userData.objectId === "string"
        ? hit.object.userData.objectId : null);
    }
    const resizePlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.06);
    type ResizeDrag = { box: FootprintBounds; corner: FootprintCorner; at: THREE.Vector3; token: symbol; last?: string };
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
      const [x, z] = footprintCorner(drag.box, drag.corner);
      const next = resizeFromCorner(drag.box, drag.corner, [x + at.x - drag.at.x, z + at.z - drag.at.z]);
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
      return beginDraftGesture(buildState, buildLevel, raycaster.ray);
    }
    function previewDrag(gesture: DraftGesture) {
      const { buildState, buildLevel, buildSizes } = build.current;
      if (buildState.tool !== gesture.mode || buildLevel !== gesture.levelId) return null;
      return draftGesturePreview(gesture, buildSizes, raycaster.ray);
    }
    function completeDrag(gesture: DraftGesture) {
      const preview = previewDrag(gesture);
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
      if (!resize.current.enabled) pick();
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
          !showConstructionItem(construction.current.stage, item)) return;
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
    const xrPress: ({ context: PointerContext; menu: string | null } | null)[] = [null, null];
    function menuKey(layout: ReturnType<typeof menuLayout>) {
      const hit = buildOverlay.menuHit(raycaster, layout);
      return hit ? JSON.stringify(hit.action) : null;
    }
    function beginXrGesture(index: number) {
      aimController(controllers[index]);
      const layout = menuLayout("");
      buildOverlay.sizeMenu(layout);
      const menu = menuKey(layout);
      xrPress[index] = { context: pointerContext(), menu };
      if (itemBrowser.open || stageMenuOpen || menu !== null) return;
      xrResize[index] = startResize();
      if (!xrResize[index]) xrGestures[index] = draftGesture();
    }
    const selectStart0 = () => beginXrGesture(0), selectStart1 = () => beginXrGesture(1);
    const selectEnd = (index: number) => {
      xrGestures[index] = null; xrResize[index] = null; xrPress[index] = null;
    };
    const selectEnd0 = () => selectEnd(0), selectEnd1 = () => selectEnd(1);
    const trigger=(index:number)=>{
      if (!renderer.xr.isPresenting) return;
      lastController = index;
      aimController(controllers[index]);
      const layout = menuLayout("");
      buildOverlay.sizeMenu(layout);
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
      if (gesture && completeDrag(gesture)) return;
      const menuChoice = buildOverlay.menuHit(raycaster, layout);
      if (menuChoice) {
        if (menuChoice.action) menuAction(menuChoice.action);
        return;
      }
      if (itemBrowser.open || stageMenuOpen || resize.current.enabled) return;
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
        pick();return;
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
        const offset=new XRRigidTransform(
          {x,y:0,z},{x:0,y:0,z:0,w:1},
        );
        renderer.xr.setReferenceSpace(space.getOffsetReferenceSpace(offset));
        teleportSettings.current.onTeleportMessage(
          `Moved ${(target.distanceM??0).toFixed(1)}m on verified floor (review navigation only)`,
        );
      } catch {
        teleportSettings.current.onTeleportMessage(
          "SteamVR declined the teleport reference-space change.",
        );
      }
    };
    const select0 = () => trigger(0);
    const select1 = () => trigger(1);
    // SteamVR presents Sony Sense controllers as standard XR input sources.
    // Do not rely on a proprietary profile name or guessed Sony button IDs:
    // WebXR 'select' aims with the trigger, 'squeeze' invokes the grip action.
    // Some OpenXR/browser combinations omit squeeze events, so xr-standard
    // Gamepad button #1 is an opt-in semantic fallback (one action per release).
    const inputSources: (PcVrInputSource | null)[] = [null, null];
    const squeezeTracker = new PcVrSqueezeTracker();
    const report = (presenting = renderer.xr.isPresenting) => {
      const controllerInfos = inputSources.map(inspectPcVrController)
        .filter((item): item is PcVrControllerInfo => item !== null);
      sessionReportCallback.current({presenting, controllers: controllerInfos});
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
      if (interaction.current.mode !== "wall-move" || itemBrowser.open || stageMenuOpen || activeGrip) return;
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
      if (interaction.current.mode !== "wall-move" || itemBrowser.open || stageMenuOpen) return;
      const p=controllers[index].getWorldPosition(new THREE.Vector3());
      const dx=p.x-held.from.x,dz=p.z-held.from.z;
      if (Number.isFinite(dx)&&Number.isFinite(dz))
        moveSettings.current.onMoveDelta(held.objectId,dx,dz);
    };
    const nativeStart0 = () => {
      squeezeTracker.onNativeStart("0");
      nativeGripSeen[0] = true;
      beginGrip(0);
    };
    const nativeStart1 = () => {
      squeezeTracker.onNativeStart("1");
      nativeGripSeen[1] = true;
      beginGrip(1);
    };
    const nativeEnd0 = () => endGrip(0), nativeEnd1 = () => endGrip(1);
    const squeeze0 = () => {
      if (squeezeTracker.onNativeSqueeze("0") && moveSettings.current.moveMode !== "move")
        applyFinishSqueeze();
    };
    const squeeze1 = () => {
      if (squeezeTracker.onNativeSqueeze("1") && moveSettings.current.moveMode !== "move")
        applyFinishSqueeze();
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
      report();
    };
    const connected0 = (event: unknown) => connected(event, 0);
    const connected1 = (event: unknown) => connected(event, 1);
    const disconnected0 = () => disconnect(0);
    const disconnected1 = () => disconnect(1);
    const onSessionStart = () => {
      cancelPointer();
      lastController = -1;
      squeezeTracker.clear();
      nativeGripSeen.fill(false);
      fallbackGripDown.fill(false);
      activeGrip=null;
      report(true);
    };
    const onSessionEnd = () => {
      buildOverlay.hideMenu();
      itemBrowser = EMPTY_ITEM_BROWSER;
      stageMenuOpen = false;
      xrGestures.fill(null);
      xrResize.fill(null);
      xrPress.fill(null);
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
    let lastLabelId: string | null = null;
    let lastMood: LightingMood | null = null;
    let lastQuality: RenderQuality | null = null;
    let lastDetail: SurfaceDetail | null = null;
    let lastCameraSerial: number | null = null;
    let lastCaptureSerial = visualSettings.current.captureSerial;
    let disposed = false;
    renderer.setAnimationLoop(() => {
      const { mood: activeMood, quality: activeQuality, detail: activeDetail,
        inspection: activeInspection, cameraRequest: requestedCamera } = visualSettings.current;
      // Fallback xr-standard grips when SteamVR omits native squeeze events.
      // Native grip events always take precedence. Neither path changes source.
      const { buildState, buildLevel } = build.current;
      if (interaction.current.mode !== "wall-move" || itemBrowser.open || stageMenuOpen) activeGrip=null;
      if (renderer.xr.isPresenting) {
        for (let index=0;index<inputSources.length;index++) {
          const pressed=standardSqueezePressed(inputSources[index]);
          if (moveSettings.current.moveMode === "move" &&
              !nativeGripSeen[index] && pressed !== null) {
            if (pressed && !fallbackGripDown[index]) beginGrip(index);
            if (!pressed && fallbackGripDown[index]) endGrip(index);
            fallbackGripDown[index] = pressed;
          }
          if (squeezeTracker.poll(String(index),pressed) &&
              moveSettings.current.moveMode !== "move") applyFinishSqueeze();
        }
      }
      const activeMoves = moveSettings.current.wallMoveState
        ? safeWallMoves(moveSettings.current.wallMoveState, manifest) : [];
      let dragX=0,dragZ=0;
      if (activeGrip && moveSettings.current.moveMode === "move") {
        const p=controllers[activeGrip.index].getWorldPosition(new THREE.Vector3());
        dragX=p.x-activeGrip.from.x;dragZ=p.z-activeGrip.from.z;
      }
      for (const obj of pickables) {
        const id=obj.userData.objectId as string|undefined;
        const move=activeMoves.find(m=>m.objectId===id);
        const held=activeGrip?.objectId===id;
        const dx=(move?.dx??0)+(held?dragX:0);
        const dz=(move?.dz??0)+(held?dragZ:0);
        if (Number.isFinite(dx)&&Number.isFinite(dz))
          obj.position.set(dx * (resize.current.projection?.scaleX ?? 1), 0, dz * (resize.current.projection?.scaleZ ?? 1));
      }
      if (startPointer && !samePointerContext(startPointer.context)) cancelPointer();
      syncItems();
      gizmo.show(resize.current.enabled ? resize.current.box : null);
      if (startPointer?.resize && hoveringCanvas && !renderer.xr.isPresenting) {
        raycaster.setFromCamera(mouse, camera);
        resizeDrag(startPointer.resize);
      }
      const currentStage = construction.current.stage;
      const framing = currentStage === "framing" || currentStage === "rough-in";
      for (const obj of pickables) {
        const kind = obj.userData.surfaceKind;
        const displayed = sourceVisible(obj);
        const visible = showConstructionSurface(currentStage, kind);
        if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshStandardMaterial) {
          obj.visible = displayed;
          obj.material.visible = visible;
          obj.material.wireframe = !kind && framing;
          if (kind === "roof") obj.castShadow = visible;
        } else obj.visible = displayed && visible;
      }
      for (const shape of wallAdditionLayer.children) {
        shape.visible = currentStage !== "slab";
        if (shape instanceof THREE.Mesh && shape.material instanceof THREE.MeshBasicMaterial) {
          shape.material.visible = showConstructionSurface(currentStage, "ceiling");
        } else {
          for (const child of shape.children) {
            if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshBasicMaterial)
              child.material.visible = !framing;
          }
        }
      }
      const origin = activeStart(buildState, buildLevel);
      const item = itemControls.current.active;
      const prompt = resize.current.enabled ? resize.current.hint || "Point at a footprint corner and hold the trigger to drag." :
        item ? itemGuide(item) : buildGuide(buildState, buildLevel);
      if (renderer.xr.isPresenting) {
        buildOverlay.positionMenu(renderer.xr.getCamera());
        const layout = menuLayout(prompt);
        buildOverlay.sizeMenu(layout);
        const isPointer = (source: PcVrInputSource | null | undefined) => source?.targetRayMode === "tracked-pointer";
        const favoured = isPointer(inputSources[lastController]) ? lastController :
          inputSources.findIndex(source => isPointer(source) && source?.handedness === "right");
        const active = favoured >= 0 ? favoured : inputSources.findIndex(isPointer);
        if (active >= 0) aimController(controllers[active]);
        const hover = active >= 0 ? buildOverlay.menuHit(raycaster, layout) : null;
        const heldResize = xrResize.findIndex(drag => drag !== null);
        if (heldResize >= 0 && xrPress[heldResize] && samePointerContext(xrPress[heldResize]!.context)) {
          aimController(controllers[heldResize]);
          resizeDrag(xrResize[heldResize]!);
        }
        const held = xrGestures.findIndex(gesture => gesture !== null);
        if (held >= 0) aimController(controllers[held]);
        const ready = active >= 0 && !hover && !itemBrowser.open && !stageMenuOpen && !resize.current.enabled;
        const itemPick = ready && item ? itemView.candidate(raycaster, item, itemControls.current.turn) : null;
        const drag = held >= 0 && xrPress[held] && samePointerContext(xrPress[held]!.context) ? xrGestures[held] : null;
        const buildTarget = drag ? previewDrag(drag)?.aim ?? null : ready && !item ? aim() : null;
        itemView.aim(itemPick?.hit ?? null);
        buildOverlay.showAim(buildTarget, item || itemBrowser.open ? null : origin);
        if (!itemBrowser.open && !stageMenuOpen) layout.note = itemPick?.hit ? "Pull the trigger to place." :
          itemPick?.reason ?? buildTarget?.hint ?? prompt;
        buildOverlay.drawMenu(layout, hover?.index ?? -1);
      } else {
        const drag = startPointer?.gesture;
        const canAim = !!(buildState.tool || item) && hoveringCanvas && (!startPointer || !!drag);
        if (canAim) raycaster.setFromCamera(mouse, camera);
        const itemPick = canAim && item ? itemView.candidate(raycaster, item, itemControls.current.turn) : null;
        const buildTarget = canAim && !item ? drag ? previewDrag(drag)?.aim ?? null : aim() : null;
        itemView.aim(itemPick?.hit ?? null);
        buildOverlay.showAim(buildTarget, item ? null : origin);
        setBuildHint(item ? (itemPick?.hit ? "Click to place " + item.label + "." :
          itemPick?.reason ?? itemGuide(item)) : buildTarget?.hint ?? "");
      }
      // Aiming at source-backed floor is visible only in immersive VR.
      // Never display this marker over an invented presentation floor.
      teleportMarker.visible=false;
      if(renderer.xr.isPresenting && interaction.current.mode === "teleport" &&
          !itemBrowser.open && !stageMenuOpen && teleportSettings.current.teleportMode) {
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
      sunlight.castShadow = activeInspection.showShadows;
      presentationFloor.visible = activeInspection.showShadows;
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
      if (lastQuality !== activeQuality) {
        const size = shadowMapSize(activeQuality);
        sunlight.shadow.mapSize.set(size, size);
        if (sunlight.shadow.map) {
          sunlight.shadow.map.dispose();
          sunlight.shadow.map = null;
        }
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1,
          maxRenderPixelRatio(activeQuality, renderer.xr.isPresenting)));
        onResize();
        lastQuality = activeQuality;
      }
      if (requestedCamera.serial !== lastCameraSerial && !renderer.xr.isPresenting) {
        const focus = requestedCamera.focus === "selected" ?
          pickables.find(obj => sourceVisible(obj) && obj.userData.objectId === picked.current) : null;
        const bounds = new THREE.Box3();
        const displayed = pickables.filter(object => sourceVisible(object) &&
          showConstructionSurface(currentStage, object.userData.surfaceKind));
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
      for (const item of pickables) {
        if (!(item instanceof THREE.Mesh) || !(item.material instanceof THREE.MeshStandardMaterial)) continue;
        const id = item.userData.objectId as string;
        const row = sourceById.get(id);
        if (!row) continue;
        const draft = draftMap.current.get(id);
        const swatch = studyColor(row, draft?.swatch ? { objectId: id, swatch: draft.swatch } : null);
        const originalHeight = item.userData.originalHeight as number | undefined;
        const ghostHeight = draft?.heightM;
        const moved=activeMoves.some(m=>m.objectId===id) ||
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
        item.material.emissive.setHex(selected ? 0x173b36 : 0x000000);
        item.material.emissiveIntensity = selected ? 0.32 : 0;
        if (originalHeight !== undefined) {
          const height=activeInspection.showGhosts && ghostHeight !== null &&
            ghostHeight !== undefined ? ghostHeight : originalHeight;
          const position = item.geometry.getAttribute("position");
          if (position instanceof THREE.BufferAttribute && position.getY(2) !== height) {
            // Triangle vertices 2, 4 and 5 are the upper face vertices.
            position.setY(2, height); position.setY(4, height); position.setY(5, height);
            position.needsUpdate = true;
            item.geometry.computeVertexNormals();
          }
        }
      }
      const labelVisible = picked.current && pickables.some(object => sourceVisible(object) && object.userData.objectId === picked.current &&
        showConstructionSurface(currentStage, object.userData.surfaceKind));
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
      controls.update();
      renderer.render(scene, camera);
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
      itemView.clear();
      scene.traverse((o) => {
        if (o instanceof THREE.Mesh || o instanceof THREE.Line) {
          o.geometry.dispose();
          const materials = Array.isArray(o.material) ? o.material : [o.material];
          materials.forEach(m => m.dispose());
        }
      });
      roughTile.dispose();
      buildOverlay.dispose();
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
