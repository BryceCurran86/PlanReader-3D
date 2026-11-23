import * as THREE from "three";
import {
  activeStart, aimOpening, buildGuide, MAX_DRAFT_WALLS, nearWall,
  openingFits, planLength, projectOnWall, snappedPoint, validWallLength,
  draftShape, validCeiling, validEditedWall,
} from "./buildPlacement.ts";
import type { BuildAction, BuildHit, BuildSizes, BuildState, CeilingDraft, PlanPoint, PlacedWall, WallVisual } from "./buildPlacement.ts";
import type { WallAdditionOpening } from "./wallAdditionProtocol.ts";
import type { MenuLayout } from "./catalogueMenu";

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
  function panel(points: THREE.Vector3[], vertices: number[]) {
    for (const index of [0, 1, 2, 0, 2, 3]) vertices.push(...points[index].toArray());
  }
  function surface(from: number, to: number, bottom: number, top: number) {
    if (to <= from || top <= bottom) return;
    panel([atOffset(wall, from, bottom), atOffset(wall, from, top),
      atOffset(wall, to, top), atOffset(wall, to, bottom)], faces);
  }
  function addMesh(vertices: number[], color: number, opacity: number, wallFace = false, doorId?: string) {
    if (!vertices.length) return;
    const geometry = new THREE.BufferGeometry().setAttribute("position",
      new THREE.Float32BufferAttribute(vertices, 3));
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
      color, side: THREE.DoubleSide, transparent: true, opacity, depthWrite: false,
    }));
    mesh.userData.catalogueWallFace = wallFace;
    if (doorId) mesh.userData.catalogueDoorLeaf = doorId;
    group.add(mesh);
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
    if (opening.openingKind === "door") {
      const leaf: number[] = [];
      panel(points, leaf);
      addMesh(leaf, 0xe9bb75, 0.55, false, opening.openingId);
    }
  }
  surface(right, planLength(wall.start, wall.end), 0, wall.heightM);
  addMesh(faces, 0xa589e4, 0.48, true);
  // A floor-level guide keeps draft walls visible and selectable from Top view.
  const outline = new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    atOffset(wall, 0, 0.018), atOffset(wall, 0, wall.heightM),
    atOffset(wall, planLength(wall.start, wall.end), wall.heightM),
    atOffset(wall, planLength(wall.start, wall.end), 0.018), atOffset(wall, 0, 0.018),
  ]), new THREE.LineBasicMaterial({ color: 0xa589e4 }));
  group.add(outline);
  return group;
}

const PLAN = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
type Aim = { hit: BuildHit | null; marker?: PlanPoint; line?: THREE.Vector3[]; valid?: boolean; hint: string };

function rectangle(start: PlanPoint, end: PlanPoint, height: number) {
  const [left, right] = [Math.min(start[0], end[0]), Math.max(start[0], end[0])];
  const [front, back] = [Math.min(start[1], end[1]), Math.max(start[1], end[1])];
  return [[left, front], [right, front], [right, back], [left, back]]
    .map(([x, z]) => new THREE.Vector3(x, height, z));
}

export function displayCeilingDraft(draft: CeilingDraft) {
  const corners = rectangle(draft.start, draft.end, draft.heightM);
  const geometry = new THREE.BufferGeometry().setFromPoints([corners[0], corners[1], corners[2],
    corners[0], corners[2], corners[3]]);
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: 0x9589df,
    side: THREE.DoubleSide, transparent: true, opacity: 0.35, depthWrite: false }));
  return mesh;
}

type DragDraw = { mode: "wall" | "ceiling"; from: PlanPoint };
type DragEdit = { mode: "move" | "stretch"; from: PlanPoint; anchor: PlanPoint; stretchStart?: boolean };
export type DraftGesture = (DragDraw | (DragEdit & (
  { kind: "wall"; previous: PlacedWall } | { kind: "ceiling"; previous: CeilingDraft }
))) & { levelId: string };

function planPoint(ray: THREE.Ray) {
  const floor = ray.intersectPlane(PLAN, new THREE.Vector3());
  return floor && snappedPoint([floor.x, floor.z]);
}

function ceilingHost(ceilings: CeilingDraft[], ray: THREE.Ray, levelId: string) {
  let closest: { ceiling: CeilingDraft; hit: THREE.Vector3; distance: number } | null = null;
  for (const ceiling of ceilings) {
    if (ceiling.levelId !== levelId) continue;
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -ceiling.heightM);
    const hit = ray.intersectPlane(plane, new THREE.Vector3());
    if (!hit) continue;
    const points = rectangle(ceiling.start, ceiling.end, ceiling.heightM);
    if (hit.x < points[0].x - .2 || hit.x > points[2].x + .2 ||
        hit.z < points[0].z - .2 || hit.z > points[2].z + .2) continue;
    const distance = ray.origin.distanceToSquared(hit);
    if (!closest || closest.distance > distance) closest = { ceiling, hit, distance };
  }
  return closest;
}

export function beginDraftGesture(state: BuildState, levelId: string | null, ray: THREE.Ray): DraftGesture | null {
  const from = planPoint(ray);
  if (!from || !levelId || !state.tool) return null;
  const mode = state.tool;
  if (mode === "wall" || mode === "ceiling") {
    return activeStart(state, levelId) ? null : { mode, from, levelId };
  }
  if (mode !== "move" && mode !== "stretch") return null;
  const floor = new THREE.Vector3(from[0], 0, from[1]);
  const wall = openingHost(state.walls.filter(draft => draft.levelId === levelId), ray, floor);
  const ceiling = ceilingHost(state.ceilings, ray, levelId);
  const nearestWall = wall && (mode === "move" || Math.min(
    planLength(wall.wall.start, wall.point), planLength(wall.wall.end, wall.point)) < .4);
  const nearestCeiling = ceiling && rectangle(ceiling.ceiling.start, ceiling.ceiling.end, ceiling.ceiling.heightM)
    .map((point, index) => ({ point, index, distance: point.distanceToSquared(ceiling.hit) }))
    .sort((a, b) => a.distance - b.distance)[0];
  const ceilingHit = ceiling && nearestCeiling && (mode === "move" || nearestCeiling.distance < .16);
  if (wall && nearestWall && (!ceiling || !ceilingHit || wall.distance <= ceiling.distance)) {
    const { start, end } = wall.wall;
    const stretchStart = planLength(start, wall.point) < planLength(end, wall.point);
    return { kind: "wall", mode, from, levelId, previous: wall.wall,
      anchor: stretchStart ? end : start, stretchStart };
  }
  if (ceiling && nearestCeiling && ceilingHit) {
    const fixed = rectangle(ceiling.ceiling.start, ceiling.ceiling.end, ceiling.ceiling.heightM)[(nearestCeiling.index + 2) % 4];
    return { kind: "ceiling", mode, from, levelId, previous: ceiling.ceiling, anchor: [fixed.x, fixed.z] };
  }
  return null;
}

export function draftGesturePreview(gesture: DraftGesture, sizes: BuildSizes, ray: THREE.Ray) {
  const current = planPoint(ray);
  if (!current) return null;
  const delta = planLength(gesture.from, current);
  if (delta < 0.045) return null;
  let line: THREE.Vector3[], valid: boolean, action: BuildAction;
  const to = current;
  if (!("previous" in gesture)) {
    const { from, levelId, mode } = gesture;
    if (mode === "wall") {
      valid = validWallLength(planLength(from, to));
      line = [new THREE.Vector3(from[0], 0.025, from[1]), new THREE.Vector3(to[0], 0.025, to[1])];
    } else {
      valid = validCeiling(from, to);
      line = rectangle(from, to, sizes.ceilingHeightM ?? sizes.wallHeightM);
      line.push(line[0]);
    }
    action = { kind: "drag", levelId, from, to, id: "" };
  } else if (gesture.kind === "wall") {
    const { previous, mode, from, anchor, stretchStart } = gesture;
    const moving = stretchStart ? previous.start : previous.end;
    const target = snappedPoint([moving[0] + to[0] - from[0], moving[1] + to[1] - from[1]]);
    if (!target) return null;
    const shape = mode === "stretch" && stretchStart
      ? { ...previous, start: target, end: anchor }
      : draftShape(previous, mode, from, mode === "stretch" ? target : to, anchor);
    if (!shape) return null;
    valid = validEditedWall(shape);
    line = [new THREE.Vector3(shape.start[0], shape.heightM, shape.start[1]),
      new THREE.Vector3(shape.end[0], shape.heightM, shape.end[1])];
    action = { kind: "adjust", previous, wall: shape };
  } else {
    const { previous, mode, from, anchor } = gesture;
    const corner: PlanPoint = [anchor[0] === Math.min(previous.start[0], previous.end[0])
      ? Math.max(previous.start[0], previous.end[0]) : Math.min(previous.start[0], previous.end[0]),
    anchor[1] === Math.min(previous.start[1], previous.end[1])
      ? Math.max(previous.start[1], previous.end[1]) : Math.min(previous.start[1], previous.end[1])];
    const target: PlanPoint = [corner[0] + to[0] - from[0], corner[1] + to[1] - from[1]];
    const shape = draftShape(previous, mode, from, mode === "stretch" ? target : to, anchor);
    if (!shape) return null;
    valid = validCeiling(shape.start, shape.end);
    line = rectangle(shape.start, shape.end, shape.heightM);
    line.push(line[0]);
    action = { kind: "adjust-ceiling", previous, ceiling: shape };
  }
  const hint = valid ? "Release to apply to the draft." : "Size is invalid or an opening would no longer fit.";
  const aim: Aim = { hit: null, valid, line, hint };
  return { action: valid ? action : null, aim };
}

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
  if (state.tool === "move" || state.tool === "stretch") {
    const edit = beginDraftGesture(state, levelId, ray);
    if (!edit || !("previous" in edit)) return { hit: null, hint: guide };
    const { previous } = edit;
    const marker = state.tool === "move" ? edit.from : edit.kind === "wall" ?
      edit.stretchStart ? previous.start : previous.end : undefined;
    return { hit: null, marker, hint: guide };
  }
  if (state.tool === "wall" || state.tool === "ceiling") {
    const ceiling = state.tool === "ceiling";
    if ((ceiling ? state.ceilings : state.walls).length >= MAX_DRAFT_WALLS) return { hit: null, hint: guide };
    const point = floor && snappedPoint([floor.x, floor.z]);
    if (!point) return { hit: null, hint: "Aim at the plan to place a point." };
    const hit: BuildHit = { kind: state.tool, levelId, point };
    const start = activeStart(state, levelId);
    if (!start) return { hit, marker: point, hint: guide };
    if (ceiling) {
      const valid = validCeiling(start, point);
      const line = rectangle(start, point, sizes.ceilingHeightM ?? sizes.wallHeightM);
      return { hit: valid ? hit : null, marker: point, valid, line: [...line, line[0]], hint: guide };
    }
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
  const label = state.tool;
  return {
    hit: { kind: "opening", levelId, proposalId: host.wall.proposalId, point: host.point },
    line: openingOutline(host.wall, result.opening), valid: true,
    hint: "Place " + label + " · " + Math.round(result.opening.widthM * 1000) + " × " + Math.round(result.opening.heightM * 1000) + " mm",
  };
}

export function createBuildOverlay(scene: THREE.Scene) {
  const canvas = document.createElement("canvas");
  canvas.width = 980;
  canvas.height = 228;
  const context = canvas.getContext("2d");
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const menu = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
    new THREE.MeshBasicMaterial({ map: texture, toneMapped: false, depthTest: false, depthWrite: false }));
  menu.renderOrder = 20;
  menu.visible = false;
  scene.add(menu);
  const mark = new THREE.Mesh(new THREE.RingGeometry(0.037, 0.057, 24),
    new THREE.MeshBasicMaterial({ color: 0x71f7dc, side: THREE.DoubleSide }));
  mark.rotation.x = -Math.PI / 2;
  mark.visible = false;
  scene.add(mark);
  const positions = new THREE.Float32BufferAttribute(new Float32Array(15), 3);
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
  function sizeMenu(layout: MenuLayout) {
    const width = layout.width / 1030, height = layout.height / 1030;
    if (menu.scale.x !== width || menu.scale.y !== height) {
      menu.scale.set(width, height, 1);
      menu.updateMatrixWorld();
    }
  }
  function menuHit(raycaster: THREE.Raycaster, layout: MenuLayout) {
    const uv = menu.visible ? raycaster.intersectObject(menu, false)[0]?.uv : undefined;
    if (!uv) return null;
    const x = uv.x * layout.width, y = (1 - uv.y) * layout.height;
    const index = layout.buttons.findIndex(button => !button.disabled &&
      x >= button.x && x <= button.x + button.w && y >= button.y && y <= button.y + button.h);
    return { action: layout.buttons[index]?.action ?? null, index };
  }
  function drawMenu(layout: MenuLayout, hover: number) {
    const key = JSON.stringify([layout, hover]);
    if (!context || drawn === key) return;
    drawn = key;
    if (canvas.width !== layout.width || canvas.height !== layout.height) {
      canvas.width = layout.width;
      canvas.height = layout.height;
    }
    context.fillStyle = "#13242c";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.font = "bold 33px sans-serif";
    context.fillStyle = "#f0fbfc";
    context.fillText(layout.title, 20, 45, layout.width - 40);
    if (layout.subtitle) {
      context.fillStyle = "#ceeceb";
      context.font = "bold 27px sans-serif";
      context.textAlign = "center";
      context.fillText(layout.subtitle, layout.width / 2, 105, 560);
      context.textAlign = "left";
    }
    // Spatial-tool groups are labels only: ray hit regions remain exactly
    // the existing actionable buttons, with no accidental source edits.
    for (const section of layout.sections ?? []) {
      context.fillStyle = "#95e9de";
      context.font = "bold 24px sans-serif";
      context.fillText(section.label, 20, section.y, layout.width - 40);
    }
    for (const [index, button] of layout.buttons.entries()) {
      const highlight = index === hover || button.active;
      context.fillStyle = highlight ? "#69dbca" : "#2a4651";
      context.fillRect(button.x, button.y, button.w, button.h);
      const middle = button.y + button.h / 2;
      if (button.swatch !== undefined) {
        context.fillStyle = "#" + button.swatch.toString(16).padStart(6, "0");
        context.fillRect(button.x + 12, middle - 13, 25, 26);
      }
      context.fillStyle = highlight ? "#102421" : button.disabled ? "#a1aeb4" : "#fff";
      context.font = "bold 25px sans-serif";
      context.textAlign = "center";
      const inset = button.swatch === undefined ? 0 : 38;
      context.fillText(button.label, button.x + (button.w + inset) * 0.5, middle + 9, button.w - 18 - inset);
      context.textAlign = "left";
    }
    context.fillStyle = "#edf9fc";
    context.font = "27px sans-serif";
    context.fillText(layout.note, 20, layout.height - 23, layout.width - 40);
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
  return { positionMenu, sizeMenu, menuHit, drawMenu, showAim,
    hideMenu: () => { menu.visible = false; },
    dispose: () => texture.dispose() };
}
