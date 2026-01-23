import { PublicClientApplication, EventType, EventMessage, AuthenticationResult } from "@azure/msal-browser";
import { msalConfig } from "../config/authConfig";

export const msalInstance = new PublicClientApplication(msalConfig);

export const initializeMsal = async (): Promise<void> => {
  await msalInstance.initialize();

  // Handle redirect response if any
  const response = await msalInstance.handleRedirectPromise();
  if (response) {
    msalInstance.setActiveAccount(response.account);
  } else {
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
