/** Nominal editable local design assemblies, not an Australian Standards specification.
 * Source wall faces remain unclassified until supported by actual evidence. */
export const WALL_PROFILES=[
 {id:"internal-timber",label:"Internal timber frame",role:"internal",core:"timber",thicknessMm:116,frameMm:90,outerColor:0xeeeae1},
 {id:"internal-steel",label:"Internal steel frame",role:"internal",core:"steel",thicknessMm:116,frameMm:90,outerColor:0xeeeae1},
 {id:"external-timber",label:"External timber + cladding",role:"external",core:"timber",thicknessMm:140,frameMm:90,outerColor:0xaaa79b},
 {id:"external-steel",label:"External steel + cladding",role:"external",core:"steel",thicknessMm:140,frameMm:90,outerColor:0x879aa1},
 {id:"brick-veneer-timber",label:"Brick veneer / timber frame",role:"external",core:"timber",thicknessMm:253,frameMm:90,outerColor:0xa75e48},
 {id:"brick-veneer-steel",label:"Brick veneer / steel frame",role:"external",core:"steel",thicknessMm:253,frameMm:90,outerColor:0xa75e48},
 {id:"double-brick",label:"Double brick",role:"external",core:"masonry",thicknessMm:270,frameMm:0,outerColor:0xa75e48},
 {id:"blockwork",label:"Concrete blockwork",role:"external",core:"masonry",thicknessMm:190,frameMm:0,outerColor:0x90918b},
 {id:"concrete",label:"Solid concrete",role:"external",core:"masonry",thicknessMm:150,frameMm:0,outerColor:0xa6a6a0},
] as const;
export type WallProfileId=typeof WALL_PROFILES[number]["id"];
export type WallAssembly={profile:WallProfileId;thicknessMm:number;exteriorSide:"left"|"right"};
export function isWallAssembly(value:unknown):value is WallAssembly{
 if(!value||typeof value!=="object")return false;
 const a=value as WallAssembly;
 return WALL_PROFILES.some(p=>p.id===a.profile)&&Number.isInteger(a.thicknessMm)&&a.thicknessMm>=50&&a.thicknessMm<=600&&["left","right"].includes(a.exteriorSide);
}
export function defaultWallAssembly(profile:WallProfileId="internal-timber"):WallAssembly{
 const p=WALL_PROFILES.find(p=>p.id===profile)??WALL_PROFILES[0];
 return {profile:p.id,thicknessMm:p.thicknessMm,exteriorSide:"left"};
}
export function wallAssembly(value:unknown):WallAssembly{
 return isWallAssembly(value)?value:defaultWallAssembly();
}
export function profileDetails(value:unknown){
 const a=wallAssembly(value);
 return WALL_PROFILES.find(p=>p.id===a.profile)!;
}
export function wallDimensionText(lengthM:number,heightM:number,assembly:unknown){
 return `${Math.round(lengthM*1000)} × ${Math.round(heightM*1000)} × ${wallAssembly(assembly).thicknessMm} mm`;
}
