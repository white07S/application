import { PublicClientApplication, EventType, EventMessage, AuthenticationResult } from "@azure/msal-browser";
import { msalConfig } from "../config/authConfig";

export const msalInstance = new PublicClientApplication(msalConfig);

export const initializeMsal = async (): Promise<void> => {
  // Clear stale redirect error hashes before MSAL processes them.
  // Since we use popup for token renewal, any error hash in the URL is
  // leftover from a previous redirect flow and causes no_token_request_cache_error.
  if (window.location.hash.includes("error=")) {
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }

  await msalInstance.initialize();

  // Handle redirect response (loginRedirect still uses this path)
  try {
    const response = await msalInstance.handleRedirectPromise();
    if (response) {
      msalInstance.setActiveAccount(response.account);
    }
  } catch (error) {
    console.warn("handleRedirectPromise failed, clearing stale interaction state:", error);
    // Clear orphaned MSAL interaction/request entries from localStorage
    Object.keys(localStorage).forEach((key) => {
      if (key.startsWith("msal.") && (key.includes(".request.") || key.includes(".interaction"))) {
        localStorage.removeItem(key);
      }
    });
  }

  // Always fall back to setting active account from cache
  if (!msalInstance.getActiveAccount()) {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0]);
    }
  }

  // Listen for sign-in event and set active account
  msalInstance.addEventCallback((event: EventMessage) => {
    if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
      const payload = event.payload as AuthenticationResult;
      msalInstance.setActiveAccount(payload.account);
    }
  });
};
