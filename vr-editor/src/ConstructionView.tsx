import { useState } from "react";
import { CONSTRUCTION_STAGES, stageDetails } from "./constructionStages";
import type { ConstructionStage } from "./constructionStages";
import { CONSTRUCTION_LAYERS } from "./constructionLayers";
import type {LayerOverrides,LayerMode} from "./constructionLayers";
import { CONSTRUCTION_REFERENCES, NCC_ADOPTION, NCC_REFERENCES } from "./constructionStandards";

export function ConstructionView({ stage, onStage }: { stage: ConstructionStage; onStage: (stage: ConstructionStage) => void }) {
  return <label className="stage-select">View
    <select value={stage} onChange={event => onStage(event.currentTarget.value as ConstructionStage)}
      title={stageDetails(stage).description}>
      {CONSTRUCTION_STAGES.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
    </select>
  </label>;
}

export function ConstructionLayerPanel({layers,onLayers}:{layers:LayerOverrides;onLayers:(layers:LayerOverrides)=>void}){
 return <details className="construction-standards">
 <summary>Construction layers</summary>
 <p>Auto follows the stage. Show or hide a layer independently; bird’s-eye cutaway still hides roof and ceilings.</p>
 <p>Plasterboard stages show nominal finishes on eligible verified source faces and ceilings (bounded preview), not verified material specifications. Framing is shown for editable draft assemblies; a source wall face alone does not identify framing. Source opening markers are review evidence, not wall cutouts.</p>
 <button type="button" onClick={()=>onLayers({})}>Reset to stage defaults</button>
 {CONSTRUCTION_LAYERS.map(([id,label])=><label key={id}>{label}
 <select value={layers[id]??"auto"} onChange={e=>onLayers({...layers,[id]:e.currentTarget.value as LayerMode})}>
 <option value="auto">Auto</option><option value="show">Show</option><option value="hide">Hide</option>
 </select></label>)}
 </details>;
}
export function StandardsPanel() {
  const [region, setRegion] = useState("");
  const [classification, setClassification] = useState("");
  return <details className="construction-standards">
    <summary>Australian standards</summary>
    <div className="standards-filters">
      <label>Jurisdiction
        <select value={region} onChange={event => setRegion(event.currentTarget.value)}>
          <option value="">Select</option>
          {["ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"].map(value => <option key={value}>{value}</option>)}
        </select>
      </label>
      <label>Building class
        <select value={classification} onChange={event => setClassification(event.currentTarget.value)}>
          <option value="">Select</option>
          <option value="housing">Class 1 or 10</option>
          <option value="other">Class 2 to 9 or mixed</option>
        </select>
      </label>
    </div>
    {region === "QLD" && <p>Queensland lists NCC 2022 until 30 April 2027 and NCC 2025 from 1 May 2027. <a href={NCC_ADOPTION} target="_blank" rel="noreferrer">Queensland adoption dates</a></p>}
    <p>Confirm the project approval date, variations and referenced editions with the relevant certifier or trade. The editor records design choices and references for review.</p>
    {classification === "other"
      ? <p>Use the applicable volume and project-specific pathway. <a href={NCC_REFERENCES} target="_blank" rel="noreferrer">National Construction Code editions</a></p>
      : <ul>{CONSTRUCTION_REFERENCES.map(reference => <li key={reference.area}>
        <strong>{reference.area}</strong> · {reference.scope}
        <div>{reference.documents}</div>
        <div>{reference.evidence} <a href={reference.url} target="_blank" rel="noreferrer">Reference</a></div>
      </li>)}</ul>}
  </details>;
}
