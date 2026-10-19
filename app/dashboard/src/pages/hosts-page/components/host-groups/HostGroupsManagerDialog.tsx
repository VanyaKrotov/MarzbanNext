import {
  Edit2,
  FolderTree,
  LoaderCircle,
  Plus,
  Tags,
  Trash2,
} from "lucide-react";
import { useState, type ReactNode } from "react";
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
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { useDeleteHostGroupMutation } from "../../lib/query";
import type { HostGroupType } from "../../types";
import { HostGroupFormDialog } from "./HostGroupFormDialog";

type HostGroupsManagerDialogProps = {
  groups: HostGroupType[];
  pending?: boolean;
  trigger: ReactNode;
};

export function HostGroupsManagerDialog({
  groups,
  pending = false,
  trigger,
}: HostGroupsManagerDialogProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("hostsPage.groupsManagerTitle")}</DialogTitle>
        </DialogHeader>
        <div className="flex justify-end">
          <HostGroupFormDialog
            open={createOpen}
            onOpenChange={setCreateOpen}
            pending={pending}
            trigger={
              <Button type="button" size="sm">
                <Plus />
                {t("create")}
              </Button>
            }
          />
        </div>
        {groups.length ? (
          <div className="space-y-2">
            {groups.map((group) => (
              <HostGroupListItem key={group.id} group={group} pending={pending} />
            ))}
          </div>
        ) : (
          <Empty className="rounded-lg border">
            <EmptyHeader>
              <EmptyTitle>{t("hostsPage.noGroups")}</EmptyTitle>
              <EmptyDescription>
                {t("hostsPage.noGroupsManagerDescription")}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </DialogContent>
    </Dialog>
  );
}

function HostGroupListItem({
  group,
  pending,
}: {
  group: HostGroupType;
  pending: boolean;
}) {
  const { t } = useTranslation();
  const [editOpen, setEditOpen] = useState(false);

  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border p-3">
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex min-w-0 items-center gap-2">
          <FolderTree className="size-4 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <p className="truncate font-medium">{group.name}</p>
            <p className="truncate font-mono text-xs text-muted-foreground">
              {group.id}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {group.tags.length ? (
            group.tags.map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))
          ) : (
            <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
              <Tags className="size-3.5" />
              {t("hostsPage.noTags")}
            </span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 gap-1">
        <HostGroupFormDialog
          open={editOpen}
          onOpenChange={setEditOpen}
          pending={pending}
          group={group}
          trigger={
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              disabled={pending}
              aria-label={t("edit")}
            >
              <Edit2 />
            </Button>
          }
        />
        <DeleteHostGroupButton group={group} pending={pending} />
      </div>
    </div>
  );
}

function DeleteHostGroupButton({
  group,
  pending,
}: {
  group: HostGroupType;
  pending: boolean;
}) {
  const { t } = useTranslation();
  const deleteGroup = useDeleteHostGroupMutation();
  const deleting = pending || deleteGroup.isPending;

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          type="button"
          variant="destructive"
          size="icon-sm"
          disabled={deleting}
          aria-label={t("delete")}
        >
          <Trash2 />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogMedia className="bg-destructive/10 text-destructive">
            <Trash2 />
          </AlertDialogMedia>
          <AlertDialogTitle>{t("hostsPage.deleteGroupTitle")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("hostsPage.deleteGroupDescription", { name: group.name })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleting}>
            {t("cancel")}
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={deleting}
            onClick={() => deleteGroup.mutate(group.id)}
          >
            {deleting && <LoaderCircle className="animate-spin" />}
            {t("delete")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
