import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, X } from "lucide-react";
import { useRef } from "react";
import { FormProvider, useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { FieldDescription } from "@/components/ui/field";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { defaultBindings, useAllTemplatesQuery, type SubscriptionTemplate } from "@/pages/subscription-templates-page/lib/query";
import type { InboundType } from "@/types/Inbound";
import { useHostCapabilitiesQuery, useHostsQuery, useInboundsQuery } from "../../lib/query";
import type { HostCapabilities, HostGroupType, HostType } from "../../types";
import { GroupsField } from "./components/GroupsField";
import { SubscriptionTemplatesPopover } from "./components/SubscriptionTemplatesPopover";
import { CoreFields, ParameterField, StandaloneField } from "./components/ParameterFields";
import { CompositionFields } from "./components/CompositionFields";
import { getHostFormValues, hostFormSchema, ParameterError, toHostPayload, type HostFormValues } from "./lib/form";
import { hostParameters } from "./lib/parameters";
export type { HostFormValues } from "./lib/form";

type HostDialogProps = {
  open: boolean; host: HostType | null; inboundTag: string | null; hostGroups: HostGroupType[];
  pending: boolean; onOpenChange: (open: boolean) => void; onSubmit: (values: HostFormValues) => void;
};
export function HostDialog(props: HostDialogProps) {
  return <Dialog open={props.open} onOpenChange={props.onOpenChange}>
    <DialogContent aria-describedby={undefined} className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-2xl"><HostDialogContent {...props} /></DialogContent>
  </Dialog>;
}
function HostDialogContent(props: HostDialogProps) {
  const { t } = useTranslation();
  const inbounds = useInboundsQuery(props.inboundTag ?? undefined);
  const templates = useAllTemplatesQuery();
  const hosts = useHostsQuery();
  const capabilities = useHostCapabilitiesQuery();
  const queries = [inbounds, templates, hosts, capabilities];
  return <>
    <DialogTitle>{t(props.host ? "hostEditor.editTitle" : "hostEditor.createTitle")}</DialogTitle>
    {queries.some((query) => query.isLoading) ? <Skeleton className="h-48" />
      : queries.some((query) => query.isError) ? <FieldDescription>{t("hostsPage.loadErrorDescription")}</FieldDescription>
      : !inbounds.data?.length ? <FieldDescription>{t("hostsPage.noInboundsDescription")}</FieldDescription>
      : <HostForm {...props} inbounds={inbounds.data} templates={templates.data ?? []} hosts={hosts.data ?? []} capabilities={capabilities.data!} />}
  </>;
}
function HostForm({ host, hostGroups, pending, onSubmit, onOpenChange, inbounds, templates, hosts, capabilities }:
  HostDialogProps & { inbounds: InboundType[]; templates: SubscriptionTemplate[]; hosts: HostType[]; capabilities: HostCapabilities }) {
  const { t } = useTranslation();
  const form = useForm<HostFormValues>({ resolver: zodResolver(hostFormSchema),
    defaultValues: getHostFormValues(inbounds[0].id, host, defaultBindings(templates)) });
  const addParameterRef = useRef<HTMLButtonElement>(null);
  const selected = useWatch({ control: form.control, name: "selected" });
  const inboundId = useWatch({ control: form.control, name: "inbound_id" });
  const inbound = inbounds.find((item) => item.id === inboundId);
  const xhttp = inbound?.network === "xhttp" || inbound?.network === "splithttp";
  const special = [["groups", "hostsPage.groups"], ["templates", "subscriptionTemplates.title"],
    ["composition", "hostEditor.composition"], ["show_when_composed", "hostEditor.showWhenComposed"]] as const;
  const remove = (id: string) => {
    form.setValue("selected", selected.filter((value) => value !== id), { shouldDirty: true });
    form.clearErrors(`parameters.${id}`);
    if (id === "show_when_composed") form.setValue("show_when_composed", true);
    if (id === "composition") form.setValue("linked_host_ids", []);
    if (id === "groups") form.setValue("group_ids", []);
    requestAnimationFrame(() => addParameterRef.current?.focus());
  };
  const submit = (values: HostFormValues) => {
    try { toHostPayload(values); onSubmit(values); }
    catch (error) {
      if (error instanceof ParameterError) form.setError(`parameters.${error.parameter}`, { message: t(error.message) }, { shouldFocus: true });
      else throw error;
    }
  };
  return <FormProvider {...form}><form onSubmit={form.handleSubmit(submit)} className="flex flex-col gap-5">
    <CoreFields inbounds={inbounds} pending={pending} />
    {selected.map((id) => {
      const definition = hostParameters.find((item) => item.id === id);
      const label = definition?.labelKey ?? special.find(([key]) => key === id)?.[1] ?? id;
      return <section key={id} className="flex flex-col gap-3 rounded-lg border p-4">
        <div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{t(label)}</span>
          <Button type="button" variant="ghost" size="icon-sm" disabled={pending} onClick={() => remove(id)} aria-label={t("hostEditor.removeParameter", { name: t(label) })}><X /></Button></div>
        {definition ? <ParameterField definition={definition} pending={pending} incompatible={Boolean(definition.xhttpOnly && !xhttp)} />
          : id === "groups" ? <GroupsField groups={hostGroups} pending={pending} />
          : id === "templates" ? <SubscriptionTemplatesPopover templates={templates} pending={pending} />
          : id === "composition" ? <CompositionFields hosts={hosts.filter((item) => item.id !== host?.id)} capabilities={capabilities} pending={pending} />
          : <StandaloneField pending={pending} />}
      </section>;
    })}
    <Select value="" disabled={pending} onValueChange={(id) => {
      form.setValue("selected", [...selected, id], { shouldDirty: true });
      requestAnimationFrame(() => form.setFocus(`parameters.${id}`));
    }}><SelectTrigger ref={addParameterRef} aria-label={t("hostEditor.addParameter")}><SelectValue placeholder={t("hostEditor.addParameter")} /></SelectTrigger>
      <SelectContent><SelectGroup>
        {hostParameters.filter((item) => !selected.includes(item.id) && (!item.xhttpOnly || xhttp)).map((item) => <SelectItem key={item.id} value={item.id}>{t(item.labelKey)}</SelectItem>)}
        {special.filter(([id]) => !selected.includes(id)).map(([id, label]) => <SelectItem key={id} value={id}>{t(label)}</SelectItem>)}
      </SelectGroup></SelectContent>
    </Select>
    <div className="flex justify-end gap-2 border-t pt-4">
      <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>{t("cancel")}</Button>
      <Button type="submit" disabled={pending}>{pending && <LoaderCircle className="animate-spin" />}{t(host ? "core.save" : "create")}</Button>
    </div>
  </form></FormProvider>;
}
