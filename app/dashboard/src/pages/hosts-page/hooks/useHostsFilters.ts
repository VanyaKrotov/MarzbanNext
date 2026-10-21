import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { HostGroupType } from "../types";

const parseGroupsFilter = (value: string | null) => {
  if (!value) return [];
  return value
    .split(",")
    .map((groupId) => groupId.trim())
    .filter(Boolean);
};

export function useHostsFilters(
  hostGroups: HostGroupType[],
  groupsLoaded: boolean,
) {
  const [searchParams, setSearchParams] = useSearchParams();
  const filterSearch = searchParams.get("search") ?? "";
  const selectedGroupIds = useMemo(
    () => parseGroupsFilter(searchParams.get("groups")),
    [searchParams],
  );
  const [search, setSearch] = useState(filterSearch);
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
    if (!groupsLoaded) return;
    const availableGroupIds = new Set(hostGroups.map((group) => group.id));
    const availableSelectedGroupIds = selectedGroupIds.filter((groupId) =>
      availableGroupIds.has(groupId),
    );
    if (availableSelectedGroupIds.length !== selectedGroupIds.length) {
      updateFilters({ groups: availableSelectedGroupIds });
    }
  }, [hostGroups, groupsLoaded, selectedGroupIds, updateFilters]);

  const changeSelectedGroupIds = useCallback(
    (groupIds: string[]) => updateFilters({ groups: groupIds }),
    [updateFilters],
  );

  return {
    filterSearch,
    selectedGroupIds,
    search,
    setSearch,
    changeSelectedGroupIds,
  };
}
