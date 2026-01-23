import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { useAuth } from "../auth/useAuth";

export const LoginButton = () => {
  const isAuthenticated = useIsAuthenticated();
  const { inProgress } = useMsal();
  const { login, logout, account } = useAuth();

  const isLoading = inProgress !== InteractionStatus.None;

  if (isAuthenticated) {
    return (
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">
          {account?.name || account?.username}
        </span>
        <button
          onClick={logout}
          disabled={isLoading}
          className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? "Signing out..." : "Sign Out"}
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={login}
      disabled={isLoading}
      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {isLoading ? "Signing in..." : "Sign In with Microsoft"}
    </button>
  );
};
