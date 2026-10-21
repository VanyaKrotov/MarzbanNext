import { Plus, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import Page from "@/components/page";
import { Button } from "@/components/ui/button";

import { HostDialog } from "./components/host-dialog";
import { HostsCards } from "./components/HostsCards";
import { HostsSkeleton } from "./components/HostsSkeleton";
import { HostsState } from "./components/HostsState";
import { HostsTable } from "./components/HostsTable";
import { HostsToolbar } from "./components/HostsToolbar";
import { useHostsPageController } from "./hooks/useHostsPageController";

export function HostsPage() {
  const { t } = useTranslation();
  const controller = useHostsPageController();

  return (
    <Page>
      <Page.Header
        actions={
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="px-2 sm:px-3"
              disabled={controller.isFetching}
              onClick={() => void controller.refetch()}
              aria-label={t("hostsPage.refresh").toString()}
            >
              <RefreshCw
                className={controller.isFetching ? "animate-spin" : undefined}
              />
              <span className="hidden sm:inline">{t("hostsPage.refresh")}</span>
            </Button>
            <Button type="button" size="sm" onClick={controller.openCreate}>
              <Plus />
              {t("create")}
            </Button>
          </div>
        }
      >
        <h1 className="font-semibold">{t("hostsPage.title")}</h1>
      </Page.Header>

      <HostsToolbar
        groups={controller.hostGroups}
        pending={controller.pending}
        search={controller.search}
        selectedGroupIds={controller.selectedGroupIds}
        onSearchChange={controller.setSearch}
        onSelectedGroupIdsChange={controller.setSelectedGroupIds}
      />

      {controller.isLoading ? (
        <HostsSkeleton />
      ) : controller.isError || !controller.hasLoadedHosts ? (
        <HostsState
          title={t("hostsPage.loadErrorTitle")}
          description={t("hostsPage.loadErrorDescription")}
          action={
            <Button variant="outline" onClick={() => void controller.refetch()}>
              <RefreshCw />
              {t("hostsPage.refresh")}
            </Button>
          }
        />
      ) : controller.rows.length ? (
        <>
          <HostsTable
            rows={controller.rows}
            pending={controller.pending}
            reorderDisabled={controller.reorderDisabled}
            dropTarget={controller.dropTarget}
            onDragStart={controller.dragStart}
            onDragEnd={controller.dragEnd}
            onDragOver={controller.dragOver}
            onDrop={controller.drop}
            onEdit={controller.openEdit}
            onDuplicate={controller.duplicate}
            onToggle={controller.toggleHost}
            onDelete={controller.removeHostRow}
          />
          <HostsCards
            rows={controller.rows}
            pending={controller.pending}
            onEdit={controller.openEdit}
            onDuplicate={controller.duplicate}
            onToggle={controller.toggleHost}
            onDelete={controller.removeHostRow}
          />
        </>
      ) : (
        <HostsState
          title={t("hostsPage.emptyTitle")}
          description={t("hostsPage.emptyDescription")}
          action={
            <Button onClick={controller.openCreate}>
              <Plus />
              {t("create")}
            </Button>
          }
        />
      )}

      {controller.hasLoadedHosts && (
        <HostDialog
          key={`${controller.editingRow?.id ?? "create"}-${
            controller.dialogOpen
          }`}
          open={controller.dialogOpen}
          host={controller.editingRow ?? null}
          inboundTag={controller.editingRow?.inbound_tag ?? null}
          hostGroups={controller.hostGroups}
          pending={controller.pending}
          onOpenChange={controller.setDialogOpen}
          onSubmit={controller.submitHost}
        />
      )}
    </Page>
  );
}
