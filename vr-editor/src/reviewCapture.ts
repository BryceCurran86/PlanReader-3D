/** Explicit user-initiated evidence VIEW capture.
 * Watermark is mandatory. Images are presentation only, never source witnesses.
 */
import type { SceneManifest } from "./types";

export interface CaptureStamp {
  title: string; subtitle: string; filename: string; warning: string;
}
function safePart(value:string):string{
  return value.replace(/[^A-Za-z0-9_-]/g,"-").slice(0,48)||"unknown";
}
export function reviewStamp(scene:SceneManifest, visibleCount:number):CaptureStamp{
  const s=scene.scope;
  const count=Number.isSafeInteger(visibleCount)&&visibleCount>=0?visibleCount:0;
  return {
    title:"PLANREADER · VR VISUAL REVIEW",
    subtitle:`Project ${s.projectId.slice(0,64)} | Drawing ${s.documentId.slice(0,64)} | Rev ${s.revisionId.slice(0,32)} | Snapshot ${s.snapshotId.slice(0,32)} | Visible ${count}`,
    filename:`planreader-review-${safePart(s.projectId)}-${safePart(s.snapshotId)}.png`,
    warning:"ILLUSTRATIVE VIEW ONLY · NOT A SOURCE MEASUREMENT OR APPROVED QUOTE",
  };
}
export function safeCaptureSize(width:number,height:number):[number,number]|null{
  if(!Number.isFinite(width)||!Number.isFinite(height)||width<1||height<1)return null;
  const scale=Math.min(1,4096/width,4096/height);
  const w=Math.floor(width*scale),h=Math.floor(height*scale);
  return w>=1&&h>=1?[w,h]:null;
}
export function drawReviewStamp(
  ctx:CanvasRenderingContext2D,width:number,height:number,stamp:CaptureStamp,
):void{
  // Keep footer at least 22 px and never obscure entire frame on mobile.
  const bar=Math.min(92,Math.max(35,Math.round(height*0.13)));
  ctx.save();
  ctx.fillStyle="rgba(8,17,24,0.88)";
  ctx.fillRect(0,height-bar,width,bar);
  ctx.fillStyle="#f9d19b";
  ctx.font=`bold ${Math.max(9,Math.min(16,Math.floor(width/50)))}px sans-serif`;
  ctx.fillText(stamp.warning.slice(0,100),12,height-bar+23,Math.max(1,width-24));
  ctx.font=`${Math.max(8,Math.min(13,Math.floor(width/75)))}px sans-serif`;
  ctx.fillStyle="#f0f7fc";
  ctx.fillText(stamp.title.slice(0,90),12,height-bar+42,Math.max(1,width-24));
  ctx.fillText(stamp.subtitle.slice(0,230),12,height-bar+61,Math.max(1,width-24));
  ctx.restore();
}
