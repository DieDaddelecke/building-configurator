import "./styles.css";
import "../../i18n";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AnalyseApp } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AnalyseApp />
  </StrictMode>,
);
