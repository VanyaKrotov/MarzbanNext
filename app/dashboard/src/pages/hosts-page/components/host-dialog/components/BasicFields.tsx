import { useMemo } from "react";
import { Controller, useFormContext } from "react-hook-form";
import find from "lodash/find";
import { useTranslation } from "react-i18next";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useComboboxAnchor } from "@/components/ui/combobox";
import type { InboundType } from "types/Inbound";

import type { HostFormValues } from "../lib/form";
import { HostTextField } from "./FormFields";
import { InfoTooltip } from "./InfoTooltip";
import { VariablesPopover } from "./VariablesPopover";

type InboundGroup = {
  key: string;
  label: string;
  inbounds: InboundType[];
};

function getInboundLabel(inbound: InboundType) {
  return `${inbound.tag} (${inbound.protocol}/${inbound.network})`;
}

function groupInboundsByNodes(
  inbounds: InboundType[],
  unassignedLabel: string,
): InboundGroup[] {
  const groups = new Map<string, InboundGroup>();

  for (const inbound of inbounds) {
    const nodes = [...inbound.nodes].sort((left, right) => left.id - right.id);
    const key = nodes.map((node) => node.id).join(",") || "unassigned";
    const label = nodes.length
      ? [...nodes]
          .sort(
            (left, right) =>
              left.name.localeCompare(right.name) || left.id - right.id,
          )
          .map((node) => node.name)
          .join(", ")
      : unassignedLabel;
    const group = groups.get(key);

    if (group) {
      group.inbounds.push(inbound);
    } else {
      groups.set(key, { key, label, inbounds: [inbound] });
    }
  }

  return [...groups.values()];
}

export function BasicFields({
  inbounds,
  pending,
}: {
  inbounds: InboundType[];
  pending: boolean;
}) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const inboundComboboxAnchor = useComboboxAnchor();
  const inboundGroups = groupInboundsByNodes(
    inbounds,
    t("hostsPage.unassignedNodes"),
  );
  const activeInboundTag = form.watch("inboundTag");
  const activeInbound = useMemo(
    () => find(inbounds, { tag: activeInboundTag }),
    [inbounds, activeInboundTag],
  );

  return (
    <>
      <Field>
        <FieldLabel htmlFor="host-inbound">{t("hostsPage.inbound")}</FieldLabel>
        <Controller
          control={form.control}
          name="inboundTag"
          render={({ field }) => (
            <Select
              value={field.value}
              disabled={pending}
              onValueChange={(inbound) => {
                field.onChange(inbound, {
                  shouldDirty: true,
                  shouldValidate: true,
                });
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {inboundGroups.map(({ inbounds, key, label }) => (
                  <SelectGroup key={key}>
                    <SelectLabel>{label}</SelectLabel>
                    {inbounds.map((inbound) => (
                      <SelectItem key={inbound.tag} value={inbound.tag}>
                        {getInboundLabel(inbound)}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </Field>

      <Field data-invalid={Boolean(form.formState.errors.remark)}>
        <div className="flex items-center gap-1.5">
          <FieldLabel htmlFor="host-remark">{t("hostsPage.name")}</FieldLabel>
          <VariablesPopover />
        </div>
        <Input
          id="host-remark"
          placeholder={t("hostsPage.namePlaceholder")}
          disabled={pending}
          {...form.register("remark")}
        />
        <FieldError errors={[form.formState.errors.remark]} />
      </Field>

      <div className="grid gap-4 sm:grid-cols-[1fr_180px]">
        <HostTextField
          id="host-address"
          label={t("nodes.nodeAddress")}
          placeholder="example.com"
          error={form.formState.errors.address?.message}
          disabled={pending}
          {...form.register("address")}
        />
        <Controller
          name="port"
          control={form.control}
          render={({ field }) => (
            <Field>
              <div className="flex items-center gap-1.5">
                <FieldLabel htmlFor="host-port">
                  {t("hostsDialog.port")}
                </FieldLabel>
                <InfoTooltip content={t("hostsDialog.port.info")} />
              </div>
              <Input
                id="host-port"
                type="number"
                min="1"
                placeholder={String(activeInbound?.port ?? 8080)}
                disabled={pending}
                value={field.value ?? ""}
                onChange={(event) =>
                  field.onChange(
                    event.target.value ? event.target.valueAsNumber : null,
                  )
                }
              />
            </Field>
          )}
        />
      </div>
    </>
  );
}
