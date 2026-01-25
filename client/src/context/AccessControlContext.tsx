import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
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
    const { instance, accounts } = useMsal();
    const isAuthenticated = useIsAuthenticated();
    const { getApiAccessToken } = useAuth();

    const [accessState, setAccessState] = useState<AccessState>({
        hasChatAccess: false,
        hasDashboardAccess: false,
        hasPipelinesIngestionAccess: false,
        user: "",
        isLoading: false,
        error: null,
    });

    useEffect(() => {
        const fetchAccess = async () => {
            if (!isAuthenticated || accounts.length === 0) {
                setAccessState(prev => ({ ...prev, isLoading: false }));
                return;
            }

            setAccessState(prev => ({ ...prev, isLoading: true, error: null }));

            try {
                const token = await getApiAccessToken();
                if (!token) {
                    throw new Error("Failed to acquire access token");
                }

                const response = await fetch(`${appConfig.api.baseUrl}/api/auth/access`, {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                });

                if (!response.ok) {
                    throw new Error("Failed to validate access with backend");
                }

                const data = await response.json();
                setAccessState({
                    hasChatAccess: data.hasChatAccess,
                    hasDashboardAccess: data.hasDashboardAccess,
                    hasPipelinesIngestionAccess: data.hasPipelinesIngestionAccess,
                    user: data.user,
                    isLoading: false,
                    error: null,
                });
            } catch (err: any) {
                console.error("Access control check failed", err);
                setAccessState(prev => ({
                    ...prev,
                    isLoading: false,
                    error: err.message || "Unknown error",
                }));
            }
        };

        fetchAccess();
    }, [isAuthenticated, accounts, getApiAccessToken]);

    return (
        <AccessControlContext.Provider value={accessState}>
            {children}
        </AccessControlContext.Provider>
    );
};
