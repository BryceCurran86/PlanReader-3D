import type {CatalogueItem,CatalogueGroup} from "./itemCatalogue.ts";
import {showConstructionItem,showConstructionSurface} from "./constructionStages.ts";
import type {ConstructionStage} from "./constructionStages.ts";
export const CONSTRUCTION_LAYERS=[
 ["floor","Slab / floors"],["wall","Wall bodies"],["framing","Framing"],["insulation","Insulation (illustrative)"],
 ["ceiling","Ceilings"],["roof","Roof"],["envelope","Exterior cladding / masonry finishes"],
 ["lining","Wall linings"],["openings","Doors and windows"],["electrical","Electrical rough-in"],
 ["plumbing","Plumbing rough-in"],["air","Air-conditioning rough-in"],
 ["finishes","Paint / floor finishes / trims"],["fixtures","Fixtures and fittings"],["site","Site and landscape"],
] as const;
export type ConstructionLayer=typeof CONSTRUCTION_LAYERS[number][0];
export type LayerMode="auto"|"show"|"hide";
export type LayerOverrides=Partial<Record<ConstructionLayer,LayerMode>>;
export const EMPTY_LAYERS:LayerOverrides=Object.freeze({});
export function layerVisible(layers:LayerOverrides,layer:ConstructionLayer,automatic:boolean){
 const mode=layers[layer]??"auto";
 return mode==="auto"?automatic:mode==="show";
}
export function cycleLayer(layers:LayerOverrides,layer:ConstructionLayer):LayerOverrides{
 const mode=layers[layer]??"auto";return {...layers,[layer]:mode==="auto"?"show":mode==="show"?"hide":"auto"};
}
const GROUP_LAYER:Partial<Record<CatalogueGroup,ConstructionLayer>>={
 paint:"finishes",boards:"lining",skirting:"finishes",architraves:"finishes",floors:"finishes",walls:"finishes",
 tapware:"fixtures",electrical:"fixtures",lights:"fixtures",bathroom:"fixtures",cabinets:"fixtures",doors:"openings",
 timber:"framing",entry:"openings",substrates:"envelope",facades:"envelope",decking:"site",soffits:"envelope",
 roofing:"roof","roof-components":"roof","plumbing-rough-in":"plumbing","electrical-rough-in":"electrical",
 "air-conditioning":"air",stairs:"framing",balustrading:"fixtures","sliding-doors":"openings",windows:"openings",
 "window-coverings":"fixtures",flyovers:"envelope",pools:"site",landscaping:"site"
};
export function itemLayer(item:CatalogueItem):ConstructionLayer{return GROUP_LAYER[item.group]??"fixtures";}
export function itemLayerVisible(stage:ConstructionStage,item:CatalogueItem,layers:LayerOverrides){
 return layerVisible(layers,itemLayer(item),showConstructionItem(stage,item));
}
export function surfaceLayerVisible(stage:ConstructionStage,kind:"floor"|"ceiling"|"roof"|undefined,layers:LayerOverrides,elevated=false){
 // A cutaway must remain clear, even when roof visibility is explicitly on.
 if(elevated&&(kind==="roof"||kind==="ceiling"))return false;
 return layerVisible(layers,kind??"wall",showConstructionSurface(stage,kind));
}
