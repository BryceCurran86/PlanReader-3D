import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./style.css";

const target = document.getElementById("root");
if (!target) throw new Error("Missing PlanReader root");
createRoot(target).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
