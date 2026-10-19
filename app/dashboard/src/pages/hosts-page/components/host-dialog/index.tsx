import { zodResolver } from "@hookform/resolvers/zod";
import { FormProvider, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  defaultBindings,
  useAllTemplatesQuery,
  type SubscriptionTemplate,
} from "@/pages/subscription-templates-page/lib/query";
import type { HostGroupType, HostType } from "../../types";
import { useInboundsQuery } from "../../lib/query";

import { AdvancedFields } from "./components/AdvancedFields";
import { BasicFields } from "./components/BasicFields";
import { HostDialogHeader } from "./components/DialogHeader";
import { FormActions } from "./components/FormActions";
import { GroupsField } from "./components/GroupsField";
import { SubscriptionTemplatesField } from "./components/SubscriptionTemplatesField";
import {
  getHostFormValues,
  hostFormSchema,
  type HostFormValues,
} from "./lib/form";

export type { HostFormValues } from "./lib/form";

type HostDialogProps = {
  open: boolean;
  host: HostType | null;
  inboundTag: string | null;
  hostGroups: HostGroupType[];
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (values: HostFormValues) => void;
};

export function HostDialog({
  open,
  host,
  inboundTag,
  hostGroups,
  pending,
  onOpenChange,
  onSubmit,
}: HostDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-2xl">
        <HostDialogContent
          host={host}
          inboundTag={inboundTag}
          hostGroups={hostGroups}
          pending={pending}
          onSubmit={onSubmit}
        />
      </DialogContent>
    </Dialog>
  );
}

function HostDialogContent({
  host,
  inboundTag,
  pending,
  onSubmit,
  hostGroups,
}: Omit<HostDialogProps, "open" | "onOpenChange">) {
  const { t } = useTranslation();
  const {
    data: inbounds = [],
    isLoading: inboundsLoading,
    isError: inboundsError,
  } = useInboundsQuery(inboundTag ?? void 0);
  const templatesQuery = useAllTemplatesQuery();

  return (
    <>
      <HostDialogHeader isEditing={Boolean(host)} />
      {inboundsLoading || !templatesQuery.isFetchedAfterMount ? (
        <div className="space-y-3">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (inboundsError && !inbounds.length) ||
        (templatesQuery.isError && !templatesQuery.data) ||
        !inbounds.length ? (
        <p className="rounded-lg border p-4 text-sm text-muted-foreground">
          {inboundsError || templatesQuery.isError
            ? t("hostsPage.loadErrorDescription")
            : t("hostsPage.noInboundsDescription")}
        </p>
      ) : (
        <HostForm
          host={host}
          inboundTag={inboundTag ?? inbounds[0].tag}
          hostGroups={hostGroups}
          pending={pending}
          onSubmit={onSubmit}
          inbounds={inbounds}
          templates={templatesQuery.data ?? []}
        />
      )}
    </>
  );
}

function HostForm({
  host,
  inboundTag,
  hostGroups,
  pending,
  onSubmit,
  inbounds,
  templates,
}: {
  host: HostType | null;
  inboundTag: string;
  hostGroups: HostGroupType[];
  pending: boolean;
  onSubmit: (values: HostFormValues) => void;
  inbounds: NonNullable<ReturnType<typeof useInboundsQuery>["data"]>;
  templates: SubscriptionTemplate[];
}) {
  // Mount after both queries resolve. Refetches must never reset a user's choices.
  const form = useForm<HostFormValues>({
    resolver: zodResolver(hostFormSchema),
    defaultValues: getHostFormValues(
      inboundTag,
      host,
      defaultBindings(templates),
    ),
  });
  return (
    <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
      <FormProvider {...form}>
        <BasicFields inbounds={inbounds} pending={pending} />
        <GroupsField groups={hostGroups} pending={pending} />
        <SubscriptionTemplatesField templates={templates} pending={pending} />
        <AdvancedFields pending={pending} inbounds={inbounds} />
        <FormActions isEditing={Boolean(host)} pending={pending} />
      </FormProvider>
    </form>
  );
}
