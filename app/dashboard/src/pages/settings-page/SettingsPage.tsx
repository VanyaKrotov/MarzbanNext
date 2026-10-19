import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import Page from "@/components/page";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { BackupSettingsSection } from "./components/BackupSettingsSection";
import { DefaultNodeConfigSection } from "./components/DefaultNodeConfigSection";
import { LoadError } from "./components/LoadError";
import { NotificationSettingsSection } from "./components/NotificationSettingsSection";
import { SubscriptionSettingsSection } from "./components/SubscriptionSettingsSection";
import { GeneratorSettingsSection } from "./components/GeneratorSettingsSection";
import { WebhookSettingsSection } from "./components/WebhookSettingsSection";
import { useRuntimeSettingsQuery } from "./lib/query";

export function SettingsPage() {
  const { t } = useTranslation();
  const settingsQuery = useRuntimeSettingsQuery();
  return (
    <Page>
      <Page.Header
        actions={
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={settingsQuery.isFetching}
            onClick={() => {
              void settingsQuery.refetch();
            }}
          >
            <RefreshCw
              className={settingsQuery.isFetching ? "animate-spin" : undefined}
            />
            <span className="hidden sm:inline">
              {t("settingsPage.refresh")}
            </span>
          </Button>
        }
      >
        <h1 className="font-semibold">{t("settingsPage.title")}</h1>
      </Page.Header>

      {settingsQuery.isLoading ? (
        <Skeleton className="h-[calc(100svh-10rem)] min-h-128 w-full rounded-xl" />
      ) : settingsQuery.isError || !settingsQuery.data ? (
        <LoadError onRefresh={() => void settingsQuery.refetch()} />
      ) : (
        <div className="space-y-5">
          <SubscriptionSettingsSection settings={settingsQuery.data} />
          <DefaultNodeConfigSection settings={settingsQuery.data} />
          <GeneratorSettingsSection settings={settingsQuery.data} />
          <NotificationSettingsSection settings={settingsQuery.data} />
          <WebhookSettingsSection settings={settingsQuery.data} />
          <BackupSettingsSection />
        </div>
      )}
    </Page>
  );
}
