import type { DragEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import {
  generateErrorMessage,
  generateSuccessMessage,
} from "utils/toastHandler";

import type { HostFormValues } from "../components/host-dialog";
import {
  cloneHosts,
  removeHost,
  reorderHost,
  toHostPayload,
  updateHost,
  type HostRow,
} from "../lib/model";
import {
  useCreateHostMutation,
  useDeleteHostMutation,
  useHostGroupsQuery,
  useHostsQuery,
  useReorderHostsMutation,
  useUpdateHostMutation,
} from "../lib/query";
import type { HostsSchema } from "../types";

export type HostsDropTarget = {
  rowId: number;
  position: "before" | "after";
} | null;

const parseGroupsFilter = (value: string | null) => {
  if (!value) return [];
  return value
    .split(",")
    .map((groupId) => groupId.trim())
    .filter(Boolean);
};

export function useHostsPageController() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const filterSearch = searchParams.get("search") ?? "";
  const selectedGroupIds = useMemo(
    () => parseGroupsFilter(searchParams.get("groups")),
    [searchParams],
  );
  const [hosts, setHosts] = useState<HostsSchema>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRow, setEditingRow] = useState<HostRow | null>(null);
  const [search, setSearch] = useState(filterSearch);
  const [draggedRow, setDraggedRow] = useState<HostRow | null>(null);
  const [dropTarget, setDropTarget] = useState<HostsDropTarget>(null);
  const {
    data: hostsData,
    isLoading,
    isFetching,
    isError,
    refetch,
  } = useHostsQuery(selectedGroupIds, filterSearch);
  const { data: hostGroups = [] } = useHostGroupsQuery();
  const createHost = useCreateHostMutation();
  const updateHostMutation = useUpdateHostMutation();
  const deleteHost = useDeleteHostMutation();
  const reorderHosts = useReorderHostsMutation();
  const pending =
    createHost.isPending ||
    updateHostMutation.isPending ||
    deleteHost.isPending ||
    reorderHosts.isPending;
  const rows = useMemo(() => hosts, [hosts]);
  const reorderDisabled = Boolean(selectedGroupIds.length);

  useEffect(() => {
    if (hostsData) setHosts(cloneHosts(hostsData));
  }, [hostsData]);

  const updateFilters = useCallback(
    (filters: { search?: string; groups?: string[] }) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);

          if ("search" in filters) {
            const nextSearch = filters.search?.trim();
            if (nextSearch) {
              next.set("search", nextSearch);
            } else {
              next.delete("search");
            }
          }

          if ("groups" in filters) {
            const nextGroups = filters.groups?.filter(Boolean) ?? [];
            if (nextGroups.length) {
              next.set("groups", nextGroups.join(","));
            } else {
              next.delete("groups");
            }
          }

          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  useEffect(() => {
    setSearch(filterSearch);
  }, [filterSearch]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      if (search.trim() !== filterSearch) {
        updateFilters({ search });
      }
    }, 700);

    return () => window.clearTimeout(timeoutId);
  }, [filterSearch, search, updateFilters]);

  useEffect(() => {
    const availableGroupIds = new Set(hostGroups.map((group) => group.id));
    const availableSelectedGroupIds = selectedGroupIds.filter((groupId) =>
      availableGroupIds.has(groupId),
    );
    if (availableSelectedGroupIds.length !== selectedGroupIds.length) {
      updateFilters({ groups: availableSelectedGroupIds });
    }
  }, [hostGroups, selectedGroupIds, updateFilters]);

  const changeSelectedGroupIds = useCallback(
    (groupIds: string[]) => updateFilters({ groups: groupIds }),
    [updateFilters],
  );

  const persistUpdate = (
    hostId: number,
    nextHosts: HostsSchema,
    values: HostFormValues,
    successMessage?: string,
  ) => {
    if (!hostsData) return;
    const previousHosts = hosts;
    const payload = toHostPayload(values);
    setHosts(nextHosts);
    updateHostMutation.mutate(
      { id: hostId, host: payload },
      {
        onSuccess: () => {
          if (successMessage) generateSuccessMessage(successMessage);
        },
        onError: (error) => {
          setHosts(previousHosts);
          generateErrorMessage(error);
        },
      },
    );
  };

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

  const submitHost = (values: HostFormValues) => {
    const payload = toHostPayload(values);
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
    createHost.mutate(
      {
        ...toHostPayload({
          ...row,
          inboundTag: row.inbound_tag,
          group_ids: row.groups.map((group) => group.id),
        }),
        remark: `${row.remark} ${t("hostsPage.copySuffix")}`,
        is_disabled: true,
      },
      {
        onSuccess: () => generateSuccessMessage(t("hostsPage.copied")),
        onError: (error) => generateErrorMessage(error),
      },
    );
  };

  const toggleHost = (row: HostRow, checked: boolean) => {
    const values: HostFormValues = {
      ...row,
      inboundTag: row.inbound_tag,
      group_ids: row.groups.map((group) => group.id),
      is_disabled: !checked,
    };
    persistUpdate(
      row.id,
      updateHost(hosts, row.id, toHostPayload(values), hostGroups),
      values,
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

  const dragStart = (row: HostRow) => {
    if (!reorderDisabled) setDraggedRow(row);
  };

  const dragEnd = () => {
    setDraggedRow(null);
    setDropTarget(null);
  };

  const dragOver = (row: HostRow, event: DragEvent<HTMLTableRowElement>) => {
    event.preventDefault();
    if (reorderDisabled || !draggedRow) {
      return;
    }

    const bounds = event.currentTarget.getBoundingClientRect();
    const position =
      event.clientY < bounds.top + bounds.height / 2 ? "before" : "after";
    setDropTarget((current) =>
      current?.rowId === row.id && current.position === position
        ? current
        : { rowId: row.id, position },
    );
  };

  const drop = (target: HostRow) => {
    if (reorderDisabled || !draggedRow || !dropTarget) {
      dragEnd();
      return;
    }

    const sourceIndex = rows.findIndex((row) => row.id === draggedRow.id);
    const targetRowIndex = rows.findIndex((row) => row.id === target.id);
    if (sourceIndex < 0 || targetRowIndex < 0) {
      dragEnd();
      return;
    }

    let targetIndex =
      targetRowIndex + (dropTarget.position === "after" ? 1 : 0);
    if (sourceIndex < targetIndex) targetIndex -= 1;

    if (sourceIndex !== targetIndex) {
      persistReorder(reorderHost(hosts, sourceIndex, targetIndex));
    }
    dragEnd();
  };

  return {
    dialogOpen,
    dropTarget,
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
    dragEnd,
    dragOver,
    dragStart,
    drop,
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
