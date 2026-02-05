import { useCallback } from "react";
import { useMsal, useAccount } from "@azure/msal-react";
import { InteractionRequiredAuthError, BrowserAuthError, InteractionStatus, CacheLookupPolicy } from "@azure/msal-browser";
import { loginRequest, apiConfig, graphConfig } from "../config/authConfig";

export const useAuth = () => {
  const { instance, accounts, inProgress } = useMsal();
  const account = useAccount(accounts[0] || {});

  const login = useCallback(async () => {
    if (inProgress !== InteractionStatus.None) {
      return;
    }
    try {
      await instance.loginRedirect(loginRequest);
    } catch (error) {
      console.error("Login failed:", error);
      throw error;
    }
  }, [instance, inProgress]);

  const logout = useCallback(async () => {
    if (inProgress !== InteractionStatus.None) {
      return;
    }
    try {
      await instance.logoutRedirect({
        postLogoutRedirectUri: "/",
        // mainWindowRedirectUri is not needed for redirect flow
      });
    } catch (error) {
      console.error("Logout failed:", error);
      throw error;
    }
  }, [instance, inProgress]);

  const getAccessToken = useCallback(async (scopes: string[] = loginRequest.scopes) => {
    if (!account) {
      throw new Error("No active account");
    }

    // Check if MSAL is ready for token acquisition
    if (inProgress !== InteractionStatus.None) {
      // MSAL is still initializing (e.g., handling redirect after page refresh)
      // Return null so caller can handle gracefully
      return null;
    }

    try {
      const response = await instance.acquireTokenSilent({
        scopes,
        account,
        cacheLookupPolicy: CacheLookupPolicy.AccessTokenAndRefreshToken,
      });
      return response.accessToken;
    } catch (error) {
      if (error instanceof InteractionRequiredAuthError) {
        // Session expired — redirect to Azure AD to re-authenticate.
        // This is a full page navigation (not an iframe or popup).
        await instance.acquireTokenRedirect({ scopes });
        return null;
      }
      // Handle transient MSAL errors - return null so caller can retry
      if (error instanceof BrowserAuthError) {
        if (
          error.errorCode === "block_iframe_reload" ||
          error.errorCode === "block_nested_popups" ||
          error.errorCode === "popup_window_error"
        ) {
          return null;
        }
      }
      throw error;
    }
  }, [instance, account, inProgress]);

  const getApiAccessToken = useCallback(async () => {
    return getAccessToken(apiConfig.scopes);
  }, [getAccessToken]);

  const fetchUserProfile = useCallback(async () => {
    const token = await getAccessToken();
    const response = await fetch(graphConfig.graphMeEndpoint, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error("Failed to fetch user profile");
    }

    return response.json();
  }, [getAccessToken]);

  return {
    account,
    isAuthenticated: !!account,
    inProgress,
    login,
    logout,
    getAccessToken,
    getApiAccessToken,
    fetchUserProfile,
  };
};
