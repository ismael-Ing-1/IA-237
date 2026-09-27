// src/app/router.tsx

import {
  Navigate,
  createBrowserRouter,
} from "react-router-dom";

import DashboardPage from "../pages/DashboardPage";


function NotFoundPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <h1>404</h1>

      <p>Page not found.</p>

      <a href="/">Back to dashboard</a>
    </div>
  );
}


export const router = createBrowserRouter([
  {
    path: "/",
    element: <DashboardPage />,
  },

  /*
   * Pour l'instant on garde une seule page principale.
   *
   * Plus tard, on pourra facilement ajouter :
   *
   * {
   *   path: "/negotiations/:negotiationId",
   *   element: <NegotiationPage />,
   * }
   *
   * {
   *   path: "/settings",
   *   element: <SettingsPage />,
   * }
   */

  {
    path: "/dashboard",
    element: <Navigate to="/" replace />,
  },

  {
    path: "*",
    element: <NotFoundPage />,
  },
]);