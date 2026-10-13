import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { configure } from "./api";
import "./styles.css";

// Inside the admin panel the page is <div id="location-editor">, whose
// data-api, data-img, data-token and data-who say where the editor's API
// and its art cache are (/admin/locations/api, /admin/locations/img), the
// panel's form token and who is signed in. The standalone page
// (tools/location_editor.py, #root) has the defaults: /api and /art on the
// same origin, and is the whole window (.le-alone).
const panel = document.getElementById("location-editor");
const host = (panel || document.getElementById("root"))!;
const d = host.dataset;
configure({ api: d.api || "/api", img: d.img || "/art", token: d.token || "", who: d.who || "", panel: !!panel });
host.classList.add("le");
if (!panel) host.classList.add("le-alone");
createRoot(host).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
