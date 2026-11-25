import * as THREE from "three";
import {
  activeStart, aimOpening, buildGuide, MAX_DRAFT_WALLS, nearWall,
  openingFits, planLength, projectOnWall, snappedPoint, snapDraftWallPoint, validWallLength,
  draftShape, validCeiling, validEditedWall, followDraftCeilingEdges,
} from "./buildPlacement.ts";
import type { BuildAction, BuildHit, BuildSizes, BuildState, CeilingDraft, PlanPoint, PlacedWall, WallSnapOptions, WallVisual } from "./buildPlacement.ts";
import type { WallAdditionOpening } from "./wallAdditionProtocol.ts";
import {localDoorMotion} from "./localDoorMotion.ts";
import { exactDraftOpening } from "./vrDraftGeometry.ts";
import { connectedWallEdit } from "./connectedWallEdit.ts";
import type { MenuLayout } from "./catalogueMenu";
import {wallAssembly,profileDetails} from "./wallProfiles.ts";
import {chooseWallAim} from "./wallMagnet.ts";
import type {WallTextureLibrary} from "./wallTextures.ts";
import {menuButtonAt} from "./toolWheelInput.ts";
import {nominalFrameLayout} from "./constructionDetailLayout.ts";
import {makeLiningVisual} from "./constructionLiningVisual.ts";
import {nominalWallConnections,nominalCeilingFraming} from "./constructionFrameVisual.ts";
import {nominalTrimMesh} from "./constructionTrimVisual.ts";

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

/** Visual-only nominal timber members, not an engineered or priced assembly. */
export function illustrativeTimberFrame(wall: WallVisual) {
  const group = new THREE.Group();
  group.userData.illustrativeFraming = true;
  group.visible = false;
  const length = planLength(wall.start, wall.end);
  if (!Number.isFinite(length) || length < .05 || length > 200 || !Number.isFinite(wall.heightM) || wall.heightM < .1 || wall.heightM > 20) return group;
  const openings = (wall.openings ?? []).filter(o => openingFits(wall,o));
  const assembly=wallAssembly(wall.assembly),profile=profileDetails(assembly);
  if(profile.core==="masonry")return group;
  const depth = Math.min(profile.frameMm,assembly.thicknessMm)/1000;
  const angle = -Math.atan2(wall.end[1]-wall.start[1],wall.end[0]-wall.start[0]);
  const holes=openings.map(o=>({x0:o.offsetM,x1:o.offsetM+o.widthM,y0:o.sillHeightM,y1:o.sillHeightM+o.heightM}));
  let members:ReturnType<typeof nominalFrameLayout>;
  try{members=nominalFrameLayout(length,wall.heightM,holes);}catch{return group;}
  // One instanced draw call per wall, rather than a geometry and material per stud.
  if(members.length){
    const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({color:profile.core==="steel"?0x9aa8ad:0xc99c65,roughness:.88}),members.length);
    const transform=new THREE.Object3D();
    members.forEach((m,i)=>{
      transform.position.copy(atOffset(wall,(m.x0+m.x1)/2,(m.y0+m.y1)/2));
      transform.rotation.y=angle;
      transform.scale.set(m.x1-m.x0,m.y1-m.y0,depth);
      transform.updateMatrix();
      mesh.setMatrixAt(i,transform.matrix);
    });
    mesh.userData.nominalFrameRoles=members.map(m=>m.role);
    mesh.instanceMatrix.needsUpdate=true;
    mesh.computeBoundingBox();mesh.computeBoundingSphere();
    mesh.userData.illustrativeFraming=true;
    group.add(mesh);
  }
  return group;
}

export function displayWallDraft(wall: WallVisual,textures?:WallTextureLibrary) {
  const group = new THREE.Group();
  const faces: number[] = [],colors:number[]=[],mountFaces:number[]=[],exteriorFaces:number[]=[],exteriorUV:number[]=[];
  const texture=textures?.get(wallAssembly(wall.assembly).profile);
  const assembly=wallAssembly(wall.assembly),profile=profileDetails(assembly);
  const length=planLength(wall.start,wall.end);
  if(!Number.isFinite(length)||length<.001)return group;
  const normal=new THREE.Vector3(-(wall.end[1]-wall.start[1])/length,0,(wall.end[0]-wall.start[0])/length);
  const half=assembly.thicknessMm/2000;
  const exterior=new THREE.Color(profile.outerColor),interior=new THREE.Color(0xeeeae1);
  const left=assembly.exteriorSide==="left"?exterior:interior,rightColor=assembly.exteriorSide==="right"?exterior:interior;
  function panel(points: THREE.Vector3[], vertices: number[]) {
    for (const index of [0, 1, 2, 0, 2, 3]) vertices.push(...points[index].toArray());
  }
  function surface(from: number, to: number, bottom: number, top: number) {
    if (to <= from || top <= bottom) return;
    const p=[atOffset(wall,from,bottom),atOffset(wall,from,top),atOffset(wall,to,top),atOffset(wall,to,bottom)];
    panel(p,mountFaces);
    const a=p.map(v=>v.clone().addScaledVector(normal,half)),b=p.map(v=>v.clone().addScaledVector(normal,-half));
    function face(points:THREE.Vector3[],color:THREE.Color){panel(points,faces);for(let k=0;k<6;k++)colors.push(color.r,color.g,color.b);}
    face([...a].reverse(),left);face(b,rightColor);
    if(texture&&profile.role==="external"){
      const side=assembly.exteriorSide==="left"?1:-1;
      const points=(side===1?a:b).map(v=>v.clone().addScaledVector(normal,side*.001));
      const ordered=side===1?[...points].reverse():points;
      panel(ordered,exteriorFaces);
      for(const index of [0,1,2,0,2,3]){
        const v=ordered[index],along=(v.x-wall.start[0])*(wall.end[0]-wall.start[0])/length+(v.z-wall.start[1])*(wall.end[1]-wall.start[1])/length;
        exteriorUV.push(along/texture.repeat[0],v.y/texture.repeat[1]);
      }
    }
    for(let i=0;i<4;i++){const j=(i+1)%4;face([a[j],a[i],b[i],b[j]],interior);}

  }
  function addMesh(vertices: number[], color: number, opacity: number, wallFace = false, doorId?: string) {
    if (!vertices.length) return;
    const geometry = new THREE.BufferGeometry().setAttribute("position",
      new THREE.Float32BufferAttribute(vertices, 3));
    if(wallFace)geometry.setAttribute("color",new THREE.Float32BufferAttribute(colors,3));
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
      color:wallFace?0xffffff:color,vertexColors:wallFace, side: THREE.DoubleSide, transparent: opacity < 1, opacity, depthWrite: opacity === 1, roughness: 0.82,
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
    if(opening.openingKind==="window"){
      const glass:number[]=[];panel(points,glass);addMesh(glass,0xb5d0d9,.42);
      const pane=group.children[group.children.length-1];pane.userData.catalogueWindow=true;
    }
    if (opening.openingKind === "door") {
      const leaf: number[] = [];
      panel(points, leaf);
      addMesh(leaf, 0xb68b60, 1, false, opening.openingId);
      const door=group.children[group.children.length-1];
      door.userData.doorHinge=atOffset(wall,opening.offsetM,opening.sillHeightM);
      door.userData.localDoorMotion=localDoorMotion(wall,opening,wallAssembly(wall.assembly).thicknessMm/2000);
    }
  }
  surface(right, planLength(wall.start, wall.end), 0, wall.heightM);
  addMesh(faces, 0xeeeae1, 1, true);
  if(texture&&exteriorFaces.length){
    const g=new THREE.BufferGeometry().setAttribute("position",new THREE.Float32BufferAttribute(exteriorFaces,3)).setAttribute("uv",new THREE.Float32BufferAttribute(exteriorUV,2));
    g.computeVertexNormals();
    const mesh=new THREE.Mesh(g,new THREE.MeshStandardMaterial({map:texture.texture,color:profile.outerColor,roughness:.9,side:THREE.DoubleSide,polygonOffset:true,polygonOffsetFactor:-1,polygonOffsetUnits:-1}));
    mesh.userData.exteriorTexture=true;group.add(mesh);
  }
  // Centre-plane witness retains the existing catalogue anchor convention.
  if(mountFaces.length&&profile.core!=="masonry"){
    const g=new THREE.BufferGeometry().setAttribute("position",new THREE.Float32BufferAttribute(mountFaces,3));
    g.computeVertexNormals();
    const insulation=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:0xd8bb6d,side:THREE.DoubleSide,roughness:1,polygonOffset:true,polygonOffsetFactor:1,polygonOffsetUnits:1}));
    insulation.userData.illustrativeInsulation=true;insulation.visible=false;group.add(insulation);
  }
  if(mountFaces.length){
    const mountGeometry=new THREE.BufferGeometry().setAttribute("position",new THREE.Float32BufferAttribute(mountFaces,3));
    mountGeometry.computeVertexNormals();
    const mount=new THREE.Mesh(mountGeometry,new THREE.MeshBasicMaterial({side:THREE.DoubleSide,visible:false}));
    mount.userData.catalogueMountFace=true;
    group.add(mount);
  }
  const trim=nominalTrimMesh(wall);if(trim)group.add(trim);
  group.add(illustrativeTimberFrame(wall));
  for(const accessory of nominalWallConnections(wall).children.slice())group.add(accessory);
  if(profile.core!=="masonry"){
    const holes=openings.map(o=>({x0:o.offsetM,x1:o.offsetM+o.widthM,y0:o.sillHeightM,y1:o.sillHeightM+o.heightM}));
    const sides=profile.role==="internal"?[1,-1]:[assembly.exteriorSide==="left"?-1:1];
    for(const side of sides){
      const lining=makeLiningVisual(length,wall.heightM,holes,(x,y,offset)=>atOffset(wall,x,y).addScaledVector(normal,side*(half+offset)));
      if(lining)group.add(lining);
    }
  }
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
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: 0xf5f2eb,
    side: THREE.DoubleSide, roughness: 0.88 }));
  const left=Math.min(draft.start[0],draft.end[0]),front=Math.min(draft.start[1],draft.end[1]);
  const lining=makeLiningVisual(Math.abs(draft.end[0]-draft.start[0]),Math.abs(draft.end[1]-draft.start[1]),[],(x,y,offset)=>new THREE.Vector3(left+x,draft.heightM-offset,front+y));
  if(lining)mesh.add(lining);
  const framing=nominalCeilingFraming(draft);if(framing)mesh.add(framing);
  return mesh;
}

type DragDraw = { mode: "wall" | "ceiling"; from: PlanPoint };
type DragEdit = { mode: "move" | "stretch"; from: PlanPoint; anchor: PlanPoint; stretchStart?: boolean };
type DragOpening = {kind:"opening";mode:"opening-move";from:PlanPoint;
  previous:PlacedWall;openingId:string};
export type DraftGesture = (DragDraw | (DragEdit & (
  { kind: "wall"; previous: PlacedWall } | { kind: "ceiling"; previous: CeilingDraft }
)) | DragOpening) & { levelId: string; fromController?: PlanPoint; precisionSource?:boolean; direct?:boolean };

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

export function beginDraftGesture(state: BuildState, levelId: string | null, ray: THREE.Ray,
  options: WallSnapOptions = {}): DraftGesture | null {
  if (!levelId || !state.tool) return null;
  // A level controller ray can hit a vertical wall but never the floor.
  // Recognise that direct wall contact as a valid draft manipulation target.
  const directWall = state.tool === "move" || state.tool === "stretch" ||
    state.tool === "opening-move"
    ? openingHost(state.walls.filter(wall => wall.levelId === levelId), ray, null,options) : null;
  const from = planPoint(ray) ?? (directWall && snappedPoint(directWall.point));
  if (!from) return null;
  const mode = state.tool;
  if (mode === "wall" || mode === "ceiling") {
    const aligned = mode === "wall" ? snapDraftWallPoint(state, levelId, from, null, options) : null;
    const alignedStart = aligned?.point ?? from;
    return activeStart(state, levelId) || !alignedStart ? null :
      { mode, from: alignedStart, levelId, precisionSource:aligned?.kind==="verified" };
  }
  if (mode !== "move" && mode !== "stretch" && mode !== "opening-move") return null;
  const floor = new THREE.Vector3(from[0], 0, from[1]);
  if(mode==="opening-move"){
    const host=openingHost(state.walls.filter(wall=>wall.levelId===levelId),ray,floor,options);
    if(!host)return null;
    const projection=projectOnWall(host.wall,host.point);
    const opening=host.wall.openings.filter(item=>
      Math.abs(item.offsetM+item.widthM/2-projection.offset)<item.widthM/2+0.12)
      .sort((a,b)=>Math.abs(a.offsetM+a.widthM/2-projection.offset)-
        Math.abs(b.offsetM+b.widthM/2-projection.offset))[0];
    return opening?{kind:"opening",mode,from,levelId,previous:host.wall,
      openingId:opening.openingId}:null;
  }
  const wall = openingHost(state.walls.filter(draft => draft.levelId === levelId), ray, floor,options);
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

export type DraftPickKind="auto"|"walls"|"ceilings";
/** Inspect-mode drag: use the existing validated move gesture, not a second
 * geometry editing path. A top-view wall hit wins over a covering ceiling. */
export function directDraftGesture(state:BuildState,levelId:string|null,ray:THREE.Ray,
 kind:DraftPickKind,top:boolean,options:WallSnapOptions={}):DraftGesture|null{
 const move={...state,tool:"move" as const};
 const wall=()=>beginDraftGesture({...move,ceilings:[]},levelId,ray,options);
 const ceiling=()=>beginDraftGesture({...move,walls:[]},levelId,ray,options);
 const gesture=kind==="walls"||top&&kind==="auto"?wall():kind==="ceilings"?ceiling():
   beginDraftGesture(move,levelId,ray,options);
 return gesture?{...gesture,direct:true}:null;
}

export function draftGesturePreview(gesture: DraftGesture, sizes: BuildSizes, ray: THREE.Ray,
  state?: BuildState, controllerPosition?: PlanPoint, options: WallSnapOptions = {}, connected=false) {
  // With Quest controllers, manipulation should follow the hand in X/Z, not
  // require aiming at an imaginary ground plane throughout the drag.
  const current = "previous" in gesture && gesture.fromController && controllerPosition
    ? snappedPoint([gesture.from[0] + controllerPosition[0] - gesture.fromController[0],
        gesture.from[1] + controllerPosition[1] - gesture.fromController[1]])
    : planPoint(ray);
  if (!current) return null;
  const floor = ray.intersectPlane(PLAN, new THREE.Vector3());
  const aligned = gesture.mode === "wall" && !("previous" in gesture) && state && floor
    ? snapDraftWallPoint(state, gesture.levelId, [floor.x, floor.z], gesture.from, options) : null;
  const to = aligned?.point ?? current;
  const delta = planLength(gesture.from, to);
  if (delta < 0.045) return null;
  let line: THREE.Vector3[], valid: boolean, action: BuildAction;
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
    action = { kind: "drag", levelId, from, to, id: "",
      precisionSource:gesture.precisionSource===true || aligned?.kind==="verified" };
  } else if (gesture.kind === "opening") {
    const {previous,openingId,from}=gesture;
    const opening=previous.openings.find(item=>item.openingId===openingId);
    if(!opening)return null;
    const length=planLength(previous.start,previous.end);
    if(length<0.05)return null;
    const direction:[number,number]=[
      (previous.end[0]-previous.start[0])/length,
      (previous.end[1]-previous.start[1])/length];
    const along=(to[0]-from[0])*direction[0]+(to[1]-from[1])*direction[1];
    const offsetMm=Math.round((opening.offsetM+along)*20)*50;
    const changed=exactDraftOpening(previous,openingId,"offset",offsetMm);
    valid=!!changed;
    const nextOpening=(changed??previous).openings.find(item=>item.openingId===openingId)!;
    line=openingOutline(changed??previous,nextOpening);
    action={kind:"exact-local-opening",proposalId:previous.proposalId,openingId,
      field:"offset",valueMm:offsetMm};
  } else if (gesture.kind === "wall") {
    const { previous, mode, from, anchor, stretchStart } = gesture;
    const moving = stretchStart ? previous.start : previous.end;
    const target = snappedPoint([moving[0] + to[0] - from[0], moving[1] + to[1] - from[1]]);
    if (!target) return null;
    const shape = mode === "stretch" && stretchStart
      ? { ...previous, start: target, end: anchor }
      : draftShape(previous, mode, from, mode === "stretch" ? target : to, anchor);
    if (!shape) return null;
    const connectedWalls=connected&&state?connectedWallEdit(state.walls,previous,shape,true):null;
    valid = validEditedWall(shape)&&(!connected||(connectedWalls!==null&&connectedWalls.every(validEditedWall)&&state!==undefined&&followDraftCeilingEdges(state.ceilings,previous,shape)!==null));
    line = [new THREE.Vector3(shape.start[0], shape.heightM, shape.start[1]),
      new THREE.Vector3(shape.end[0], shape.heightM, shape.end[1])];
    action = { kind: "adjust", previous, wall: shape, ...(connected ? {connected:true,allowTJunctions:true} : {}) };
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
  const hint = !valid ? connected&&"previous" in gesture&&gesture.kind==="wall" ? "Connected edit blocked: junction, wall size or opening conflict. Turn Junctions OFF to edit independently." : "Size is invalid or an opening would no longer fit."
    : gesture.mode === "opening-move" ?
      "Release to slide draft opening along its host wall."
    : gesture.mode === "wall" && !("previous" in gesture)
    ? "Release to place · " + Math.round(delta * 1000) + " mm" +
      (aligned?.kind === "corner" ? " · corner snap" :
       aligned?.kind === "verified" ? " · verified source guide (draft only)" :
       aligned?.kind === "straight" ? " · straight" : "")
    : "Release to apply to the draft.";
  const aim: Aim = { hit: null, valid, line, hint,
    marker: gesture.mode === "wall" && !("previous" in gesture) ? to : undefined };
  return { action: valid ? action : null, aim };
}

function openingHost(walls: PlacedWall[], ray: THREE.Ray, floor: THREE.Vector3 | null,options:WallSnapOptions={}) {
  if(options.magnetic===true){
    const targets=walls.map(w=>({key:"draft:"+w.proposalId,id:w.proposalId,kind:"draft" as const,start:w.start,end:w.end,heightM:w.heightM,halfThickness:wallAssembly(w.assembly).thicknessMm/2000}));
    const aim=chooseWallAim(ray,targets,options.preferredDraftId?"draft:"+options.preferredDraftId:null,true);
    const wall=aim&&walls.find(w=>w.proposalId===aim.target.id);
    if(aim&&wall)return {wall,point:aim.point,distance:aim.distance*aim.distance};
  }
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

// All overlapping local draft targets are ordered by distance, with a stable
// proposal ID tie-break. The caller may cycle them on repeated trigger presses.
export function pickDraftWalls(state: BuildState, levelId: string | null,
  ray: THREE.Ray): PlacedWall[] {
  if (!levelId) return [];
  const floor = ray.intersectPlane(PLAN, new THREE.Vector3());
  return state.walls.filter(wall => wall.levelId === levelId)
    .map(wall => openingHost([wall],ray,floor))
    .filter((hit): hit is NonNullable<typeof hit> => !!hit)
    .sort((a,b) => a.distance-b.distance ||
      a.wall.proposalId.localeCompare(b.wall.proposalId))
    .map(hit => hit.wall);
}
/** Exact visible draft faces win; near misses use bounded magnetic tolerance.
 * The previous hover receives a wider release band only when no exact face is hit. */
export function magneticDraftWalls(state:BuildState,levelId:string|null,ray:THREE.Ray,previous:string|null=null,strength=.15):PlacedWall[]{
 if(!levelId||!Number.isFinite(strength)||strength<0||strength>.4)return [];
 const exact:{wall:PlacedWall;distance:number}[]=[],near:{wall:PlacedWall;miss:number;distance:number}[]=[];
 const floor=ray.intersectPlane(PLAN,new THREE.Vector3());
 for(const wall of state.walls){
  if(wall.levelId!==levelId)continue;
  const length=planLength(wall.start,wall.end);if(length<.05)continue;
  const normal=new THREE.Vector3(wall.end[1]-wall.start[1],0,wall.start[0]-wall.end[0]).normalize();
  const plane=new THREE.Plane().setFromNormalAndCoplanarPoint(normal,new THREE.Vector3(wall.start[0],0,wall.start[1]));
  const hit=ray.intersectPlane(plane,new THREE.Vector3());
  const tolerance=strength*(wall.proposalId===previous?1.6:1);
  if(hit){
   const {offset}=projectOnWall(wall,[hit.x,hit.z]);
   const miss=Math.hypot(Math.max(0,-offset,offset-length),Math.max(0,-hit.y,hit.y-wall.heightM));
   if(miss<1e-7){exact.push({wall,distance:ray.origin.distanceToSquared(hit)});continue;}
   if(miss<=tolerance&&strength>0){near.push({wall,miss,distance:ray.origin.distanceToSquared(hit)});continue;}
  }
  if(floor&&strength>0){
   const projection=projectOnWall(wall,[floor.x,floor.z]);
   const miss=Math.hypot(projection.distance,Math.max(0,-projection.offset,projection.offset-length));
   if(miss<=tolerance)near.push({wall,miss,distance:ray.origin.distanceToSquared(floor)});
  }
 }
 if(exact.length)return exact.sort((a,b)=>a.distance-b.distance||a.wall.proposalId.localeCompare(b.wall.proposalId)).map(x=>x.wall);
 return near.sort((a,b)=>Number(b.wall.proposalId===previous)-Number(a.wall.proposalId===previous)||a.miss-b.miss||a.distance-b.distance||a.wall.proposalId.localeCompare(b.wall.proposalId)).map(x=>x.wall);
}

export function pickDraftWall(state: BuildState, levelId: string | null,
  ray: THREE.Ray): PlacedWall | null {
  return pickDraftWalls(state,levelId,ray)[0] ?? null;
}

export function aimBuild(state: BuildState, levelId: string | null, sizes: BuildSizes, ray: THREE.Ray,
  options: WallSnapOptions = {}): Aim {
  const guide = buildGuide(state, levelId);
  if (!state.tool || !levelId) return { hit: null, hint: guide };
  const floor = ray.intersectPlane(PLAN, new THREE.Vector3());
  if (state.tool === "move" || state.tool === "stretch" || state.tool === "opening-move") {
    const edit = beginDraftGesture(state, levelId, ray,options);
    if (!edit || !("previous" in edit)) return { hit: null, hint: guide };
    const { previous } = edit;
    const marker = state.tool === "move" || edit.kind === "opening" ?
      edit.from : edit.kind === "wall" ?
      edit.stretchStart ? previous.start : previous.end : undefined;
    return { hit: null, marker, hint: guide };
  }
  if (state.tool === "wall" || state.tool === "ceiling") {
    const ceiling = state.tool === "ceiling";
    if ((ceiling ? state.ceilings : state.walls).length >= MAX_DRAFT_WALLS) return { hit: null, hint: guide };
    const start = activeStart(state, levelId);
    const snap = state.tool === "wall" && floor
      ? snapDraftWallPoint(state, levelId, [floor.x, floor.z], start, options) : null;
    const point = snap?.point ?? (floor && snappedPoint([floor.x, floor.z]));
    if (!point) return { hit: null, hint: "Aim at the plan to place a point." };
    const hit: BuildHit = { kind: state.tool, levelId, point,
      precisionSource:snap?.kind==="verified" };
    if (!start) return { hit, marker: point,
      hint: snap?.kind === "wall-face" ? "Place wall start · magnetic wall snap" : snap?.kind === "corner" ? "Place wall start · corner snap" :
        snap?.kind === "verified" ? "Place wall start · verified source guide (draft only)" : guide };
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
      hint: valid
        ? "Place wall end · " + Math.round(length * 1000) + " mm" +
          (snap?.kind === "wall-face" ? " · magnetic wall snap" : snap?.kind === "corner" ? " · corner snap" :
           snap?.kind === "verified" ? " · verified source guide (draft only)" :
           snap?.kind === "straight" ? " · straight" : "")
        : "Wall length must be 50 mm to 200 m.",
    };
  }
  const host = openingHost(state.walls.filter(wall => wall.levelId === levelId), ray, floor,options);
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
    new THREE.MeshBasicMaterial({ map: texture, toneMapped: false, transparent: true, depthTest: false, depthWrite: false }));
  menu.renderOrder = 20;
  menu.visible = false;
  scene.add(menu);
  // Hover is a tiny untextured overlay, not a full canvas redraw/upload.
  const hoverMesh=new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({color:0x91e8d2,transparent:true,opacity:.20,depthTest:false,depthWrite:false,toneMapped:false}));
  hoverMesh.renderOrder=21;hoverMesh.visible=false;menu.add(hoverMesh);
  function highlightMenu(layout:MenuLayout,index:number){
    const button=layout.buttons[index];
    hoverMesh.visible=!layout.radial&&!!button&&!button.disabled;
    if(!hoverMesh.visible)return;
    hoverMesh.position.set((button.x+button.w/2)/layout.width-.5,.5-(button.y+button.h/2)/layout.height,.002);
    hoverMesh.scale.set(button.w/layout.width,button.h/layout.height,1);
  }
  const mark = new THREE.Mesh(new THREE.RingGeometry(0.037, 0.057, 24),
    new THREE.MeshBasicMaterial({ color: 0x71f7dc, side: THREE.DoubleSide }));
  mark.rotation.x = -Math.PI / 2;
  mark.visible = false;
  scene.add(mark);
  // The live length is shown next to the point in the world, rather than
  // only on the distant tool panel where a Quest user must look away.
  const dimensionCanvas = document.createElement("canvas");
  dimensionCanvas.width = 640;
  dimensionCanvas.height = 96;
  const dimensionContext = dimensionCanvas.getContext("2d");
  const dimensionTexture = new THREE.CanvasTexture(dimensionCanvas);
  dimensionTexture.colorSpace = THREE.SRGBColorSpace;
  const dimensionMaterial = new THREE.SpriteMaterial({
    map: dimensionTexture, depthTest: false, depthWrite: false,
  });
  const dimensionSprite = new THREE.Sprite(dimensionMaterial);
  dimensionSprite.scale.set(1.7, 0.255, 1);
  dimensionSprite.renderOrder = 22;
  dimensionSprite.visible = false;
  scene.add(dimensionSprite);
  let lastDimension = "";
  const positions = new THREE.Float32BufferAttribute(new Float32Array(15), 3);
  const geometry = new THREE.BufferGeometry().setAttribute("position", positions);
  const outline = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: 0x71f7dc }));
  outline.frustumCulled = false;
  outline.visible = false;
  scene.add(outline);
  // Local-only 3D moving-wall outline: shows where the entire wall will land
  // before release, including height, without moving any source-backed meshes.
  const ghostPositions = new THREE.Float32BufferAttribute(new Float32Array(72),3);
  const ghostGeometry=new THREE.BufferGeometry().setAttribute("position",ghostPositions);
  const ghost=new THREE.LineSegments(ghostGeometry,new THREE.LineBasicMaterial({
    color:0x75f7db,transparent:true,opacity:0.9,depthTest:false}));
  ghost.frustumCulled=false;
  ghost.renderOrder=18;
  ghost.visible=false;
  scene.add(ghost);
  let lastGhost: readonly number[] | null = null;
  function showWallGhost(shape:{start:PlanPoint;end:PlanPoint;heightM:number;assembly?:WallVisual["assembly"]}|null){
    ghost.visible=!!shape;
    if(!shape)return;
    const {start,end,heightM}=shape,length=planLength(start,end);
    if(length<.001){ghost.visible=false;return;}
    const half=wallAssembly(shape.assembly).thicknessMm/2000;
    const key=[start[0],start[1],end[0],end[1],heightM,half];
    if(lastGhost && key.every((v,i)=>v===lastGhost![i]))return;
    lastGhost=key;
    const nx=-(end[1]-start[1])/length*half,nz=(end[0]-start[0])/length*half;
    const points=[[start[0]+nx,.035,start[1]+nz],[end[0]+nx,.035,end[1]+nz],[end[0]-nx,.035,end[1]-nz],[start[0]-nx,.035,start[1]-nz],
      [start[0]+nx,heightM,start[1]+nz],[end[0]+nx,heightM,end[1]+nz],[end[0]-nx,heightM,end[1]-nz],[start[0]-nx,heightM,start[1]-nz]];
    let index=0;
    for(const [a,b] of [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]])for(const i of [a,b])ghostPositions.setXYZ(index++,points[i][0],points[i][1],points[i][2]);
    ghostPositions.needsUpdate=true;
    ghostGeometry.setDrawRange(0,index);
  }

  const previousHead = new THREE.Vector3();
  const previousFacing = new THREE.Vector3();
  const head = new THREE.Vector3();
  const facing = new THREE.Vector3();
  const right = new THREE.Vector3();
  let drawn = "";
  function positionMenu(camera: THREE.Camera, pinned = false, force = false) {
    camera.getWorldPosition(head);
    camera.getWorldDirection(facing);
    facing.y = 0;
    if (facing.lengthSq() < 0.01) facing.set(0,0,-1);
    facing.normalize();
    // Pinned is world-locked during editing, but auto-recentres if the user
    // walks too far away and would otherwise lose the control surface.
    if (!force && pinned && menu.visible && menu.position.distanceTo(head) < 2.25) return;
    if (!force && !pinned && menu.visible &&
      previousHead.distanceToSquared(head) <= 0.36 &&
      previousFacing.dot(facing) > 0.75) return;
    previousHead.copy(head);
    previousFacing.copy(facing);
    right.set(-facing.z, 0, facing.x);
    menu.position.copy(head).addScaledVector(facing, 1.30);
    menu.position.y -= 0.30;
    menu.lookAt(head);
    menu.updateMatrixWorld();
    menu.visible = true;
  }
  function positionHandMenu(camera:THREE.Camera,hand:THREE.Object3D){
    camera.getWorldPosition(head);
    hand.getWorldPosition(menu.position);
    menu.position.y+=.18;
    // Keep the tool wheel at a comfortable readable distance even if the hand is near the face.
    const offset=menu.position.clone().sub(head);
    const distance=offset.length();
    if(distance<.65||distance>1.0){if(distance<.001)offset.set(0,-.4,-.5);menu.position.copy(head).add(offset.setLength(Math.max(.65,Math.min(1.0,distance))));}
    menu.lookAt(head);menu.updateMatrixWorld();menu.visible=true;
  }
  function sizeMenu(layout: MenuLayout) {
    // Larger angular hit targets without changing the menu action mapping.
    const scale=layout.radial?950:Math.max(800,layout.height/.85,layout.width/1.12);
    const width = layout.width / scale, height = layout.height / scale;
    if (menu.scale.x !== width || menu.scale.y !== height) {
      menu.scale.set(width, height, 1);
      menu.updateMatrixWorld();
    }
  }
  function menuHit(raycaster: THREE.Raycaster, layout: MenuLayout) {
    const uv = menu.visible ? raycaster.intersectObject(menu, false)[0]?.uv : undefined;
    if (!uv) return null;
    const x = uv.x * layout.width, y = (1 - uv.y) * layout.height;
    const index=menuButtonAt(layout,x,y);
    return { action: layout.buttons[index]?.action ?? null, index };
  }
  function drawMenu(layout: MenuLayout, hover: number) {
    highlightMenu(layout,hover);
    const key = JSON.stringify([layout, layout.radial?hover:-1]);
    if (!context || drawn === key) return;
    drawn = key;
    if (canvas.width !== layout.width || canvas.height !== layout.height) {
      canvas.width = layout.width;
      canvas.height = layout.height;
    }
    context.clearRect(0,0,canvas.width,canvas.height);
    context.fillStyle = "#13242c";
    if(layout.radial){context.beginPath();context.arc(canvas.width/2,canvas.height/2,canvas.width/2-2,0,Math.PI*2);context.fill();}
    else context.fillRect(0, 0, canvas.width, canvas.height);
    context.font = "bold 33px sans-serif";
    context.fillStyle = "#f0fbfc";
    if(layout.radial){/* title is rendered in the centre below */}
    else context.fillText(layout.title, 20, 45, layout.width - 40);
    if (layout.subtitle) {
      context.fillStyle = "#ceeceb";
      context.font = "bold 27px sans-serif";
      context.textAlign = "center";
      context.fillText(layout.subtitle, layout.width / 2, 105, 560);
      context.textAlign = "left";
    }
    for (const section of layout.sections ?? []) {
      context.fillStyle = "#96e6dd";
      context.font = "bold 24px sans-serif";
      context.fillText(section.label, 20, section.y, layout.width - 40);
    }
    if (layout.helpLines) {
      context.font = "bold 27px sans-serif";
      layout.helpLines.forEach((line,index) => {
        context.fillStyle = index%2===0 ? "#f0fbfc" : "#b9d5d8";
        context.fillText(line, 28, 95+index*44, layout.width-56);
      });
    }
    if(layout.radial){
      const cx=layout.width/2,cy=layout.height/2,outer=layout.width/2-4,inner=layout.width*.145;
      for(let i=0;i<8;i++){
        const button=layout.buttons[i],angle=i*Math.PI/4-Math.PI/2,half=Math.PI/8-.012;
        const active=i===hover&&!button.disabled;
        context.beginPath();context.arc(cx,cy,outer,angle-half,angle+half);
        context.arc(cx,cy,inner,angle+half,angle-half,true);context.closePath();
        context.fillStyle=button.disabled?"#203039":active?"#69dbca":"#355463";context.fill();
        context.strokeStyle="#13242c";context.lineWidth=3;context.stroke();
        context.font="bold 32px sans-serif";context.fillStyle=active?"#102421":button.disabled?"#8d9aa0":"#fff";context.textAlign="center";context.textBaseline="middle";
        context.fillText(button.label,cx+Math.cos(angle)*218,cy+Math.sin(angle)*218,162);
      }
      context.beginPath();context.arc(cx,cy,inner-5,0,Math.PI*2);context.fillStyle=hover===8?"#69dbca":"#142a34";context.fill();
      context.fillStyle=hover===8?"#102421":"#fff";context.font="bold 27px sans-serif";context.fillText("Close",cx,cy-12,140);
      context.font="18px sans-serif";context.fillText("Grip / trigger",cx,cy+22,150);
      context.textAlign="left";context.textBaseline="alphabetic";
      texture.needsUpdate=true;return;
    }
    for (const [index, button] of layout.buttons.entries()) {
      const highlight = button.active;
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
    if(layout.radial){context.textAlign="center";context.fillText(layout.note,layout.width/2,layout.height-33,240);context.textAlign="left";}
    else context.fillText(layout.note, 20, layout.height - 23, layout.width - 40);
    texture.needsUpdate = true;
  }
  function showAim(aim: Aim | null, origin: PlanPoint | null) {
    const marker = aim?.marker ?? origin;
    const text = marker && aim?.line && aim.valid !== false &&
      /\\bmm\\b/.test(aim.hint) ? aim.hint : "";
    dimensionSprite.visible = !!text;
    if (text && marker) {
      dimensionSprite.position.set(marker[0], 0.38, marker[1]);
      if (text !== lastDimension && dimensionContext) {
        lastDimension = text;
        dimensionContext.clearRect(0, 0, 640, 96);
        dimensionContext.fillStyle = "rgba(12, 31, 38, .96)";
        dimensionContext.fillRect(0, 0, 640, 96);
        dimensionContext.fillStyle = "#b2fff0";
        dimensionContext.font = "bold 32px sans-serif";
        dimensionContext.textAlign = "center";
        dimensionContext.textBaseline = "middle";
        dimensionContext.fillText(text, 320, 48, 610);
        dimensionTexture.needsUpdate = true;
      }
    }
    mark.visible = !!marker;
    if (marker) {
      mark.position.set(marker[0], 0.027, marker[1]);
      mark.material.color.setHex(aim?.valid === false ? 0xffab78 : 0x71f7dc);
    }
    outline.visible = !!aim?.line;
    if (aim?.line) {
      let changed=geometry.drawRange.count!==aim.line.length;
      aim.line.forEach((point,i)=>{
        if(positions.getX(i)!==Math.fround(point.x)||positions.getY(i)!==Math.fround(point.y)||positions.getZ(i)!==Math.fround(point.z)){
          positions.setXYZ(i,point.x,point.y,point.z);
          changed=true;
        }
      });
      if(changed){
        positions.needsUpdate=true;
        geometry.setDrawRange(0,aim.line.length);
      }
      outline.material.color.setHex(aim.valid === false ? 0xffab78 : 0x71f7dc);
    }
  }
  return { positionMenu, positionHandMenu, sizeMenu, menuHit, drawMenu, highlightMenu, showAim, showWallGhost,
    hideMenu: () => { menu.visible = false; },
    dispose: () => { texture.dispose(); dimensionTexture.dispose(); dimensionMaterial.dispose(); } };
}
