import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from "react";
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { useAuth } from "../auth/useAuth";
import { appConfig } from "../config/appConfig";

interface AccessState {
    hasChatAccess: boolean;
    hasDashboardAccess: boolean;
    hasPipelinesIngestionAccess: boolean;
    user: string;
    isLoading: boolean;
    error: string | null;
}

const AccessControlContext = createContext<AccessState>({
    hasChatAccess: false,
    hasDashboardAccess: false,
    hasPipelinesIngestionAccess: false,
    user: "",
    isLoading: true,
    error: null,
});

export const useAccessControl = () => useContext(AccessControlContext);

export const AccessControlProvider = ({ children }: { children: ReactNode }) => {
    const { inProgress } = useMsal();
    const isAuthenticated = useIsAuthenticated();
    const { getApiAccessToken } = useAuth();

    const [accessState, setAccessState] = useState<AccessState>({
        hasChatAccess: false,
        hasDashboardAccess: false,
        hasPipelinesIngestionAccess: false,
        user: "",
        isLoading: true,
        error: null,
    });

    // Use refs to access latest values in async callbacks
    const inProgressRef = useRef(inProgress);
    const isAuthenticatedRef = useRef(isAuthenticated);
    const getApiAccessTokenRef = useRef(getApiAccessToken);
    const fetchSucceededRef = useRef(false);

    // Keep refs updated
    useEffect(() => {
        inProgressRef.current = inProgress;
        isAuthenticatedRef.current = isAuthenticated;
        getApiAccessTokenRef.current = getApiAccessToken;
    });

    useEffect(() => {
        let cancelled = false;
        let timeoutId: NodeJS.Timeout | null = null;

        const fetchWithRetry = async (retryCount: number = 0): Promise<void> => {
            const maxRetries = 20; // 20 * 200ms = 4 seconds max wait

            if (cancelled || fetchSucceededRef.current) {
                return;
            }

            // Use refs to get latest values
            const currentInProgress = inProgressRef.current;
            const currentIsAuthenticated = isAuthenticatedRef.current;
            const currentGetToken = getApiAccessTokenRef.current;

            // MSAL is still initializing - wait and retry
            if (currentInProgress !== InteractionStatus.None) {
                if (retryCount < maxRetries) {
                    timeoutId = setTimeout(() => fetchWithRetry(retryCount + 1), 200);
                } else {
                    if (!cancelled) {
                        setAccessState(prev => ({
                            ...prev,
                            isLoading: false,
                            error: "Authentication timeout - please refresh the page",
                        }));
                    }
                }
                return;
            }

            // Not authenticated - not an error, just stop loading
            if (!currentIsAuthenticated) {
                if (!cancelled) {
                    setAccessState(prev => ({ ...prev, isLoading: false }));
                }
                return;
            }

            // Try to get token
            let token: string | null = null;
            try {
                token = await currentGetToken();
            } catch (err) {
                console.warn("Token acquisition error:", err);
            }

            if (cancelled) return;

            if (!token) {
                // Token not ready, retry
                if (retryCount < maxRetries) {
                    timeoutId = setTimeout(() => fetchWithRetry(retryCount + 1), 200);
                } else {
                    setAccessState(prev => ({
                        ...prev,
                        isLoading: false,
                        error: "Failed to acquire authentication token",
                    }));
                }
                return;
            }

            // Fetch access from backend
            try {
                const response = await fetch(`${appConfig.api.baseUrl}/api/auth/access`, {
                    headers: { "X-MS-TOKEN-AAD": token },
                });

                if (cancelled) return;

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const data = await response.json();
                fetchSucceededRef.current = true;

                if (!cancelled) {
                    setAccessState({
                        hasChatAccess: data.hasChatAccess,
                        hasDashboardAccess: data.hasDashboardAccess,
                        hasPipelinesIngestionAccess: data.hasPipelinesIngestionAccess,
                        user: data.user,
                        isLoading: false,
                        error: null,
                    });
                }
            } catch (err: any) {
                console.error("Access control check failed:", err);
                if (!cancelled) {
                    setAccessState(prev => ({
                        ...prev,
                        isLoading: false,
                        error: err.message || "Failed to verify access",
                    }));
                }
            }
        };

        // Start fetching if we haven't succeeded yet
        if (!fetchSucceededRef.current) {
            fetchWithRetry(0);
        }

        return () => {
            cancelled = true;
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
        };
    }, []); // Empty deps - we use refs to access current values

    return (
        <AccessControlContext.Provider value={accessState}>
            {children}
        </AccessControlContext.Provider>
    );
};
