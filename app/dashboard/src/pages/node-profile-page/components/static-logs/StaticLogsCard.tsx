import {
  Download,
  FileCog,
  FileText,
  FolderOpen,
  LoaderCircle,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { formatBytes } from "@/utils/formatByte";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import type { NodeType } from "types/Node";
import { generateErrorMessage } from "utils/toastHandler";

import { NodeLoggingSettingsDialog } from "../NodeLoggingSettingsDialog";
import {
  downloadNodeStaticLog,
  type NodeStaticLogFile,
  useDeleteNodeStaticLogMutation,
  useNodeStaticLogsQuery,
} from "./query";

const logTypes = ["access", "error"] as const;

export function StaticLogsCard({ node }: { node: NodeType & { id: number } }) {
  const { t, i18n } = useTranslation();
  const staticLogsDisabled =
    !node.access_log_enabled && !node.error_log_enabled;
  const query = useNodeStaticLogsQuery(node.id, !staticLogsDisabled);
  const remove = useDeleteNodeStaticLogMutation(node.id);
  const [pendingDelete, setPendingDelete] = useState<NodeStaticLogFile | null>(
    null,
  );
  const [loggingSettingsOpen, setLoggingSettingsOpen] = useState(false);
  const files = query.data ?? [];

  const confirmDelete = () => {
    if (!pendingDelete) return;
    remove.mutate(pendingDelete, {
      onSuccess: () => setPendingDelete(null),
      onError: (error) => generateErrorMessage(error),
    });
  };

  const types = useMemo(() => {
    const access: NodeStaticLogFile[] = [];
    const error: NodeStaticLogFile[] = [];

    for (const file of files) {
      if (file.type === "access") {
        access.push(file);
      } else {
        error.push(file);
      }
    }

    return { access, error };
  }, [files]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("staticLogs.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {staticLogsDisabled ? (
          <Empty className="min-h-56 rounded-lg border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FileCog />
              </EmptyMedia>
              <EmptyTitle className="text-sm">
                {t("staticLogs.disabled")}
              </EmptyTitle>
            </EmptyHeader>
            <EmptyContent>
              <Button
                type="button"
                variant="outline"
                onClick={() => setLoggingSettingsOpen(true)}
              >
                <FileCog />
                {t("staticLogs.configure")}
              </Button>
            </EmptyContent>
          </Empty>
        ) : query.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : query.isError ? (
          <p className="text-sm text-destructive">
            {t("staticLogs.loadError")}
          </p>
        ) : !files.length ? (
          <Empty className="min-h-56 rounded-lg border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FolderOpen />
              </EmptyMedia>
              <EmptyTitle className="text-sm">
                {t("staticLogs.filesNotCreated")}
              </EmptyTitle>
            </EmptyHeader>
          </Empty>
        ) : (
          <Accordion
            type="multiple"
            defaultValue={[...logTypes]}
            className="rounded-lg border px-3"
          >
            {logTypes
              .filter((x) => Boolean(types[x]?.length))
              .map((type) => {
                const typeFiles = types[type];

                return (
                  <AccordionItem value={type} key={type}>
                    <AccordionTrigger className="py-3 no-underline hover:no-underline">
                      <span className="flex items-center gap-2">
                        <FolderOpen className="size-4 text-muted-foreground" />
                        {t(`staticLogs.${type}`)}
                        <Badge variant="secondary">{typeFiles.length}</Badge>
                      </span>
                    </AccordionTrigger>
                    <AccordionContent>
                      {typeFiles.length ? (
                        <div className="divide-y rounded-md border">
                          {typeFiles.map((file) => (
                            <div
                              key={file.filename}
                              className="flex min-w-0 items-center gap-3 px-3 py-2.5"
                            >
                              <FileText className="size-4 shrink-0 text-muted-foreground" />
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="truncate font-medium">
                                    {file.filename}
                                  </span>
                                  {file.active && (
                                    <div className="size-2 rounded-full bg-primary" />
                                  )}
                                </div>
                                <p className="text-xs text-muted-foreground">
                                  {formatBytes(file.size)}
                                  {` - ${new Intl.DateTimeFormat(
                                    i18n.language,
                                    {
                                      dateStyle: "medium",
                                      timeStyle: "short",
                                    },
                                  ).format(new Date(file.modified_at))}`}
                                </p>
                              </div>
                              <div className="flex items-center gap-x-1">
                                <Button
                                  type="button"
                                  size="icon-sm"
                                  variant="ghost"
                                  aria-label={t("staticLogs.download")}
                                  onClick={() =>
                                    downloadNodeStaticLog(
                                      node.id,
                                      file.type,
                                      file.filename,
                                    ).catch(generateErrorMessage)
                                  }
                                >
                                  <Download />
                                </Button>
                                <Button
                                  type="button"
                                  size="icon-sm"
                                  variant="ghost"
                                  className="text-destructive hover:text-destructive"
                                  aria-label={t("delete")}
                                  onClick={() => setPendingDelete(file)}
                                >
                                  <Trash2 />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="py-2 text-sm text-muted-foreground">
                          {t("staticLogs.empty")}
                        </p>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
          </Accordion>
        )}
      </CardContent>

      <AlertDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(open) => !open && setPendingDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t(
                pendingDelete?.active
                  ? "staticLogs.clearTitle"
                  : "staticLogs.deleteTitle",
              )}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                pendingDelete?.active
                  ? "staticLogs.clearDescription"
                  : "staticLogs.deleteDescription",
                {
                  filename: pendingDelete?.filename,
                },
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>
              {t("cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={remove.isPending}
              onClick={confirmDelete}
            >
              {remove.isPending && <LoaderCircle className="animate-spin" />}
              {t(pendingDelete?.active ? "staticLogs.clear" : "delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <NodeLoggingSettingsDialog
        node={node}
        open={loggingSettingsOpen}
        onOpenChange={setLoggingSettingsOpen}
      />
    </Card>
  );
}
