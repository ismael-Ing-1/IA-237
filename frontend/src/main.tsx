import React from "react";
import ReactDOM from "react-dom/client";

import "@xyflow/react/dist/style.css";
import "./styles/globals.css";

import App from "./app/App";
import { AppProviders } from "./app/providers";
import { WebSocketBootstrap } from "./websocket";


const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error(
    'Root element with id "root" was not found.',
  );
}


ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <AppProviders>
      <WebSocketBootstrap />
      <App />
    </AppProviders>
  </React.StrictMode>,
);
