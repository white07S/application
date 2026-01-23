import { ReactNode } from "react";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { Navigate } from "react-router-dom";

interface ProtectedRouteProps {
  children: ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const isAuthenticated = useIsAuthenticated();
  const { inProgress } = useMsal();

  if (inProgress !== InteractionStatus.None) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg text-gray-600">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
