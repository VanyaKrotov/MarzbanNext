import { Controller, useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { InboundType } from "@/types/Inbound";
import type { HostFormValues } from "../lib/form";
import { VariablesPopover } from "./VariablesPopover";
import { GroupsField } from "./GroupsField";
import type { HostGroupType } from "../../../types";

export function CoreFields({
  inbounds,
  groups,
  pending,
}: {
  inbounds: InboundType[];
  groups: HostGroupType[];
  pending: boolean;
}) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const inboundId = useWatch({ control: form.control, name: "inbound_id" });
  const inbound = inbounds.find((item) => item.id === inboundId);
  return (
    <FieldGroup>
      <Field data-invalid={Boolean(form.formState.errors.remark)}>
        <div className="flex items-center gap-2">
          <FieldLabel htmlFor="host-remark">
            {t("hostEditor.remark")}
          </FieldLabel>
          <VariablesPopover />
        </div>
        <FieldGroup className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
          <Input
            id="host-remark"
            disabled={pending}
            aria-invalid={Boolean(form.formState.errors.remark)}
            {...form.register("remark")}
          />
          <Controller
            control={form.control}
            name="enabled"
            render={({ field }) => (
              <Switch
                id="host-enabled"
                aria-label={t("hostsPage.enabled")}
                checked={field.value}
                onCheckedChange={field.onChange}
                disabled={pending}
              />
            )}
          />
        </FieldGroup>
        <FieldError errors={[form.formState.errors.remark]} />
      </Field>
      <Controller
        control={form.control}
        name="inbound_id"
        render={({ field }) => (
          <Field>
            <FieldLabel htmlFor="host-inbound">
              {t("hostsPage.inbound")}
            </FieldLabel>
            <Select
              value={String(field.value)}
              onValueChange={(value) => field.onChange(Number(value))}
              disabled={pending}
            >
              <SelectTrigger id="host-inbound">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {inbounds.map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.tag} ({item.protocol}/{item.network}) —{" "}
                      {item.nodes.map((node) => node.name).join(", ") ||
                        t("hostsPage.unassignedNodes")}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
        )}
      />
      <GroupsField groups={groups} pending={pending} />
      <FieldGroup className="grid grid-cols-[minmax(0,1fr)_7rem] items-start gap-3">
        <Field data-invalid={Boolean(form.formState.errors.address)}>
          <FieldLabel htmlFor="host-address">
            {t("nodes.nodeAddress")}
          </FieldLabel>
          <Input
            id="host-address"
            disabled={pending}
            aria-invalid={Boolean(form.formState.errors.address)}
            {...form.register("address")}
          />
          <FieldError errors={[form.formState.errors.address]} />
        </Field>
        <Controller
          control={form.control}
          name="port"
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="host-port">
                {t("hostsDialog.port")}
              </FieldLabel>
              <Input
                id="host-port"
                type="number"
                min={1}
                max={65535}
                disabled={pending}
                aria-invalid={fieldState.invalid}
                placeholder={String(inbound?.port ?? "")}
                value={field.value ?? ""}
                onChange={(event) =>
                  field.onChange(
                    event.target.value === ""
                      ? null
                      : event.target.valueAsNumber,
                  )
                }
              />
              <FieldError errors={[fieldState.error]} />
            </Field>
          )}
        />
      </FieldGroup>
    </FieldGroup>
  );
}
