import { ChevronsUpDown, FolderTree, Search, X } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

import { HostGroupsManagerDialog } from "./host-groups/HostGroupsManagerDialog";

import type { HostGroupType } from "../types";

type HostsToolbarProps = {
  groups: HostGroupType[];
  pending: boolean;
  search: string;
  selectedGroupIds: string[];
  onSearchChange: (search: string) => void;
  onSelectedGroupIdsChange: (groupIds: string[]) => void;
};

export function HostsToolbar({
  groups,
  pending,
  search,
  selectedGroupIds,
  onSearchChange,
  onSelectedGroupIdsChange,
}: HostsToolbarProps) {
  const { t } = useTranslation();

  return (
    <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <InputGroup className="sm:max-w-sm">
        <InputGroupAddon>
          <Search />
        </InputGroupAddon>
        <InputGroupInput
          aria-label={t("hostsPage.searchPlaceholder")}
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={t("hostsPage.searchPlaceholder")}
        />
        {search && (
          <InputGroupAddon align="inline-end">
            <InputGroupButton
              aria-label={t("hostsPage.clearSearch")}
              size="icon-xs"
              onClick={() => onSearchChange("")}
            >
              <X />
            </InputGroupButton>
          </InputGroupAddon>
        )}
      </InputGroup>
      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
        <HostGroupsManagerDialog
          groups={groups}
          pending={pending}
          trigger={
            <Button type="button" variant="outline">
              <FolderTree />
              {t("hostsPage.manageGroups")}
            </Button>
          }
        />


        <HostGroupsFilter
          groups={groups}
          selectedGroupIds={selectedGroupIds}
          onChange={onSelectedGroupIdsChange}
        />
      </div>
    </div>
  );
}

type HostGroupsFilterProps = {
  groups: HostGroupType[];
  selectedGroupIds: string[];
  onChange: (groupIds: string[]) => void;
};

function HostGroupsFilter({
  groups,
  selectedGroupIds,
  onChange,
}: HostGroupsFilterProps) {
  const { t } = useTranslation();
  const groupsById = useMemo(
    () => new Map(groups.map((group) => [group.id, group])),
    [groups],
  );
  const selectedGroups = selectedGroupIds.flatMap((groupId) => {
    const group = groupsById.get(groupId);
    return group ? [group] : [];
  });

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="min-h-9 min-w-56 justify-between whitespace-normal"
          disabled={!groups.length}
        >
          <span className="flex min-w-0 flex-wrap gap-1">
            {selectedGroups.length ? (
              selectedGroups.map((group) => (
                <Badge key={group.id} variant="secondary">
                  {group.name}
                </Badge>
              ))
            ) : (
              <span className="truncate">
                {groups.length
                  ? t("hostsPage.allGroups")
                : t("hostsPage.noGroupsShort")}
              </span>
            )}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-2">
        <div className="space-y-1">
          <button
            type="button"
            className="w-full rounded-md px-2 py-1.5 text-start text-sm hover:bg-accent"
            onClick={() => onChange([])}
          >
            {t("hostsPage.allGroups")}
          </button>
          {groups.map((group) => {
            const checked = selectedGroupIds.includes(group.id);
            return (
              <label
                key={group.id}
                className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-accent"
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={(nextChecked) => {
                    const isChecked = nextChecked === true;
                    onChange(
                      isChecked
                        ? [...selectedGroupIds, group.id]
                        : selectedGroupIds.filter((id) => id !== group.id),
                    );
                  }}
                />
                <span className="min-w-0 flex-1 truncate">{group.name}</span>
              </label>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
