import { createRoot } from "react-dom/client";
import { Shell } from "./components/Layout";
import { Compare } from "./pages/Compare";
// The stylesheet of the viewer modules (status cards, charts, calendar, ground view), then the
// look of this site on top of it.
import "../../viewer/viewer.css";
import "./styles.css";
import "./compare.css";

// No StrictMode here: the comparison module fills the page once, outside React.
createRoot(document.getElementById("root")!).render(
  <Shell page="compare"><Compare /></Shell>,
);
