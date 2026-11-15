import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Shell } from "./components/Layout";
import { Landing } from "./pages/Landing";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Shell page="home"><Landing /></Shell>
  </StrictMode>,
);
