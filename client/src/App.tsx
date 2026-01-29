import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";

import { useIsAuthenticated, MsalProvider } from "@azure/msal-react";
import { msalInstance } from "./auth/msalInstance";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AccessControlProvider, useAccessControl } from "./context/AccessControlContext";
import { routes, RouteConfig } from "./config/routes";
import Header from "./components/Layout/Header";
import Footer from "./components/Layout/Footer";

const Layout = () => {
  return (
    <div className="min-h-screen bg-surface-light flex flex-col font-sans text-text-main antialiased selection:bg-primary/10 selection:text-primary">
      <Header />
      <div className="flex-grow pt-12">
        <Outlet />
      </div>
      <Footer />
    </div>
  );
};

// Wrapper to handle granular access checks inside protected routes
const RouteGuard = ({ route, children }: { route: RouteConfig, children: React.ReactElement }) => {
  const accessState = useAccessControl();

  // If strict access check is required (e.g., hasChatAccess)
  if (route.accessRight && !accessState[route.accessRight as keyof typeof accessState]) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

const AppRoutes = () => {
  const { isLoading, error } = useAccessControl();
  const isAuthenticated = useIsAuthenticated();

  if (isAuthenticated && isLoading) {
    // Basic loading state that matches design system could be better, but this suffices for logic
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-light">
        <div className="flex items-center gap-2 text-primary">
          <span className="material-symbols-outlined animate-spin">refresh</span>
          <span className="text-sm font-medium">Verifying access...</span>
        </div>
      </div>
    );
  }

  // Show error state if access check failed
  if (isAuthenticated && error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-light">
        <div className="text-center p-6">
          <span className="material-symbols-outlined text-4xl text-red-500 mb-2">error</span>
          <p className="text-sm font-medium text-red-600">Access verification failed</p>
          <p className="text-xs text-gray-500 mt-1">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-primary text-white rounded text-sm hover:bg-primary-dark"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <Routes>

      <Route element={<Layout />}>
        {routes.map((route) => {
          const Element = route.component;
          return (
            <Route
              key={route.path}
              path={route.path}
              element={
                route.protected ? (
                  <ProtectedRoute>
                    <RouteGuard route={route}>
                      <Element />
                    </RouteGuard>
                  </ProtectedRoute>
                ) : (
                  <Element />
                )
              }
            />
          );
        })}
      </Route>
    </Routes>
  );
};

function App() {
  return (
    <MsalProvider instance={msalInstance}>
      <AccessControlProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AccessControlProvider>
    </MsalProvider>
  );
}

export default App;
