import React from "react";
import ReactDOM from "react-dom/client";
import { MsalProvider } from "@azure/msal-react";
import { msalInstance, initializeMsal } from "./auth/msalInstance";

import "./index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);

// Wait for MSAL to initialize before rendering
initializeMsal().then(() => {
  root.render(
    <React.StrictMode>
      <MsalProvider instance={msalInstance}>
        <App />
      </MsalProvider>
    </React.StrictMode>
  );
});

reportWebVitals();
