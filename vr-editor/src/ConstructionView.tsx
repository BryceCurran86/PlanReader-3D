import { useState } from "react";
import { CONSTRUCTION_STAGES, stageDetails } from "./constructionStages";
import type { ConstructionStage } from "./constructionStages";
import { CONSTRUCTION_REFERENCES, NCC_ADOPTION, NCC_REFERENCES } from "./constructionStandards";

export function ConstructionView({ stage, onStage }: { stage: ConstructionStage; onStage: (stage: ConstructionStage) => void }) {
  return <div className="construction-view">
    <details>
      <summary>View · {stageDetails(stage).label}</summary>
      <div className="construction-stage-actions" aria-label="Construction stage">
        {CONSTRUCTION_STAGES.map(option => <button key={option.id} type="button"
          aria-pressed={stage === option.id} onClick={() => onStage(option.id)}>{option.label}</button>)}
      </div>
      <p>{stageDetails(stage).description}</p>
    </details>
    <StandardsPanel />
  </div>;
}

function StandardsPanel() {
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
