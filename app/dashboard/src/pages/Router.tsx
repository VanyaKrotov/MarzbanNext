import {
  createHashRouter,
  Navigate,
  redirect,
  useRouteError,
} from "react-router-dom";
import { AxiosError } from "axios";

import { ErrorFallback } from "@/components/ErrorFallback";
import HostsPage from "@/pages/hosts-page";
import NodesPage from "@/pages/nodes-page";
import NodeProfilePage from "@/pages/node-profile-page";
import StatsPage from "@/pages/stats-page";
import UsersPage from "@/pages/users-page";
import LoginPage from "@/pages/login-page";
import SettingsPage from "@/pages/settings-page";
import SubscriptionTemplatesPage from "@/pages/subscription-templates-page/SubscriptionTemplatesPage";

import { queryClient } from "@/utils/query-client";
import { accountQuery } from "@/hooks/use-admin";

import Layout from "./Layout";

function RouteErrorBoundary() {
  const error = useRouteError();

  if (error instanceof AxiosError && error.response?.status === 401) {
    return <Navigate to="/login" />;
  }

  return <ErrorFallback error={error} />;
}

async function requireSudo() {
  const admin = await queryClient.ensureQueryData(accountQuery);

  if (!admin.is_sudo) {
    throw redirect("/");
  }

  return null;
}

export const router = createHashRouter([
  {
    id: "layout",
    path: "/",
    element: <Layout />,
    ErrorBoundary: RouteErrorBoundary,
    loader: () => queryClient.ensureQueryData(accountQuery),
    children: [
      {
        index: true,
        element: <UsersPage />,
      },
      {
        path: "nodes",
        element: <NodesPage />,
        loader: requireSudo,
      },
      {
        path: "nodes/:id",
        element: <NodeProfilePage />,
        loader: requireSudo,
      },
      {
        path: "hosts",
        element: <HostsPage />,
        loader: requireSudo,
      },
      {
        path: "stats",
        element: <StatsPage />,
      },
      {
        path: "subscription-templates",
        element: <SubscriptionTemplatesPage />,
        loader: requireSudo,
      },
      {
        path: "settings",
        element: <SettingsPage />,
        loader: requireSudo,
      },
    ],
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "*",
    element: <Navigate to="/" replace />,
  },
]);
