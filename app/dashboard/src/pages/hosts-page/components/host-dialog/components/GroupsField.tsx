import { ChevronsUpDown, Plus } from "lucide-react";
import { useState } from "react";
import { Controller, useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { HostGroupFormDialog } from "../../host-groups/HostGroupFormDialog";
import type { HostGroupType } from "../../../types";
import type { HostFormValues } from "../lib/form";

export function GroupsField({
  groups,
  pending,
}: {
  groups: HostGroupType[];
  pending: boolean;
}) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const groupsById = new Map(groups.map((group) => [group.id, group]));
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  return (
    <Controller
      name="group_ids"
      control={form.control}
      render={({ field }) => {
        const selectedGroups = field.value.flatMap((groupId) => {
          const group = groupsById.get(groupId);
          return group ? [group] : [];
        });

        return (
          <Field>
            <div className="flex items-center justify-between gap-2">
              <FieldLabel>{t("hostsPage.groups")}</FieldLabel>
            </div>
            <div className="flex gap-2">
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-9 min-w-0 flex-1 justify-between whitespace-normal"
                    disabled={pending || !groups.length}
                  >
                    <span className="flex min-w-0 flex-wrap gap-1">
                      {selectedGroups.length ? (
                        selectedGroups.map((group) => (
                          <Badge key={group.id} variant="secondary">
                            {group.name}
                          </Badge>
                        ))
                      ) : (
                        <span className="truncate text-muted-foreground">
                          {groups.length
                            ? t("actions.select")
                            : t("hostsPage.noGroupsShort")}
                        </span>
                      )}
                    </span>
                    <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent
                  align="start"
                  className="max-h-72 overflow-y-auto p-2"
                >
                  <div className="space-y-1">
                    {groups.map((group) => {
                      const checked = field.value.includes(group.id);
                      return (
                        <label
                          key={group.id}
                          className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-accent"
                        >
                          <Checkbox
                            checked={checked}
                            onCheckedChange={(nextChecked) => {
                              const isChecked = nextChecked === true;
                              field.onChange(
                                isChecked
                                  ? [...field.value, group.id]
                                  : field.value.filter((id) => id !== group.id),
                              );
                            }}
                          />
                          <span className="min-w-0 flex-1 truncate">
                            {group.name}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </PopoverContent>
              </Popover>
              <HostGroupFormDialog
                open={createDialogOpen}
                onOpenChange={setCreateDialogOpen}
                pending={pending}
                onSaved={(group) => {
                  if (!field.value.includes(group.id)) {
                    field.onChange([...field.value, group.id]);
                  }
                }}
                trigger={
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    disabled={pending}
                    aria-label={t("hostsPage.addGroup")}
                  >
                    <Plus className="size-4" />
                  </Button>
                }
              />
            </div>
          </Field>
        );
      }}
    />
  );
}
