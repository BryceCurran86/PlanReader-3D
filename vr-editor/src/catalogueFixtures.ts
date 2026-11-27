import * as THREE from "three";
import {RoundedBoxGeometry} from "three/addons/geometries/RoundedBoxGeometry.js";
import {applyFixtureFabric} from "./fixtureFabric.ts";
import type { ItemTarget, ItemVisual } from "./itemCatalogue";

type FixtureSpec = Extract<ItemVisual, { kind: "fixture" }>;

export function createCatalogueFixture(spec: FixtureSpec, target: ItemTarget) {
  const group = new THREE.Group();
  const { widthM: w, heightM: h, depthM: d, count, shape } = spec;
  const body = new THREE.MeshStandardMaterial({
    color: spec.color, roughness: spec.metalness > 0.4 ? 0.31 : 0.54, metalness: spec.metalness,
  });
  const detail = new THREE.MeshStandardMaterial({ color: 0x2d3337, roughness: 0.67 });
  const white = new THREE.MeshStandardMaterial({ color: 0xf0ece2, roughness: 0.34 });
  const lens = new THREE.MeshStandardMaterial({ color: 0xfff3db, emissive: 0xffedc9, emissiveIntensity: 0.18 });
  let worktop: THREE.Mesh | undefined;

  function mesh(geometry: THREE.BufferGeometry, x: number, y: number, z: number, material = body) {
    const part = new THREE.Mesh(geometry, material);
    part.position.set(x, y, z);
    part.receiveShadow = true;
    part.castShadow = true;
    group.add(part);
    return part;
  }
  function box(w: number, h: number, d: number, x: number, y: number, z: number, material = body) {
    return mesh(new THREE.BoxGeometry(w, h, d), x, y, z, material);
  }
  function softBox(w:number,h:number,d:number,x:number,y:number,z:number,material=body){
    return mesh(new RoundedBoxGeometry(w,h,d,2,Math.min(.035,w/4,h/4,d/4)),x,y,z,material);
  }
  function cylinder(radius: number, depth: number, x: number, y: number, z: number, material = body) {
    return mesh(new THREE.CylinderGeometry(radius, radius, depth, 16), x, y, z, material);
  }
  function disk(radius: number, depth: number, x: number, y: number, z: number, material = body) {
    const part = cylinder(radius, depth, x, y, z, material);
    part.rotation.x = Math.PI / 2;
    return part;
  }
  function oval(w: number, h: number, d: number, x: number, y: number, z: number, material = body) {
    const part = mesh(new THREE.SphereGeometry(1, 18, 12), x, y, z, material);
    part.scale.set(w / 2, h / 2, d / 2);
    return part;
  }
  function pipe(points: [number, number, number][], radius: number, smooth = true) {
    if (smooth) {
      const curve = new THREE.CatmullRomCurve3(points.map(([x, y, z]) => new THREE.Vector3(x, y, z)));
      mesh(new THREE.TubeGeometry(curve, 16, radius, 10), 0, 0, 0);
      return;
    }
    for (let index = 1; index < points.length; index++) {
      const first = new THREE.Vector3(...points[index - 1]);
      const last = new THREE.Vector3(...points[index]);
      const middle = first.clone().lerp(last, 0.5);
      const segment = cylinder(radius, first.distanceTo(last), middle.x, middle.y, middle.z);
      segment.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), last.sub(first).normalize());
    }
  }

  switch (shape) {
    case "shower-screen": {
      const glass=new THREE.MeshStandardMaterial({color:0xdce9e7,roughness:.075,metalness:.08,transparent:true,opacity:.19,depthWrite:false,side:THREE.DoubleSide,envMapIntensity:1.4});
      const pane=box(w-.024,h-.018,.008,0,h/2,0,glass);pane.name="Shower safety-glass preview";pane.castShadow=false;
      box(.018,h,d,-w/2+.009,h/2,0).name="Screen wall channel";
      box(w,.012,d,0,.006,0).name="Screen bottom channel";
      for(const y of [h*.23,h*.78])box(.035,.045,d,w/2-.018,y,0).name="Screen retaining clamp";
      break;
    }
    case "oven": {
      softBox(w,h,d*.94,0,h/2,-d*.03).name="Oven cabinet";
      box(w*.9,h*.095,.012,0,h*.87,d*.455,detail).name="Oven control fascia";
      const glass=new THREE.MeshStandardMaterial({color:0x20272a,metalness:.18,roughness:.12});
      box(w*.84,h*.56,.018,0,h*.47,d*.475,glass).name="Oven door glazing";
      box(w*.78,.021,.027,0,h*.765,d*.486).name="Oven handle";
      for(let i=0;i<4;i++)disk(.017,.013,(i-1.5)*w*.18,h*.87,d*.47);
      break;
    }
    case "fridge":
    case "dishwasher": {
      softBox(w,h,d*.92,0,h/2,-d*.04).name="Appliance carcass";
      const divisions=shape==="fridge"?[.32,.68]:[1];let bottom=.035;
      for(const fraction of divisions){const height=(h-.065)*fraction;softBox(w*.97,height-.008,d*.06,0,bottom+height/2,d*.46).name="Appliance door";box(w*.62,.019,.019,0,bottom+height-.04,d*.489,detail).name="Appliance handle";bottom+=height;}
      box(w*.85,.035,.012,0,.0175,d*.42,detail).name="Recessed appliance plinth";
      break;
    }
    case "cooktop": {
      softBox(w,h,d,0,h/2,0,detail).name="Induction glass surface";
      const ringMaterial=new THREE.MeshStandardMaterial({color:0x7b8183,roughness:.5});
      for(const x of [-.24,.24])for(const z of [-.23,.23]){const radius=Math.min(w,d)*.17;const ring=mesh(new THREE.TorusGeometry(radius,.0013,4,32),x*w,h+.001,z*d,ringMaterial);ring.rotation.x=-Math.PI/2;ring.name="Induction zone";ring.castShadow=false;}
      break;
    }
    case "service-box":
      box(w, h, d, 0, h / 2, d / 2);
      for (let line = -1; line <= 1; line++) {
        box(w * 0.74, h * 0.05, d * 0.04,
          0, h / 2 + h * 0.18 * line, d, detail);
      }
      break;
    case "mixer":
      if (target === "wall") {
        disk(w / 2, 0.012, 0, 0, 0.008);
        disk(w * 0.22, d * 0.65, 0, 0, d * 0.42);
        box(w * 0.13, h * 0.45, 0.01, 0, h * 0.12, d * 0.78);
        break;
      }
      cylinder(w * 0.53, 0.008, 0, 0.004, 0);
      cylinder(w * 0.31, h, 0, h / 2, 0);
      pipe([[0, h * 0.8, 0], [0, h * 0.8, d * 0.85], [0, h * 0.7, d]], w * 0.16);
      box(w * 0.2, 0.008, d * 0.4, 0, h, d * 0.09);
      cylinder(w*.12,.004,0,h*.7-.005,d,detail);
      break;
    case "gooseneck":
    case "square-spout":
      cylinder(w * 0.52, 0.009, 0, 0.0045, 0);
      cylinder(w * 0.36, h * 0.4, 0, h * 0.2, 0);
      pipe([[0, h * 0.28, 0], [0, h * 0.9, 0], [0, h, d * 0.47],
        [0, h * 0.86, d * 0.91], [0, h * 0.72, d]], w * 0.19, shape === "gooseneck");
      cylinder(w * (count > 1 ? 0.27 : 0.18), 0.025, 0, h * 0.72, d, count > 1 ? detail : body);
      box(w * 0.19, h * 0.16, 0.012, w * 0.47, h * 0.31, 0);
      cylinder(w*.12,.004,0,h*.72-.014,d,detail);
      break;
    case "wall-spout":
    case "outdoor-tap":
      disk(w / 2, 0.01, 0, 0, 0.007);
      pipe([[0, 0, 0.01], [0, 0, d * 0.83], [0, -h * 0.3, d]], w * 0.17);
      if (shape === "outdoor-tap") {
        cylinder(w * 0.13, h * 0.52, 0, h * 0.25, d * 0.35);
        box(w * 0.8, 0.013, w * 0.17, 0, h * 0.51, d * 0.35);
      }
      break;
    case "shower":
      disk(w * 0.24, 0.014, 0, 0, 0.009);
      if (count > 1) {
        cylinder(0.011, h, 0, 0, d * 0.37);
        disk(w * 0.36, 0.03, 0, h * 0.37, d * 0.83);
        pipe([[0, -h * 0.15, d * 0.42], [0, -h * 0.57, d * 0.37], [0, h * 0.33, d * 0.82]], 0.006);
      } else {
        pipe([[0, 0, 0.01], [0, h * 0.3, d * 0.6], [0, -h * 0.11, d]], 0.012);
        cylinder(w / 2, 0.026, 0, -h * 0.13, d);
      }
      break;
    case "socket":
    case "switch":
    case "port":
    case "isolator":
      box(w, h, d, 0, 0, d / 2);
      for (let index = 0; index < count; index++) {
        const horizontal = shape !== "switch" || w > h;
        const position = (index + 0.5) / count - 0.5;
        const x = horizontal ? position * w * 0.8 : 0;
        const y = horizontal ? 0 : position * h * 0.85;
        const componentWidth = w * (horizontal ? 0.72 / count : 0.6);
        const componentHeight = h * (horizontal ? 0.52 : 0.76 / count);
        if (shape === "socket") {
          box(componentWidth * 0.12, componentHeight * 0.34, 0.003, x - componentWidth * 0.22, y + h * 0.07, d, detail);
          box(componentWidth * 0.12, componentHeight * 0.34, 0.003, x + componentWidth * 0.22, y + h * 0.07, d, detail);
          box(componentWidth * 0.11, componentHeight * 0.21, 0.003, x, y - h * 0.14, d, detail);
        } else if (shape === "isolator") {
          disk(Math.min(componentWidth, componentHeight) * 0.4, 0.009, x, y, d, detail);
        } else {
          box(componentWidth, componentHeight, 0.005, x, y, d, shape === "port" ? detail : body);
        }
      }
      break;
    case "alarm":
    case "downlight":
    case "fan":
      disk(w / 2, d * 0.65, 0, 0, d * 0.35);
      disk(w * 0.39, d * 0.28, 0, 0, d * 0.76, shape === "downlight" ? lens : detail);
      if (shape === "alarm") disk(w * 0.055, 0.005, w * 0.25, 0, d * 0.95, lens);
      if (shape === "fan") for (let index = -2; index <= 2; index++) {
        box(w * 0.62, w * 0.035, d * 0.18, 0, w * index * 0.105, d * 0.88);
      }
      break;
    case "batten":
      box(w, h, d * 0.65, 0, 0, d * 0.32);
      box(w * 0.94, h * 0.77, d * 0.29, 0, 0, d * 0.79, lens);
      break;
    case "pendant":
      disk(w * 0.24, 0.02, 0, 0, 0.01);
      disk(0.005, h * 0.7, 0, 0, h * 0.36, detail);
      oval(w, w, w * (count > 1 ? 0.9 : 0.5), 0, 0, h * 0.8, count > 1 ? lens : body);
      break;
    case "sconce":
      disk(w * 0.34, 0.018, 0, 0, 0.01);
      cylinder(w / 2, h, 0, 0, d * 0.45);
      cylinder(w * 0.43, 0.005, 0, -h * 0.5, d * 0.45, lens);
      if (count > 1) cylinder(w * 0.43, 0.005, 0, h * 0.5, d * 0.45, lens);
      break;
    case "basin":
    case "bath": {
      const bowls = count === 3 ? 2 : 1;
      for (let index = 0; index < bowls; index++) {
        const x = ((index + 0.5) / bowls - 0.5) * w;
        const span = w / bowls;
        // Continuous outer shell, rolled rim and actual recessed bowl. No flat
        // dark ellipse pretending to be a cavity. Nominal catalogue envelope retained.
        const bowl=ceramicBowlGeometry(span,h,d);
        const shell=mesh(bowl,x,0,0,body);shell.name="Ceramic bowl shell";
        const drain=cylinder(Math.min(.028,span*.065),.003,x,h*.19+.002,0,detail);
        drain.name="Bowl drain";
        const wasteRadius=Math.min(.028,span*.065);
        const collar=mesh(new THREE.TorusGeometry(wasteRadius*.82,Math.min(.002,wasteRadius*.12),8,24),x,h*.19+.004,0,white);
        collar.rotation.x=-Math.PI/2;collar.name="Waste flange";
        const plug=cylinder(Math.min(.017,span*.04),.004,x,h*.19+.004,0,white);
        plug.name="Waste plug";
      }
      break;
    }
    case "toilet":
      oval(w*.72,h*.38,d*.62,0,h*.19,d*.09);
      const bowl=mesh(ceramicBowlGeometry(w,h*.38,d*.76),0,h*.25,d*.10,body);bowl.name="Recessed toilet bowl";
      const seat=mesh(new THREE.TorusGeometry(1,.10,8,40),0,h*.64,d*.10,white);seat.rotation.x=-Math.PI/2;seat.scale.set(w*.43,d*.33,h*.20);seat.name="Open toilet seat";
      softBox(w*.89,h*.43,d*.31,0,h*.78,-d*.27);
      cylinder(0.018, 0.004, 0, h, -d * 0.27, detail);
      break;
    case "rail":
      for (let index = 0; index < count; index++) {
        const y = ((index + 0.5) / count - 0.5) * h;
        disk(0.014, d, -w * 0.43, y, d * 0.51);
        disk(0.014, d, w * 0.43, y, d * 0.51);
        const rail = cylinder(0.011, w, 0, y, d);
        rail.rotation.z = Math.PI / 2;
      }
      break;
    case "sofa":
      softBox(w*.94,h*.20,d*.9,0,h*.17,0);
      softBox(w*.94,h*.57,d*.18,0,h*.67,-d*.39);
      for(let i=0;i<3;i++){const x=(i-1)*w*.28;softBox(w*.27,h*.19,d*.68,x,h*.40,d*.04);softBox(w*.27,h*.35,d*.13,x,h*.65,-d*.27);}
      for(const sign of [-1,1]){softBox(w*.105,h*.43,d*.91,sign*w*.447,h*.48,0);for(const z of [-1,1])box(.045,.11,.045,sign*w*.43,.055,z*d*.39,detail);}
      break;
    case "bed":
      box(w,h*.26,d,0,h*.19,0,detail);
      softBox(w*.98,h*.27,d*.98,0,h*.45,0,white);
      softBox(w*.98,h*.075,d*.71,0,h*.62,d*.14);
      softBox(w,h*.8,.07,0,h*.60,-d*.48);
      for(const sign of [-1,1])oval(w*.41,.12,d*.22,sign*w*.25,h*.65,-d*.30,white);
      break;
    case "coffee-table":
      cylinder(w*.5,.035,0,h-.0175,0);
      cylinder(w*.30,h-.035,0,(h-.035)/2,0,detail);
      break;
    case "vanity":
    case "cabinet":
    case "bench":
      const plinth=box(w*.91,h*.085,d*.80,0,h*.0425,-d*.06,detail);plinth.name="Recessed cabinet plinth";
      const carcass=box(w,h*.87,d*.94,0,h*.52,-d*.02);carcass.name="Cabinet carcass";
      const topMaterial=h<1.3?white:body;
      worktop=softBox(w*1.018,h*.047,d*1.02,0,h*.9765,0,topMaterial);worktop.name="Bevelled benchtop";
      for (let index = 0; index < count; index++) {
        const x = ((index + 0.5) / count - 0.5) * w;
        const panelWidth=w/count-.009;
        const front=softBox(panelWidth,h*.82,.018,x,h*.515,d*.5);front.name="Radiused cabinet front";
        // Recessed panel reveal and physical pull with two mounting posts.
        const pull=Math.min(.16,panelWidth*.48);
        const handle=softBox(pull,.012,.016,x,h*.79,d*.5+.029,detail);handle.name="Cabinet pull";
        for(const sign of [-1,1])box(.012,.012,.025,x+sign*pull*.36,h*.79,d*.5+.015,detail);
        if(h<1.3)box(panelWidth*.88,.004,.003,x,h*.68,d*.5+.010,detail);
      }
      if (h >= 1.3) worktop = undefined;
      break;
  }
  if(shape==="sofa"||shape==="bed")applyFixtureFabric(group,shape==="bed"?[body,white]:[body]);
  const used = new Set(group.children.flatMap(part => part instanceof THREE.Mesh ? [part.material] : []));
  for (const material of [body, detail, white, lens]) if (!used.has(material)) material.dispose();
  return { group, worktop };
}

/** Bounded, closed ring shell, suitable for a bath or basin without a costly CSG pass. */
export function ceramicBowlGeometry(w:number,h:number,d:number){
 const rings:[[number,number],[number,number],[number,number],[number,number],[number,number],[number,number],[number,number],[number,number]]=[[.001,0],[.72,0],[.94,.18],[1,.93],[.98,1],[.88,.97],[.65,.24],[.001,.19]];
 const segments=40,positions:number[]=[],indices:number[]=[];
 for(const [radius,y] of rings)for(let i=0;i<segments;i++){const t=i*2*Math.PI/segments;positions.push(Math.cos(t)*w*.5*radius,y*h,Math.sin(t)*d*.5*radius);}
 for(let j=0;j<rings.length-1;j++)for(let i=0;i<segments;i++){const n=(i+1)%segments,a=j*segments+i,b=j*segments+n,c=(j+1)*segments+i,e=(j+1)*segments+n;indices.push(a,c,b,b,c,e);}
 // Close tiny centre holes at the bottom and inside the bowl.
 const bottom=positions.length/3;positions.push(0,0,0);const inner=positions.length/3;positions.push(0,h*.19,0);
 for(let i=0;i<segments;i++){const n=(i+1)%segments;indices.push(bottom,i,n,inner,(rings.length-1)*segments+n,(rings.length-1)*segments+i);}
 const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.Float32BufferAttribute(positions,3));g.setIndex(indices);g.computeVertexNormals();return g;
}
