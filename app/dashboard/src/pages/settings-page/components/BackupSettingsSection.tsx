import {
  ArchiveRestore,
  DatabaseBackup,
  Download,
  LoaderCircle,
  Upload,
} from "lucide-react";
import { useRef, useState, type ReactNode, type RefObject } from "react";
import { useTranslation } from "react-i18next";

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
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";
import {
  generateErrorMessage,
  generateSuccessMessage,
} from "@/utils/toastHandler";

import {
  downloadDatabaseBackup,
  downloadFullBackup,
  useRestoreDatabaseBackupMutation,
  useRestoreFullBackupMutation,
} from "../lib/query";

type RestoreType = "full" | "database";

type PendingRestore = {
  type: RestoreType;
  file: File;
};

export function BackupSettingsSection() {
  const { t } = useTranslation();
  const fullInputRef = useRef<HTMLInputElement>(null);
  const databaseInputRef = useRef<HTMLInputElement>(null);
  const [downloading, setDownloading] = useState<RestoreType | null>(null);
  const [pendingRestore, setPendingRestore] = useState<PendingRestore | null>(
    null,
  );
  const restoreFull = useRestoreFullBackupMutation();
  const restoreDatabase = useRestoreDatabaseBackupMutation();
  const restoring = restoreFull.isPending || restoreDatabase.isPending;

  const download = async (type: RestoreType) => {
    setDownloading(type);
    try {
      if (type === "full") {
        await downloadFullBackup();
      } else {
        await downloadDatabaseBackup();
      }
    } catch (error) {
      generateErrorMessage(error);
    } finally {
      setDownloading(null);
    }
  };

  const selectRestoreFile = (type: RestoreType, file?: File) => {
    if (!file) return;
    setPendingRestore({ type, file });
  };

  const restore = () => {
    if (!pendingRestore) return;
    const mutation =
      pendingRestore.type === "full" ? restoreFull : restoreDatabase;
    mutation.mutate(pendingRestore.file, {
      onSuccess: () => {
        generateSuccessMessage(t("settingsPage.backups.restoreSuccess"));
        setPendingRestore(null);
      },
      onError: (error) => generateErrorMessage(error),
    });
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{t("settingsPage.backups.title")}</CardTitle>
          <CardDescription>
            {t("settingsPage.backups.description")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            <BackupActionItem
              icon={<ArchiveRestore />}
              title={t("settingsPage.backups.fullTitle")}
              description={t("settingsPage.backups.fullDescription")}
              downloadLabel={t("actions.download")}
              restoreLabel={t("settingsPage.backups.restore")}
              downloading={downloading === "full"}
              restoring={restoreFull.isPending}
              accept=".zip,application/zip"
              inputRef={fullInputRef}
              onDownload={() => void download("full")}
              onRestore={(file) => selectRestoreFile("full", file)}
            />
            <BackupActionItem
              icon={<DatabaseBackup />}
              title={t("settingsPage.backups.databaseTitle")}
              description={t("settingsPage.backups.databaseDescription")}
              downloadLabel={t("actions.download")}
              restoreLabel={t("settingsPage.backups.restore")}
              downloading={downloading === "database"}
              restoring={restoreDatabase.isPending}
              accept=".sql,application/sql,text/sql,text/plain"
              inputRef={databaseInputRef}
              onDownload={() => void download("database")}
              onRestore={(file) => selectRestoreFile("database", file)}
            />
          </div>
        </CardContent>
      </Card>

      <AlertDialog
        open={Boolean(pendingRestore)}
        onOpenChange={(open) => {
          if (!open && !restoring) setPendingRestore(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogMedia>
              <Upload />
            </AlertDialogMedia>
            <AlertDialogTitle>
              {t("settingsPage.backups.restoreConfirmTitle")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("settingsPage.backups.restoreConfirmDescription", {
                filename: pendingRestore?.file.name ?? "",
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={restoring}>
              {t("settingsPage.backups.cancel")}
            </AlertDialogCancel>
            <AlertDialogAction disabled={restoring} onClick={restore}>
              {restoring && <LoaderCircle className="animate-spin" />}
              {t("settingsPage.backups.restore")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function BackupActionItem({
  icon,
  title,
  description,
  downloadLabel,
  restoreLabel,
  downloading,
  restoring,
  accept,
  inputRef,
  onDownload,
  onRestore,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  downloadLabel: string;
  restoreLabel: string;
  downloading: boolean;
  restoring: boolean;
  accept: string;
  inputRef: RefObject<HTMLInputElement | null>;
  onDownload(): void;
  onRestore(file?: File): void;
}) {
  return (
    <Item variant="outline" className="gap-4">
      <ItemMedia variant="icon" className="rounded-md bg-muted p-2">
        {icon}
      </ItemMedia>
      <ItemContent className="min-w-0 basis-full sm:basis-0">
        <ItemTitle className="w-full">{title}</ItemTitle>
        <ItemDescription className="line-clamp-none">
          {description}
        </ItemDescription>
      </ItemContent>
      <ItemActions className="w-full flex-wrap sm:ms-auto sm:w-auto">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full sm:w-auto"
          disabled={downloading || restoring}
          onClick={onDownload}
        >
          {downloading ? <LoaderCircle className="animate-spin" /> : <Download />}
          {downloadLabel}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full sm:w-auto"
          disabled={downloading || restoring}
          onClick={() => inputRef.current?.click()}
        >
          {restoring ? <LoaderCircle className="animate-spin" /> : <Upload />}
          {restoreLabel}
        </Button>
        <input
          ref={inputRef as RefObject<HTMLInputElement>}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(event) => {
            onRestore(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </ItemActions>
    </Item>
  );
}
