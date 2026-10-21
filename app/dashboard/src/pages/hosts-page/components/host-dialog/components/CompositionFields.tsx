import { Controller, useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";
import {
  Field,
  FieldDescription,
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
import type { HostCapabilities, HostType } from "../../../types";
import type { HostFormValues } from "../lib/form";
import { ClientBalancerFields } from "./ClientBalancerFields";
import { LinkedHostsField } from "./LinkedHostsField";
import { balancerStrategies } from "../../../lib/balancer";

export function CompositionFields({
  hosts,
  capabilities,
  pending,
}: {
  hosts: HostType[];
  capabilities: HostCapabilities;
  pending: boolean;
}) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  return (
    <FieldGroup>
      <FieldDescription>{t("hostEditor.compositionHint")}</FieldDescription>
      <LinkedHostsField hosts={hosts} pending={pending} />
      <Field>
        <FieldLabel htmlFor="balancer-remark">
          {t("hostEditor.profileRemark")}
        </FieldLabel>
        <Input
          id="balancer-remark"
          disabled={pending}
          {...form.register("balancer_remark")}
        />
      </Field>
      <Controller
        control={form.control}
        name="balancer_strategy"
        render={({ field }) => (
          <Field>
            <FieldLabel htmlFor="balancer-strategy">
              {t("hostEditor.strategy")}
            </FieldLabel>
            <Select
              value={field.value}
              onValueChange={field.onChange}
              disabled={pending}
            >
              <SelectTrigger id="balancer-strategy">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {balancerStrategies.map((value) => (
                    <SelectItem key={value} value={value}>
                      {t(`hostEditor.strategies.${value}`)}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
        )}
      />
      <Field>
        <FieldLabel htmlFor="balancer-probe-url">
          {t("hostEditor.probeUrl")}
        </FieldLabel>
        <Input
          id="balancer-probe-url"
          disabled={pending}
          {...form.register("balancer_probe_url")}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="balancer-probe-interval">
          {t("hostEditor.probeInterval")}
        </FieldLabel>
        <Input
          id="balancer-probe-interval"
          type="number"
          min={10}
          max={86400}
          disabled={pending}
          {...form.register("balancer_probe_interval", { valueAsNumber: true })}
        />
        <FieldError errors={[form.formState.errors.balancer_probe_interval]} />
      </Field>
      <ClientBalancerFields capabilities={capabilities} pending={pending} />
    </FieldGroup>
  );
}
