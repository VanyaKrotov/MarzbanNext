import debounce from "lodash.debounce";
import { ListRestart, Plus, RefreshCcw, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import type { UsersFilter } from "../lib/types";

type UsersToolbarProps = {
  filters: UsersFilter;
  isFetching: boolean;
  onFiltersChange: (filters: Partial<UsersFilter>) => void;
  onRefresh: () => void;
  onResetFilters: () => void;
  showResetFilters: boolean;
  onCreate: () => void;
};

export function UsersToolbar({
  filters,
  isFetching,
  onFiltersChange,
  onRefresh,
  onResetFilters,
  showResetFilters,
  onCreate,
}: UsersToolbarProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState(filters.search ?? "");

  useEffect(() => {
    setSearch(filters.search ?? "");
  }, [filters.search]);

  const updateSearch = useMemo(
    () => debounce((value: string) => {
      onFiltersChange({ search: value || undefined, offset: 0 });
    }, 350),
    [onFiltersChange],
  );

  useEffect(() => () => updateSearch.cancel(), [updateSearch]);

  const clearSearch = () => {
    updateSearch.cancel();
    setSearch("");
    onFiltersChange({ search: undefined, offset: 0 });
  };

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <InputGroup className="max-w-md">
        <InputGroupAddon>
          <Search />
        </InputGroupAddon>
        <InputGroupInput
          aria-label={t("search")}
          placeholder={t("search")}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            updateSearch(event.target.value);
          }}
        />
        {search && (
          <InputGroupAddon align="inline-end">
            <InputGroupButton
              aria-label={t("usersTable.clearSearch")}
              size="icon-xs"
              onClick={clearSearch}
            >
              <X />
            </InputGroupButton>
          </InputGroupAddon>
        )}
      </InputGroup>

      <div className="flex justify-end gap-2">
        {showResetFilters && (
          <Button variant="outline" onClick={onResetFilters}>
            <ListRestart />
            {t("usersTable.resetFilters")}
          </Button>
        )}
        <Button
          aria-label={t("usersTable.refresh")}
          variant="outline"
          size="icon"
          disabled={isFetching}
          onClick={onRefresh}
        >
          <RefreshCcw className={isFetching ? "animate-spin" : undefined} />
        </Button>
        <Button onClick={onCreate}>
          <Plus />
          {t("create")}
        </Button>
      </div>
    </div>
  );
}
