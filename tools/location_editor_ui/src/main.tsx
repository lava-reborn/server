import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

const host = document.getElementById("root")!;
host.classList.add("le");
createRoot(host).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
