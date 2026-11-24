import type {MenuLayout} from "./catalogueMenu.ts";
/** Hit the entire visible sector, not just its text rectangle. */
export function radialSector(x:number,y:number):number {
 if(!Number.isFinite(x)||!Number.isFinite(y))return -1;
 const radius=Math.hypot(x,y);
 if(radius<.29)return 8;
 if(radius>1.04)return -1;
 return ((Math.round((Math.atan2(y,x)+Math.PI/2)/(Math.PI/4))%8)+8)%8;
}
export function thumbstickSector(stick:readonly [number,number]):number {
 const n=Math.hypot(...stick);
 return n>=.45?radialSector(stick[0]/n,stick[1]/n):-1;
}
export function menuButtonAt(layout:MenuLayout,x:number,y:number):number {
 if(!Number.isFinite(x)||!Number.isFinite(y))return -1;
 if(layout.radial){
  const i=radialSector((x-layout.width/2)/(layout.width/2),(y-layout.height/2)/(layout.height/2));
  return i>=0&&layout.buttons[i]&&!layout.buttons[i].disabled?i:-1;
 }
 // A little forgiveness around rectangular buttons; never select through a
 // disabled button or jump to a neighbouring active button on its behalf.
 const direct=layout.buttons.findIndex(b=>x>=b.x&&x<=b.x+b.w&&y>=b.y&&y<=b.y+b.h);
 if(direct>=0)return layout.buttons[direct].disabled?-1:direct;
 let best=-1,distance=Infinity;
 for(let i=0;i<layout.buttons.length;i++){
  const b=layout.buttons[i];
  const d=Math.hypot(Math.max(b.x-x,0,x-b.x-b.w),Math.max(b.y-y,0,y-b.y-b.h));
  if(d<distance){best=i;distance=d;}
 }
 return distance<=12&&best>=0&&!layout.buttons[best].disabled?best:-1;
}
