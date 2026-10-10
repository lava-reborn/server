import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { configure } from "./api";
import { setHost } from "./theme";

// Inside the admin panel the page is <div id="quest-editor" class="qe">,
// whose data-api, data-icons, data-token and data-who say where the API and
// the item icons are, the panel's CSRF token and who is signed in. The
// standalone page (tools/quest_editor.py) has #root and the defaults, and
// carries the panel's tokens itself (.qe-alone).
const host = (document.getElementById("quest-editor") || document.getElementById("root"))!;
const d = host.dataset;
configure({ api: d.api || "/api", icons: d.icons || "/icon/", token: d.token || "", who: d.who || "" });
host.classList.add("qe");
if (host.id !== "quest-editor") host.classList.add("qe-alone");
setHost(host);

createRoot(host).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
