/** Fixed GPU backing size across all logical menu panels, including radial. */
export const MENU_ATLAS_SIZE=1024;
export function menuAtlasScale(width:number,height:number):[number,number]|null{
 if(!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)return null;
 return [MENU_ATLAS_SIZE/width,MENU_ATLAS_SIZE/height];
}
