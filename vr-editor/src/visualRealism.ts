/** Render-only photometric controls for source-bound wall evidence.
 * These settings NEVER alter metres, geometry, source authority or quantities.
 * Ground/sky are deliberately marked as presentation context, not source BIM.
 */
export type LightingMood = "daylight" | "studio" | "dusk" | "night";
export type RenderQuality = "performance" | "balanced" | "high";
export interface VisualPreset {
  label: string;
  background: number;
  ambientSky: number;
  ambientGround: number;
  ambientIntensity: number;
  sunColor: number;
  sunIntensity: number;
  sunPosition: readonly [number, number, number];
  exposure: number;
  materialRoughness: number;
}
export const VISUAL_PRESETS: Readonly<Record<LightingMood, Readonly<VisualPreset>>> = {
  daylight: {
    label: "Architectural daylight (illustrative)",
    background: 0xc6d9e5, ambientSky: 0xe9f0fa, ambientGround: 0x8d887d,
    ambientIntensity: 1.1, sunColor: 0xfff5e7, sunIntensity: 2.7,
    sunPosition: [9, 12, 7], exposure: 0.92, materialRoughness: 0.78,
  },
  studio: {
    label: "Neutral model studio (illustrative)",
    background: 0x182934, ambientSky: 0xd9ebf7, ambientGround: 0x667782,
    ambientIntensity: 2.3, sunColor: 0xf7fbff, sunIntensity: 2.0,
    sunPosition: [-8, 17, 11], exposure: 0.92, materialRoughness: 0.83,
  },
  night: {
    label: "Night · local fixture preview (illustrative)",
    background: 0x121b2c, ambientSky: 0x8d9ac2, ambientGround: 0x45424d,
    ambientIntensity: .24, sunColor: 0xb5c9ff, sunIntensity: .08,
    sunPosition: [16, 12, 5], exposure: 1.0, materialRoughness: .88,
  },
  dusk: {
    label: "Warm evening light (illustrative)",
    background: 0x354358, ambientSky: 0x849ac1, ambientGround: 0x574d48,
    ambientIntensity: 1.5, sunColor: 0xffc18c, sunIntensity: 2.2,
    sunPosition: [16, 9, 5], exposure: 0.91, materialRoughness: 0.91,
  },
};

export function isLightingMood(v: unknown): v is LightingMood {
  return typeof v === "string" && Object.hasOwn(VISUAL_PRESETS, v);
}
export function isRenderQuality(v: unknown): v is RenderQuality {
  return v === "performance" || v === "balanced" || v === "high";
}
export function maxRenderPixelRatio(quality: RenderQuality, isXR: boolean): number {
  // Headset compositor controls its own size; don't add an expensive desktop multiplier.
  return isXR ? 1 : quality === "high" ? 2 : quality==="performance"?1:1.5;
}
export function shadowMapSize(quality: RenderQuality): number {
  return quality === "high" ? 2048 : quality==="performance"?512:1024;
}
/** Only authentic existing wall faces with stated heights may be lit as surfaces. */
export function mayRenderWallFace(
  kind: string | null | undefined, heightM: number | null | undefined,
): boolean {
  return kind === "wallFace" && typeof heightM === "number" &&
    Number.isFinite(heightM) && heightM > 0 && heightM < 1000;
}

export function realismBudget(quality:RenderQuality,xr:boolean){
 return {detail:quality!=="performance",landscape:quality!=="performance",shadows:quality!=="performance",shadowRefreshMs:xr?1000:100,environmentIntensity:quality==="performance"?.45:quality==="high"?.85:.65};
}

/** Runtime cap below the user's selected quality; never raise above it. */
export function adaptiveRenderQuality(requested:RenderQuality,cap:number):RenderQuality{
 const levels:RenderQuality[]=["performance","balanced","high"];
 return levels[Math.min(levels.indexOf(requested),Math.max(0,Math.min(2,Math.floor(cap))))]??requested;
}

/** Bounded shadow frustum around actual editable house. */
export function architecturalShadowExtent(width:number,depth:number):number{
 if(!Number.isFinite(width)||!Number.isFinite(depth)||width<=0||depth<=0)return 12;
 return Math.min(150,Math.max(6,Math.hypot(width,depth)*.68+2));
}

/** Desktop frame pacing leaves time for DOM input, source loading and layout.
 * XR remains completely under the headset compositor's native frame schedule. */
export function shouldRenderDesktopFrame(now:number,last:number,quality:RenderQuality,isXR:boolean){
 if(isXR||!Number.isFinite(last)||now<last)return true;
 return now-last>= (quality==="performance"?1000/30:1000/45)-1;
}

/** Desktop-only render governor. Slow rendering must leave a real idle window
 * for UI events and loading, not merely request another frame at 60 Hz.
 * Hysteresis prevents oscillation and never exceeds the selected quality. */
export class DesktopRenderGovernor {
 cap=2;
 private nextAt=-Infinity;
 private previous=-Infinity;
 private slow=0;
 private fast=0;
 private requested:RenderQuality|null=null;
 allow(now:number,requested:RenderQuality,paused:boolean){
  if(paused){this.previous=-Infinity;this.nextAt=-Infinity;return false;}
  if(this.requested!==requested){this.requested=requested;this.reset();}
  return now>=this.nextAt;
 }
 complete(now:number,elapsed:number){
  if(!Number.isFinite(now)||!Number.isFinite(elapsed)||elapsed<0)return;
  const gap=now-this.previous;this.previous=now;
  const overloaded=elapsed>36||Number.isFinite(gap)&&gap>110;
  const healthy=elapsed<15&&gap<65;
  this.slow=overloaded?this.slow+1:0;this.fast=healthy?this.fast+1:0;
  // A single pathological desktop frame can block DOM input for seconds.
  // Drop expensive shadows/detail immediately rather than demanding two more.
  if(elapsed>=250){this.cap=0;this.slow=this.fast=0;}
  else if(elapsed>=100||this.slow>=3){this.cap=Math.max(0,this.cap-1);this.slow=0;this.fast=0;}
  else if(this.fast>=90){this.cap=Math.min(2,this.cap+1);this.fast=0;}
  const interval=this.requested==="performance"||this.cap===0?1000/30:1000/45;
  // Reserve an actual event-processing interval after an expensive frame.
  this.nextAt=now+Math.max(interval,elapsed+Math.min(1000,Math.max(8,elapsed*.85)))-1;
 }
 idle(){this.previous=-Infinity;}
 reset(){this.cap=2;this.nextAt=this.previous=-Infinity;this.slow=this.fast=0;}
}

/** Demand rendering in desktop mode only. A bounded heartbeat presents async
 * texture updates and delayed shadows even when input references are stable. */
export class DesktopFrameDemand {
 private last:readonly unknown[]=[];
 private lastDraw=-Infinity;
 shouldDraw(now:number,key:readonly unknown[],continuous=false){
  const changed=key.length!==this.last.length||key.some((v,i)=>!Object.is(v,this.last[i]));
  if(!continuous&&!changed&&now-this.lastDraw<500)return false;
  this.last=[...key];this.lastDraw=now;return true;
 }
 reset(){this.last=[];this.lastDraw=-Infinity;}
}
