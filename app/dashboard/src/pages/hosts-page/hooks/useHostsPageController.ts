import { useHostsFilters } from "./useHostsFilters";
import { useHostReordering } from "./useHostReordering";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  generateErrorMessage,
  generateSuccessMessage,
} from "utils/toastHandler";

import { removeHost, type HostRow } from "../lib/model";
import {
  useCreateHostMutation,
  useCloneHostMutation,
  useDeleteHostMutation,
  useHostGroupsQuery,
  useHostsQuery,
  useReorderHostsMutation,
  useUpdateHostMutation,
} from "../lib/query";
import type { HostPayload, HostsSchema } from "../types";

export function useHostsPageController() {
  const { t } = useTranslation();
  const { data: hostGroups = [], isSuccess: groupsLoaded } =
    useHostGroupsQuery();
  const {
    filterSearch,
    selectedGroupIds,
    search,
    setSearch,
    changeSelectedGroupIds,
  } = useHostsFilters(hostGroups, groupsLoaded);
  const [hosts, setHosts] = useState<HostsSchema>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRow, setEditingRow] = useState<HostRow | null>(null);
  const {
    data: hostsData,
    isLoading,
    isFetching,
    isError,
    refetch,
  } = useHostsQuery(selectedGroupIds, filterSearch);
  const createHost = useCreateHostMutation();
  const cloneHost = useCloneHostMutation();
  const updateHostMutation = useUpdateHostMutation();
  const deleteHost = useDeleteHostMutation();
  const reorderHosts = useReorderHostsMutation();
  const pending =
    createHost.isPending ||
    cloneHost.isPending ||
    updateHostMutation.isPending ||
    deleteHost.isPending ||
    reorderHosts.isPending;
  const rows = hosts;
  const reorderDisabled = Boolean(
    selectedGroupIds.length || filterSearch.trim(),
  );

  useEffect(() => {
    if (hostsData) setHosts(hostsData);
  }, [hostsData]);

  const persistReorder = (nextHosts: HostsSchema) => {
    if (!hostsData) return;
    const previousHosts = hosts;
    setHosts(nextHosts);
    reorderHosts.mutate(
      nextHosts.map((host) => host.id),
      {
        onSuccess: () => {
          generateSuccessMessage(t("hostsPage.orderSaved"));
        },
        onError: (error) => {
          setHosts(previousHosts);
          generateErrorMessage(error);
        },
      },
    );
  };

  const openCreate = () => {
    setEditingRow(null);
    setDialogOpen(true);
  };

  const openEdit = (row: HostRow) => {
    setEditingRow(row);
    setDialogOpen(true);
  };

  const submitHost = (payload: HostPayload) => {
    if (editingRow) {
      updateHostMutation.mutate(
        { id: editingRow.id, host: payload },
        {
          onSuccess: () => {
            generateSuccessMessage(t("hostsDialog.savedSuccess"));
            setDialogOpen(false);
          },
          onError: (error) => generateErrorMessage(error),
        },
      );
      return;
    }

    createHost.mutate(payload, {
      onSuccess: () => {
        generateSuccessMessage(t("hostsDialog.savedSuccess"));
        setDialogOpen(false);
      },
      onError: (error) => generateErrorMessage(error),
    });
  };

  const duplicate = (row: HostRow) => {
    cloneHost.mutate(
      { id: row.id, remark: `${row.remark} ${t("hostsPage.copySuffix")}` },
      {
        onSuccess: () => generateSuccessMessage(t("hostsPage.copied")),
        onError: (error) => generateErrorMessage(error),
      },
    );
  };

  const toggleHost = (row: HostRow, checked: boolean) => {
    updateHostMutation.mutate(
      { id: row.id, host: { enabled: checked } },
      {
        onError: (error) => generateErrorMessage(error),
      },
    );
  };

  const removeHostRow = (row: HostRow) => {
    const previousHosts = hosts;
    setHosts(removeHost(hosts, row.id));
    deleteHost.mutate(row.id, {
      onError: (error) => {
        setHosts(previousHosts);
        generateErrorMessage(error);
      },
    });
  };

  const reordering = useHostReordering(
    rows,
    reorderDisabled || pending,
    persistReorder,
  );

  return {
    dialogOpen,
    ...reordering,
    editingRow,
    hasLoadedHosts: Boolean(hostsData),
    hostGroups,
    isError,
    isFetching,
    isLoading,
    pending,
    reorderDisabled,
    rows,
    search,
    selectedGroupIds,
    duplicate,
    openCreate,
    openEdit,
    refetch,
    removeHostRow,
    setDialogOpen,
    setSearch,
    setSelectedGroupIds: changeSelectedGroupIds,
    submitHost,
    toggleHost,
  };
}
