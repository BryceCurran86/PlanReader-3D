import * as THREE from "three";
import {
  activeStart, aimOpening, BUILD_TOOLS, buildGuide, MAX_DRAFT_WALLS, nearWall,
  openingFits, planLength, projectOnWall, snappedPoint, validWallLength,
} from "./buildPlacement.ts";
import type { BuildAction, BuildHit, BuildSizes, BuildState, PlanPoint, PlacedWall, WallVisual } from "./buildPlacement.ts";
import type { WallAdditionOpening } from "./wallAdditionProtocol.ts";

function atOffset(wall: WallVisual, offset: number, height: number): THREE.Vector3 {
  const t = offset / planLength(wall.start, wall.end);
  return new THREE.Vector3(
    THREE.MathUtils.lerp(wall.start[0], wall.end[0], t), height,
    THREE.MathUtils.lerp(wall.start[1], wall.end[1], t),
  );
}

function openingOutline(wall: WallVisual, opening: WallAdditionOpening) {
  const a = opening.offsetM, b = a + opening.widthM;
  const bottom = opening.sillHeightM, top = bottom + opening.heightM;
  return [atOffset(wall, a, bottom), atOffset(wall, a, top),
    atOffset(wall, b, top), atOffset(wall, b, bottom)];
}

export function displayWallDraft(wall: WallVisual) {
  const group = new THREE.Group();
  const faces: number[] = [];
  const leaves: number[] = [];
  function panel(points: THREE.Vector3[], vertices: number[]) {
    for (const index of [0, 1, 2, 0, 2, 3]) vertices.push(...points[index].toArray());
  }
  function surface(from: number, to: number, bottom: number, top: number) {
    if (to <= from || top <= bottom) return;
    panel([atOffset(wall, from, bottom), atOffset(wall, from, top),
      atOffset(wall, to, top), atOffset(wall, to, bottom)], faces);
  }
  function addMesh(vertices: number[], color: number, opacity: number) {
    if (!vertices.length) return;
    const geometry = new THREE.BufferGeometry().setAttribute("position",
      new THREE.Float32BufferAttribute(vertices, 3));
    group.add(new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
      color, side: THREE.DoubleSide, transparent: true, opacity, depthWrite: false,
    })));
  }
  const openings = (wall.openings ?? []).filter(opening => openingFits(wall, opening))
    .sort((a, b) => a.offsetM - b.offsetM);
  let right = 0;
  for (const opening of openings) {
    if (opening.offsetM < right - 0.000001) continue;
    surface(right, opening.offsetM, 0, wall.heightM);
    right = opening.offsetM + opening.widthM;
    surface(opening.offsetM, right, 0, opening.sillHeightM);
    surface(opening.offsetM, right, opening.sillHeightM + opening.heightM, wall.heightM);
    const points = openingOutline(wall, opening);
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),
      new THREE.LineBasicMaterial({ color: 0xf5d9ad })));
    if (opening.openingKind === "door") panel(points, leaves);
  }
  surface(right, planLength(wall.start, wall.end), 0, wall.heightM);
  addMesh(faces, 0xa589e4, 0.48);
  addMesh(leaves, 0xe9bb75, 0.55);
  // A floor-level guide keeps draft walls visible and selectable from Top view.
  group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    atOffset(wall, 0, 0.018), atOffset(wall, planLength(wall.start, wall.end), 0.018),
  ]), new THREE.LineBasicMaterial({ color: 0xa589e4 })));
  return group;
}

const PLAN = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
type Aim = { hit: BuildHit | null; marker?: PlanPoint; line?: THREE.Vector3[]; valid?: boolean; hint: string };

function openingHost(walls: PlacedWall[], ray: THREE.Ray, floor: THREE.Vector3 | null) {
  type HostHit = { wall: PlacedWall; point: PlanPoint; distance: number };
  let direct: HostHit | null = null;
  let fromAbove: HostHit | null = null;
  for (const wall of walls) {
    const normal = new THREE.Vector3(wall.end[1] - wall.start[1], 0, wall.start[0] - wall.end[0]).normalize();
    const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(normal,
      new THREE.Vector3(wall.start[0], 0, wall.start[1]));
    const target = ray.intersectPlane(plane, new THREE.Vector3());
    if (target && target.y >= 0 && target.y <= wall.heightM) {
      const point: PlanPoint = [target.x, target.z];
      const { offset, length } = projectOnWall(wall, point);
      const distance = ray.origin.distanceToSquared(target);
      if (offset >= 0 && offset <= length && (!direct || distance < direct.distance)) {
        direct = { wall, point, distance };
      }
    }
    if (floor) {
      const point: PlanPoint = [floor.x, floor.z];
      const projection = projectOnWall(wall, point);
      if (nearWall(projection) && (!fromAbove || projection.distance < fromAbove.distance)) {
        fromAbove = { wall, point, distance: projection.distance };
      }
    }
  }
  return direct ?? fromAbove;
}

export function aimBuild(state: BuildState, levelId: string | null, sizes: BuildSizes, ray: THREE.Ray): Aim {
  const guide = buildGuide(state, levelId);
  if (!state.tool || !levelId) return { hit: null, hint: guide };
  const floor = ray.intersectPlane(PLAN, new THREE.Vector3());
  if (state.tool === "wall") {
    if (state.walls.length >= MAX_DRAFT_WALLS) return { hit: null, hint: guide };
    const point = floor && snappedPoint([floor.x, floor.z]);
    if (!point) return { hit: null, hint: "Aim at the plan to place a wall point." };
    const hit: BuildHit = { kind: "wall", levelId, point };
    const start = activeStart(state, levelId);
    if (!start) return { hit, marker: point, hint: guide };
    const length = planLength(start, point);
    const valid = validWallLength(length);
    return {
      hit: valid ? hit : null, marker: point, valid,
      line: [new THREE.Vector3(start[0], 0.025, start[1]), new THREE.Vector3(point[0], 0.025, point[1])],
      hint: valid ? "Place wall end · " + length.toFixed(2) + " m" : "Wall length must be 50 mm to 200 m.",
    };
  }
  const host = openingHost(state.walls.filter(wall => wall.levelId === levelId), ray, floor);
  const result = host && aimOpening(host.wall, host.point, state.tool, sizes);
  if (!host || !result) return { hit: null, hint: guide };
  if (result.error) return { hit: null, hint: result.error };
  const label = state.tool === "door" ? "door" : "frame";
  return {
    hit: { kind: "opening", levelId, proposalId: host.wall.proposalId, point: host.point },
    line: openingOutline(host.wall, result.opening), valid: true,
    hint: "Place " + label + " · " + Math.round(sizes.widthM * 1000) + " × " + Math.round(sizes.heightM * 1000) + " mm",
  };
}

const MENU_WIDTH = 840, MENU_HEIGHT = 240;
const MENU_ACTIONS = [
  ...BUILD_TOOLS.map(({ id, label }) => ({ label, action: { kind: "tool", tool: id } as const })),
  { label: "Undo", action: { kind: "undo" } as const },
  { label: "Done", action: { kind: "done" } as const },
];

function enabled(action: BuildAction, state: BuildState, levelId: string | null) {
  if (action.kind === "tool") return !!levelId;
  if (action.kind === "undo") return !!state.history.length || !!activeStart(state, levelId);
  return !!state.tool;
}

export function createBuildOverlay(scene: THREE.Scene) {
  const canvas = document.createElement("canvas");
  canvas.width = MENU_WIDTH;
  canvas.height = MENU_HEIGHT;
  const context = canvas.getContext("2d");
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const menu = new THREE.Mesh(new THREE.PlaneGeometry(0.85, 0.243),
    new THREE.MeshBasicMaterial({ map: texture, toneMapped: false, depthTest: false, depthWrite: false }));
  menu.renderOrder = 20;
  menu.visible = false;
  scene.add(menu);
  const mark = new THREE.Mesh(new THREE.RingGeometry(0.037, 0.057, 24),
    new THREE.MeshBasicMaterial({ color: 0x71f7dc, side: THREE.DoubleSide }));
  mark.rotation.x = -Math.PI / 2;
  mark.visible = false;
  scene.add(mark);
  const positions = new THREE.Float32BufferAttribute(new Float32Array(12), 3);
  const geometry = new THREE.BufferGeometry().setAttribute("position", positions);
  const outline = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: 0x71f7dc }));
  outline.frustumCulled = false;
  outline.visible = false;
  scene.add(outline);

  const previousHead = new THREE.Vector3();
  const previousFacing = new THREE.Vector3();
  const head = new THREE.Vector3();
  const facing = new THREE.Vector3();
  const right = new THREE.Vector3();
  let drawn = "";
  function positionMenu(camera: THREE.Camera) {
    camera.getWorldPosition(head);
    camera.getWorldDirection(facing);
    facing.y = 0;
    if (facing.lengthSq() < 0.01) return;
    facing.normalize();
    if (menu.visible && previousHead.distanceToSquared(head) <= 0.36 && previousFacing.dot(facing) > 0.75) return;
    previousHead.copy(head);
    previousFacing.copy(facing);
    right.set(-facing.z, 0, facing.x);
    menu.position.copy(head).addScaledVector(facing, 1.3).addScaledVector(right, 0.32);
    menu.position.y -= 0.38;
    menu.lookAt(head);
    menu.updateMatrixWorld();
    menu.visible = true;
  }
  function menuHit(raycaster: THREE.Raycaster, state: BuildState, levelId: string | null) {
    const uv = menu.visible ? raycaster.intersectObject(menu, false)[0]?.uv : undefined;
    if (!uv) return null;
    const x = uv.x * MENU_WIDTH, y = (1 - uv.y) * MENU_HEIGHT;
    const index = Math.floor((x - 20) / 160);
    const button = x >= 20 && y >= 67 && y <= 142 && (x - 20) % 160 <= 147
      ? MENU_ACTIONS[index] : undefined;
    const action = button && enabled(button.action, state, levelId) ? button.action : null;
    return { action, index: action ? index : -1 };
  }
  function drawMenu(state: BuildState, levelId: string | null, hint: string, hover: number) {
    const key = JSON.stringify([state.tool, levelId, !!state.history.length, !!activeStart(state, levelId), hint, hover]);
    if (!context || drawn === key) return;
    drawn = key;
    context.fillStyle = "#13242c";
    context.fillRect(0, 0, MENU_WIDTH, MENU_HEIGHT);
    context.font = "bold 32px sans-serif";
    context.fillStyle = "#f0fbfc";
    context.fillText("Build tools", 20, 44);
    for (const [index, button] of MENU_ACTIONS.entries()) {
      const disabled = !enabled(button.action, state, levelId);
      const selected = button.action.kind === "tool" && button.action.tool === state.tool;
      const x = 20 + index * 160;
      context.fillStyle = index === hover || selected ? "#69dbca" : "#2a4651";
      context.fillRect(x, 67, 147, 75);
      context.fillStyle = index === hover || selected ? "#102421" : disabled ? "#a1aeb4" : "#fff";
      context.font = "bold 30px sans-serif";
      context.textAlign = "center";
      context.fillText(button.label, x + 73.5, 115);
      context.textAlign = "left";
    }
    context.fillStyle = "#edf9fc";
    context.font = "28px sans-serif";
    context.fillText(hint, 20, 199, 800);
    texture.needsUpdate = true;
  }
  function showAim(aim: Aim | null, origin: PlanPoint | null) {
    const marker = aim?.marker ?? origin;
    mark.visible = !!marker;
    if (marker) {
      mark.position.set(marker[0], 0.027, marker[1]);
      mark.material.color.setHex(aim?.valid === false ? 0xffab78 : 0x71f7dc);
    }
    outline.visible = !!aim?.line;
    if (aim?.line) {
      aim.line.forEach((point, i) => positions.setXYZ(i, point.x, point.y, point.z));
      positions.needsUpdate = true;
      geometry.setDrawRange(0, aim.line.length);
      outline.material.color.setHex(aim.valid === false ? 0xffab78 : 0x71f7dc);
    }
  }
  return { positionMenu, menuHit, drawMenu, showAim,
    hideMenu: () => { menu.visible = false; },
    dispose: () => texture.dispose() };
}
