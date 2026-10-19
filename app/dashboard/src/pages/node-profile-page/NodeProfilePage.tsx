import {
  ArrowLeft,
  AlertTriangle,
  Ellipsis,
  LoaderCircle,
  RefreshCw,
  Server,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";

import Page from "@/components/page";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { RuntimeLogsCard } from "@/components/runtime-logs/RuntimeLogsCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useDeleteNodeMutation,
  useNodeQuery,
  useRestartNodeMutation,
} from "@/pages/nodes-page/lib/query";
import {
  generateErrorMessage,
  generateSuccessMessage,
} from "utils/toastHandler";

import { NodeInboundsCard } from "./components/NodeInboundsCard";
import { NodeOutboundsCard } from "./components/NodeOutboundsCard";
import { NodeOverviewCard } from "./components/NodeOverviewCard";
import { NodeRoutingCard } from "./components/NodeRoutingCard";
import { StaticLogsCard } from "./components/static-logs/StaticLogsCard";

export function NodeProfilePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const params = useParams();
  const nodeId = Number(params.id);
  const query = useNodeQuery(nodeId, Number.isInteger(nodeId) && nodeId > 0);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const remove = useDeleteNodeMutation();
  const restart = useRestartNodeMutation();
  const node = query.data;
  const restartNode = () =>
    restart.mutate(node!.id!, {
      onSuccess: () => generateSuccessMessage(t("nodeProfile.restartSuccess")),
      onError: (error) => generateErrorMessage(error),
    });

  if (query.isLoading) {
    return (
      <Page className="gap-4">
        <Page.Header className="mb-0">
          <div className="min-w-0">
            <Skeleton className="h-6 w-40 rounded-xl" />
          </div>
          <div className="ml-auto flex gap-2">
            <Skeleton className="h-6 w-6 md:w-40 rounded-xl" />
            <Skeleton className="h-6 w-6 md:w-34 rounded-xl" />
          </div>
        </Page.Header>
        <Skeleton className="h-72 w-full rounded-xl" />
        <Skeleton className="h-52 w-full rounded-xl" />
      </Page>
    );
  }

  if (!node || !node.id || query.isError) {
    return (
      <Page>
        <Empty className="min-h-96 rounded-xl">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Server />
            </EmptyMedia>
            <EmptyTitle>{t("nodeProfile.notFound")}</EmptyTitle>
            <EmptyDescription>
              {t("nodeProfile.notFoundDescription")}
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button asChild variant="outline">
              <Link to="/nodes">
                <ArrowLeft />
                {t("actions.back")}
              </Link>
            </Button>
          </EmptyContent>
        </Empty>
      </Page>
    );
  }

  const profileNode = { ...node, id: node.id };
  const nodeActions = (
    <>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={restart.isPending}
          >
            <RefreshCw
              className={restart.isPending ? "animate-spin" : undefined}
            />
            <span className="hidden sm:inline">{t("actions.restart")}</span>
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogMedia>
              <RefreshCw />
            </AlertDialogMedia>
            <AlertDialogTitle>{t("nodeProfile.restartTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("nodeProfile.restartDescription", { name: node.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={restart.isPending}>
              {t("cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={restart.isPending}
              onClick={restartNode}
            >
              {restart.isPending && <LoaderCircle className="animate-spin" />}
              {t("actions.restart")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            aria-label={t("nodeProfile.actions")}
          >
            <Ellipsis />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-50">
          <DropdownMenuItem
            variant="destructive"
            onSelect={() => setDeleteDialogOpen(true)}
          >
            <Trash2 />
            {t("nodesPage.deleteNode")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogMedia className="bg-destructive/10 text-destructive">
              <Trash2 />
            </AlertDialogMedia>
            <AlertDialogTitle>{t("deleteNode.title")}</AlertDialogTitle>
            <AlertDialogDescription>
              <Trans
                i18nKey="deleteNode.prompt"
                values={{ name: node.name }}
                components={{ b: <strong /> }}
              />
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>
              {t("cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={remove.isPending}
              onClick={(event) => {
                event.preventDefault();
                remove.mutate(node.id!, {
                  onSuccess: () => {
                    setDeleteDialogOpen(false);
                    generateSuccessMessage(
                      t("deleteNode.deleteSuccess", { name: node.name }),
                    );
                    navigate("/nodes", { replace: true });
                  },
                  onError: (error) => generateErrorMessage(error),
                });
              }}
            >
              {remove.isPending && <LoaderCircle className="animate-spin" />}
              {t("delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );

  return (
    <Page className="gap-4 pb-6">
      <Page.Header className="mb-0">
        <div className="min-w-0">
          <h1 className="truncate font-semibold">{node.name}</h1>
        </div>
        <div className="ml-auto flex gap-2">{nodeActions}</div>
      </Page.Header>

      {node.restart_required && (
        <div className="flex flex-col gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-amber-600 dark:text-amber-300 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <div className="min-w-0 space-y-1">
              <p className="font-medium text-foreground">
                {t("nodeProfile.restartRequiredTitle")}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("nodeProfile.restartRequiredDescription")}
              </p>
            </div>
          </div>
          <Button
            type="button"
            size="sm"
            disabled={restart.isPending}
            onClick={restartNode}
            className="shrink-0"
          >
            <RefreshCw
              className={restart.isPending ? "animate-spin" : undefined}
            />
            {t("apply")}
          </Button>
        </div>
      )}

      <div className="grid gap-4 2xl:grid-cols-2">
        <NodeOverviewCard node={profileNode} />
        <NodeInboundsCard node={profileNode} />
        <NodeRoutingCard node={profileNode} />
        <NodeOutboundsCard node={profileNode} />
      </div>
      <Tabs defaultValue="static">
        <TabsList>
          <TabsTrigger value="static">{t("staticLogs.static")}</TabsTrigger>
          <TabsTrigger value="runtime">{t("staticLogs.runtime")}</TabsTrigger>
        </TabsList>
        <TabsContent value="static">
          <StaticLogsCard node={profileNode} />
        </TabsContent>
        <TabsContent value="runtime">
          <RuntimeLogsCard nodeId={profileNode.id} />
        </TabsContent>
      </Tabs>
    </Page>
  );
}
