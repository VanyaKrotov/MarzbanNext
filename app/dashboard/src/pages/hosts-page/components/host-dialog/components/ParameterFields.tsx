import { Controller, useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { InboundType } from "@/types/Inbound";
import type { HostFormValues } from "../lib/form";
import type { HostParameterDefinition } from "../lib/parameters";
import { VariablesPopover } from "./VariablesPopover";

export function CoreFields({ inbounds, pending }: { inbounds: InboundType[]; pending: boolean }) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const inboundId = useWatch({ control: form.control, name: "inbound_id" });
  const inbound = inbounds.find((item) => item.id === inboundId);
  return <FieldGroup>
    <Field data-invalid={Boolean(form.formState.errors.remark)}>
      <div className="flex items-center gap-2"><FieldLabel htmlFor="host-remark">{t("hostEditor.remark")}</FieldLabel><VariablesPopover /></div>
      <Input id="host-remark" disabled={pending} aria-invalid={Boolean(form.formState.errors.remark)} {...form.register("remark")} />
      <FieldError errors={[form.formState.errors.remark]} />
    </Field>
    <Controller control={form.control} name="inbound_id" render={({ field }) => <Field>
      <FieldLabel htmlFor="host-inbound">{t("hostsPage.inbound")}</FieldLabel>
      <Select value={String(field.value)} onValueChange={(value) => field.onChange(Number(value))} disabled={pending}>
        <SelectTrigger id="host-inbound"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>
          {inbounds.map((item) => <SelectItem key={item.id} value={String(item.id)}>
            {item.tag} ({item.protocol}/{item.network}) — {item.nodes.map((node) => node.name).join(", ") || t("hostsPage.unassignedNodes")}
          </SelectItem>)}
        </SelectGroup></SelectContent>
      </Select>
    </Field>} />
    <Field data-invalid={Boolean(form.formState.errors.address)}>
      <FieldLabel htmlFor="host-address">{t("nodes.nodeAddress")}</FieldLabel>
      <Input id="host-address" disabled={pending} aria-invalid={Boolean(form.formState.errors.address)} {...form.register("address")} />
      <FieldError errors={[form.formState.errors.address]} />
    </Field>
    <Controller control={form.control} name="port" render={({ field, fieldState }) => <Field data-invalid={fieldState.invalid}>
      <FieldLabel htmlFor="host-port">{t("hostsDialog.port")}</FieldLabel>
      <Input id="host-port" type="number" min={1} max={65535} disabled={pending} aria-invalid={fieldState.invalid}
        placeholder={String(inbound?.port ?? "")} value={field.value ?? ""}
        onChange={(event) => field.onChange(event.target.value === "" ? null : event.target.valueAsNumber)} />
      <FieldDescription>{t("hostEditor.inheritedPort")}</FieldDescription><FieldError errors={[fieldState.error]} />
    </Field>} />
    <Controller control={form.control} name="enabled" render={({ field }) => <Field orientation="horizontal">
      <Switch id="host-enabled" checked={field.value} onCheckedChange={field.onChange} disabled={pending} />
      <FieldLabel htmlFor="host-enabled">{t("hostsPage.enabled")}</FieldLabel>
    </Field>} />
  </FieldGroup>;
}

export function ParameterField({ definition, pending, incompatible }: {
  definition: HostParameterDefinition; pending: boolean; incompatible: boolean;
}) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const explicitEmpty = useWatch({ control: form.control, name: "explicit_empty" });
  return <Controller control={form.control} name={`parameters.${definition.id}`} render={({ field, fieldState }) => <Field data-invalid={fieldState.invalid || incompatible}>
    <FieldLabel htmlFor={`host-parameter-${definition.id}`} className="sr-only">{t(definition.labelKey)}</FieldLabel>
    {definition.kind === "boolean" || definition.kind === "security" ? <Select disabled={pending} value={field.value || "__inherit__"}
      onValueChange={(value) => field.onChange(value === "__inherit__" ? "" : value)}>
      <SelectTrigger ref={field.ref} id={`host-parameter-${definition.id}`} aria-invalid={fieldState.invalid}><SelectValue /></SelectTrigger><SelectContent><SelectGroup>
        <SelectItem value="__inherit__">{t("hostEditor.inherit")}</SelectItem>
        {(definition.kind === "boolean" ? [["true", "hostsDialog.enabled"], ["false", "hostsDialog.disabled"]] : [["tls", "TLS"], ["none", "hostEditor.noSecurity"]])
          .map(([value, label]) => <SelectItem key={value} value={value}>{t(label)}</SelectItem>)}
      </SelectGroup></SelectContent>
    </Select> : definition.kind === "json" ? <Textarea {...field} value={field.value ?? ""} disabled={pending}
      id={`host-parameter-${definition.id}`} aria-invalid={fieldState.invalid} rows={6} className="font-mono text-xs" dir="ltr"
      placeholder={definition.id === "xhttp_extra" ? '{"scMaxBufferedPosts":0,"xPaddingObfsMode":false,"uplinkHTTPMethod":"PUT"}' : undefined} />
      : <>
        <Input {...field} id={`host-parameter-${definition.id}`} value={field.value ?? ""} disabled={pending || explicitEmpty.includes(definition.id)} aria-invalid={fieldState.invalid} />
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={explicitEmpty.includes(definition.id)} disabled={pending}
          onCheckedChange={(checked) => {
            form.setValue("explicit_empty", checked ? [...explicitEmpty, definition.id] : explicitEmpty.filter((id) => id !== definition.id));
            if (checked) field.onChange("");
          }} />
          {t("hostEditor.explicitEmpty")}</label>
      </>}
    {definition.id === "xhttp_extra" && <FieldDescription>{t("hostEditor.extraHint")}</FieldDescription>}
    {incompatible && <FieldError>{t("hostEditor.incompatibleInbound")}</FieldError>}
    <FieldError errors={[fieldState.error]} />
  </Field>} />;
}

export function StandaloneField({ pending }: { pending: boolean }) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  return <Controller control={form.control} name="show_when_composed" render={({ field }) => <Field>
    <Switch aria-label={t("hostEditor.showWhenComposed")} checked={field.value} onCheckedChange={field.onChange} disabled={pending} />
    <FieldDescription>{t("hostEditor.showWhenComposedHint")}</FieldDescription>
  </Field>} />;
}
