import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Shell } from "./components/Shell";
import { Landing } from "./landing/Landing";
// The stylesheet of the viewer modules (for the 3-D ground view), then the look of this site.
import "../../viewer/viewer.css";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Shell page="home"><Landing /></Shell>
  </StrictMode>,
);
