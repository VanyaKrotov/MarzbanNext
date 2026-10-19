import { zodResolver } from "@hookform/resolvers/zod";
import {
  Gauge,
  GripVertical,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import type { DragEvent, PropsWithChildren } from "react";
import { useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

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
  Combobox,
  ComboboxChip,
  ComboboxChips,
  ComboboxChipsInput,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyContent,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  generateErrorMessage,
  generateSuccessMessage,
} from "@/utils/toastHandler";

import {
  type SubscriptionBalancer,
  type SubscriptionBalancerPayload,
  type SubscriptionBalancerStrategy,
  useCreateSubscriptionBalancerMutation,
  useDeleteSubscriptionBalancerMutation,
  useReorderSubscriptionBalancersMutation,
  useSubscriptionBalancersQuery,
  useUpdateSubscriptionBalancerMutation,
} from "../../lib/subscription-balancers-query";
import { cn } from "@/lib/utils";
import { useHostsQuery } from "../../lib/query";
import type { HostType } from "../../types";

const balancerFormSchema = z.object({
  name: z.string().trim().min(1).max(256),
  enabled: z.boolean(),
  strategy: z.enum(["least_ping", "least_load", "random", "round_robin"]),
  probe_url: z
    .string()
    .url()
    .refine((value) => /^https?:\/\//i.test(value)),
  probe_interval: z.coerce.number().int().min(10).max(86400),
  host_ids: z.array(z.number()),
});

type BalancerFormValues = z.infer<typeof balancerFormSchema>;

const defaultValues: BalancerFormValues = {
  name: "",
  enabled: true,
  strategy: "least_ping",
  probe_url: "https://www.gstatic.com/generate_204",
  probe_interval: 300,
  host_ids: [],
};

function getFormValues(balancer?: SubscriptionBalancer): BalancerFormValues {
  return balancer
    ? {
        name: balancer.name,
        enabled: balancer.enabled,
        strategy: balancer.strategy,
        probe_url: balancer.probe_url,
        probe_interval: balancer.probe_interval,
        host_ids: balancer.host_ids,
      }
    : defaultValues;
}

function getHostLabel(host: HostType) {
  return host.remark || host.address;
}

function getHostDetails(host: HostType, noGroupsLabel: string) {
  const groups = host.groups.map((group) => group.name).join(", ");
  return `${host.inbound_tag} - ${groups || noGroupsLabel}`;
}

type BalancerDropTarget = {
  id: number;
  position: "before" | "after";
} | null;

export function SubscriptionBalancersDialog({ children }: PropsWithChildren) {
  const [open, onOpenChange] = useState(false);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="min-w-0 max-h-[calc(100svh-2rem)] max-w-[calc(100%-2rem)] overflow-y-auto sm:max-w-4xl">
        <SubscriptionBalancersContent />
      </DialogContent>
    </Dialog>
  );
}

function SubscriptionBalancersContent() {
  const { t } = useTranslation();
  const query = useSubscriptionBalancersQuery();
  const deleteBalancer = useDeleteSubscriptionBalancerMutation();
  const reorderBalancers = useReorderSubscriptionBalancersMutation();
  const updateBalancer = useUpdateSubscriptionBalancerMutation();
  const [editor, setEditor] = useState<SubscriptionBalancer | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleting, setDeleting] = useState<SubscriptionBalancer | null>(null);
  const [draggedBalancerId, setDraggedBalancerId] = useState<number | null>(
    null,
  );
  const [dropTarget, setDropTarget] = useState<BalancerDropTarget>(null);
  const balancers = query.data ?? [];

  const openEditor = (balancer?: SubscriptionBalancer) => {
    setEditor(balancer ?? null);
    setEditorOpen(true);
  };

  const resetDrag = () => {
    setDraggedBalancerId(null);
    setDropTarget(null);
  };

  const dropBalancer = (targetId: number) => {
    if (draggedBalancerId == null || dropTarget?.id !== targetId) {
      resetDrag();
      return;
    }

    const sourceIndex = balancers.findIndex(
      (balancer) => balancer.id === draggedBalancerId,
    );
    const targetIndex = balancers.findIndex(
      (balancer) => balancer.id === targetId,
    );
    if (sourceIndex < 0 || targetIndex < 0) {
      resetDrag();
      return;
    }

    const reordered = [...balancers];
    const [dragged] = reordered.splice(sourceIndex, 1);
    let insertIndex = targetIndex + (dropTarget.position === "after" ? 1 : 0);
    if (sourceIndex < insertIndex) insertIndex -= 1;
    reordered.splice(insertIndex, 0, dragged);

    if (sourceIndex !== insertIndex) {
      reorderBalancers.mutate(
        reordered.map((balancer) => balancer.id),
        { onError: (error) => generateErrorMessage(error) },
      );
    }
    resetDrag();
  };

  const createAction = (
    <Button type="button" size="sm" onClick={() => openEditor()}>
      <Plus />
      {t("create")}
    </Button>
  );

  return (
    <>
      <DialogHeader className="pe-8">
        <DialogTitle>{t("settingsPage.balancers.title")}</DialogTitle>
        <DialogDescription>
          {t("settingsPage.balancers.description")}
        </DialogDescription>
      </DialogHeader>
      <div className="mt-4 min-w-0">
        {query.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-18" />
            <Skeleton className="h-18" />
          </div>
        ) : query.isError ? (
          <Empty className="min-h-52 rounded-lg border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Gauge />
              </EmptyMedia>
              <EmptyTitle className="text-sm">
                {t("settingsPage.balancers.loadError")}
              </EmptyTitle>
            </EmptyHeader>
            <EmptyContent className="flex-row justify-center">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void query.refetch()}
              >
                <RefreshCw />
                {t("settingsPage.balancers.retry")}
              </Button>
              {createAction}
            </EmptyContent>
          </Empty>
        ) : balancers.length ? (
          <div className="space-y-3">
            <div className="flex justify-end">{createAction}</div>
            <div className="min-w-0 max-w-full overflow-hidden rounded-lg border">
              <Table className="w-full min-w-190">
                <TableHeader className="bg-muted/40">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-10" />
                    <TableHead>{t("settingsPage.balancers.name")}</TableHead>
                    <TableHead>
                      {t("settingsPage.balancers.strategyLabel")}
                    </TableHead>
                    <TableHead className="text-right">
                      {t("settingsPage.balancers.hosts")}
                    </TableHead>
                    <TableHead>
                      {t("settingsPage.balancers.probeUrl")}
                    </TableHead>
                    <TableHead className="w-20">
                      {t("settingsPage.balancers.enabled")}
                    </TableHead>
                    <TableHead className="w-24" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {balancers.map((balancer) => (
                    <BalancerListItem
                      key={balancer.id}
                      balancer={balancer}
                      pending={
                        deleteBalancer.isPending ||
                        reorderBalancers.isPending ||
                        updateBalancer.isPending
                      }
                      dragged={draggedBalancerId === balancer.id}
                      dropTarget={
                        dropTarget?.id === balancer.id
                          ? dropTarget.position
                          : null
                      }
                      onEdit={() => openEditor(balancer)}
                      onDelete={() => setDeleting(balancer)}
                      onEnabledChange={(enabled) =>
                        updateBalancer.mutate(
                          {
                            id: balancer.id,
                            balancer: {
                              name: balancer.name,
                              enabled,
                              strategy: balancer.strategy,
                              probe_url: balancer.probe_url,
                              probe_interval: balancer.probe_interval,
                              host_ids: balancer.host_ids,
                            },
                          },
                          { onError: (error) => generateErrorMessage(error) },
                        )
                      }
                      onDragStart={() => setDraggedBalancerId(balancer.id)}
                      onDragEnd={resetDrag}
                      onDragOver={(event) => {
                        event.preventDefault();
                        if (
                          draggedBalancerId == null ||
                          draggedBalancerId === balancer.id
                        ) {
                          return;
                        }

                        const bounds =
                          event.currentTarget.getBoundingClientRect();
                        const position =
                          event.clientY < bounds.top + bounds.height / 2
                            ? "before"
                            : "after";
                        setDropTarget((current) =>
                          current?.id === balancer.id &&
                          current.position === position
                            ? current
                            : { id: balancer.id, position },
                        );
                      }}
                      onDrop={() => dropBalancer(balancer.id)}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        ) : (
          <Empty className="min-h-52 rounded-lg border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Gauge />
              </EmptyMedia>
              <EmptyTitle className="text-sm">
                {t("settingsPage.balancers.empty")}
              </EmptyTitle>
            </EmptyHeader>
            <EmptyContent>{createAction}</EmptyContent>
          </Empty>
        )}
      </div>

      <BalancerEditorDialog
        key={editor?.id ?? "new"}
        balancer={editor}
        open={editorOpen}
        onOpenChange={setEditorOpen}
      />

      <AlertDialog
        open={Boolean(deleting)}
        onOpenChange={(nextOpen) => !nextOpen && setDeleting(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogMedia className="bg-destructive/10 text-destructive">
              <Trash2 />
            </AlertDialogMedia>
            <AlertDialogTitle>
              {t("settingsPage.balancers.deleteTitle")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("settingsPage.balancers.deleteDescription", {
                name: deleting?.name,
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteBalancer.isPending}>
              {t("cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteBalancer.isPending}
              onClick={() => {
                if (!deleting) return;
                deleteBalancer.mutate(deleting.id, {
                  onSuccess: () => {
                    setDeleting(null);
                    generateSuccessMessage(t("settingsPage.balancers.deleted"));
                  },
                  onError: (error) => generateErrorMessage(error),
                });
              }}
            >
              {deleteBalancer.isPending && (
                <LoaderCircle className="animate-spin" />
              )}
              {t("delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function BalancerListItem({
  balancer,
  pending,
  dragged,
  dropTarget,
  onEdit,
  onDelete,
  onEnabledChange,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}: {
  balancer: SubscriptionBalancer;
  pending: boolean;
  dragged: boolean;
  dropTarget: "before" | "after" | null;
  onEdit: () => void;
  onDelete: () => void;
  onEnabledChange: (enabled: boolean) => void;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDragOver: (event: DragEvent<HTMLTableRowElement>) => void;
  onDrop: () => void;
}) {
  const { t } = useTranslation();

  return (
    <TableRow
      className={cn(
        dragged && "opacity-50",
        dropTarget === "before" && "border-t-2 border-t-primary",
        dropTarget === "after" && "border-b-2 border-b-primary",
      )}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <TableCell>
        <span
          draggable={!pending}
          className={cn("block w-fit text-muted-foreground", {
            "cursor-grab active:cursor-grabbing": !pending,
            "opacity-30": pending,
          })}
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
        >
          <GripVertical className="size-4" />
        </span>
      </TableCell>
      <TableCell className="max-w-60">
        <span className="block truncate font-medium">{balancer.name}</span>
      </TableCell>
      <TableCell>
        {t(`settingsPage.balancers.strategy.${balancer.strategy}`)}
      </TableCell>
      <TableCell align="right">{balancer.host_ids.length}</TableCell>
      <TableCell className="max-w-72">
        <span className="block truncate text-xs text-muted-foreground">
          {balancer.probe_url}
        </span>
        <span className="text-xs text-muted-foreground">
          {balancer.probe_interval}s
        </span>
      </TableCell>
      <TableCell>
        <Switch
          checked={balancer.enabled}
          disabled={pending}
          aria-label={
            balancer.enabled
              ? t("settingsPage.balancers.enabled")
              : t("settingsPage.balancers.disabled")
          }
          onCheckedChange={onEnabledChange}
        />
      </TableCell>
      <TableCell>
        <div className="flex justify-end gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            disabled={pending}
            aria-label={t("settingsPage.balancers.edit")}
            onClick={onEdit}
          >
            <Pencil />
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="icon-sm"
            disabled={pending}
            aria-label={t("settingsPage.balancers.delete")}
            onClick={onDelete}
          >
            <Trash2 />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

function BalancerEditorDialog({
  balancer,
  open,
  onOpenChange,
}: {
  balancer: SubscriptionBalancer | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100svh-2rem)] max-w-[calc(100%-2rem)] overflow-y-auto sm:max-w-3xl">
        {open && (
          <BalancerEditorContent
            balancer={balancer}
            onOpenChange={onOpenChange}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function BalancerEditorContent({
  balancer,
  onOpenChange,
}: {
  balancer: SubscriptionBalancer | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const createBalancer = useCreateSubscriptionBalancerMutation();
  const updateBalancer = useUpdateSubscriptionBalancerMutation();
  const hostsQuery = useHostsQuery();
  const hosts = hostsQuery.data ?? [];
  const hostsById = useMemo(
    () => new Map(hosts.map((host) => [host.id, host])),
    [hosts],
  );
  const [hostComboboxAnchor, setHostComboboxAnchor] =
    useState<HTMLDivElement | null>(null);
  const form = useForm<BalancerFormValues>({
    resolver: zodResolver(balancerFormSchema),
    mode: "onChange",
    defaultValues: getFormValues(balancer ?? undefined),
  });
  const pending = createBalancer.isPending || updateBalancer.isPending;

  const save = form.handleSubmit((values) => {
    const payload: SubscriptionBalancerPayload = values;
    const options = {
      onSuccess: () => {
        generateSuccessMessage(t("settingsPage.balancers.saved"));
        onOpenChange(false);
      },
      onError: (error: unknown) => generateErrorMessage(error),
    };

    if (balancer) {
      updateBalancer.mutate({ id: balancer.id, balancer: payload }, options);
    } else {
      createBalancer.mutate(payload, options);
    }
  });

  return (
    <form className="grid gap-5" onSubmit={save}>
      <DialogHeader className="pe-8">
        <DialogTitle>
          {balancer
            ? t("settingsPage.balancers.edit")
            : t("settingsPage.balancers.create")}
        </DialogTitle>
      </DialogHeader>
      <Field>
        <FieldLabel htmlFor="balancer-name">
          {t("settingsPage.balancers.name")}
        </FieldLabel>
        <Input
          id="balancer-name"
          disabled={pending}
          {...form.register("name")}
        />
        <FieldError errors={[form.formState.errors.name]} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Controller
          control={form.control}
          name="strategy"
          render={({ field }) => (
            <Field>
              <FieldLabel>
                {t("settingsPage.balancers.strategyLabel")}
              </FieldLabel>
              <Select
                value={field.value}
                disabled={pending}
                onValueChange={field.onChange}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {(
                      [
                        "least_ping",
                        "least_load",
                        "random",
                        "round_robin",
                      ] as SubscriptionBalancerStrategy[]
                    ).map((strategy) => (
                      <SelectItem key={strategy} value={strategy}>
                        {t(`settingsPage.balancers.strategy.${strategy}`)}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          )}
        />
        <Field>
          <FieldLabel htmlFor="balancer-interval">
            {t("settingsPage.balancers.interval")}
          </FieldLabel>
          <Input
            id="balancer-interval"
            type="number"
            min={10}
            max={86400}
            disabled={pending}
            {...form.register("probe_interval")}
          />
          <FieldError errors={[form.formState.errors.probe_interval]} />
        </Field>
      </div>
      <Field>
        <FieldLabel htmlFor="balancer-probe-url">
          {t("settingsPage.balancers.probeUrl")}
        </FieldLabel>
        <Input
          id="balancer-probe-url"
          type="url"
          disabled={pending}
          {...form.register("probe_url")}
        />
        <FieldError errors={[form.formState.errors.probe_url]} />
      </Field>
      <Controller
        control={form.control}
        name="host_ids"
        render={({ field }) => {
          const selectedHosts = field.value.flatMap((hostId) => {
            const host = hostsById.get(hostId);
            return host ? [host] : [];
          });

          return (
            <Field>
              <FieldLabel>{t("settingsPage.balancers.hosts")}</FieldLabel>
              <Combobox
                multiple
                items={hosts}
                value={selectedHosts}
                disabled={pending || hostsQuery.isLoading || hostsQuery.isError}
                itemToStringLabel={getHostLabel}
                onValueChange={(nextHosts) =>
                  field.onChange(nextHosts.map((host) => host.id))
                }
              >
                <div ref={setHostComboboxAnchor} className="w-full">
                  <ComboboxChips className="w-full">
                    {selectedHosts.map((host) => (
                      <ComboboxChip key={host.id} className="max-w-full">
                        <span className="max-w-48 truncate">
                          {getHostLabel(host)}
                        </span>
                      </ComboboxChip>
                    ))}
                    <ComboboxChipsInput
                      aria-label={t("settingsPage.balancers.hosts")}
                      placeholder={
                        selectedHosts.length
                          ? undefined
                          : t("settingsPage.balancers.selectHosts")
                      }
                    />
                  </ComboboxChips>
                </div>
                <ComboboxContent
                  anchor={hostComboboxAnchor}
                  className="w-(--anchor-width)! min-w-(--anchor-width)!"
                >
                  <ComboboxList>
                    {(host) => (
                      <ComboboxItem key={host.id} value={host}>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">
                            {getHostLabel(host)}
                          </span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {getHostDetails(host, t("hostsPage.noGroups"))}
                          </span>
                        </span>
                      </ComboboxItem>
                    )}
                  </ComboboxList>
                  <ComboboxEmpty>
                    {t("settingsPage.balancers.hostsEmpty")}
                  </ComboboxEmpty>
                </ComboboxContent>
              </Combobox>
              {hostsQuery.isError && (
                <p className="text-sm text-destructive">
                  {t("settingsPage.balancers.hostsLoadError")}
                </p>
              )}
            </Field>
          );
        }}
      />
      <div className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <Controller
          control={form.control}
          name="enabled"
          render={({ field }) => (
            <Field
              orientation="horizontal"
              className="w-full justify-between sm:w-auto"
            >
              <FieldLabel htmlFor="balancer-enabled">
                {t("settingsPage.balancers.enabled")}
              </FieldLabel>
              <Switch
                id="balancer-enabled"
                checked={field.value}
                disabled={pending}
                onCheckedChange={field.onChange}
              />
            </Field>
          )}
        />
        <DialogFooter className="w-full sm:w-auto">
          <Button
            type="button"
            variant="outline"
            disabled={pending}
            onClick={() => onOpenChange(false)}
          >
            {t("cancel")}
          </Button>
          <Button type="submit" disabled={pending || !form.formState.isValid}>
            {pending && <LoaderCircle className="animate-spin" />}
            {t(balancer ? "core.save" : "create")}
          </Button>
        </DialogFooter>
      </div>
    </form>
  );
}
