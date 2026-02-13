import { Configuration, LogLevel } from "@azure/msal-browser";
import { appConfig } from "./appConfig";

// Azure AD App Registration Configuration
export const msalConfig: Configuration = {
  auth: {
    clientId: appConfig.auth.clientId,
    authority: appConfig.auth.authority,
    redirectUri: appConfig.auth.redirectUri,
    postLogoutRedirectUri: appConfig.auth.redirectUri,
  },
  cache: {
    cacheLocation: "localStorage",
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) {
          return;
        }
        switch (level) {
          case LogLevel.Error:
            console.error(message);
            return;
          case LogLevel.Info:
            console.info(message);
            return;
          case LogLevel.Verbose:
            console.debug(message);
            return;
          case LogLevel.Warning:
            console.warn(message);
            return;
        }
      },
      logLevel: LogLevel.Warning,
    },
  },
};

// Scopes for Microsoft Graph API
export const loginRequest = {
  scopes: appConfig.auth.loginScopes,
};

// Scopes for your FastAPI backend
export const apiConfig = {
  scopes: appConfig.auth.apiScopes,
};

