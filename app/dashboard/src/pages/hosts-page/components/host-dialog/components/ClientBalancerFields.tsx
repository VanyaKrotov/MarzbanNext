import { X } from "lucide-react";
import { Controller, useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { balancerTargets, type BalancerTarget } from "../../../lib/balancer";
import type { HostCapabilities } from "../../../types";
import type { HostFormValues } from "../lib/form";
import { BalancerOptionField } from "./BalancerOptionField";
import { LeastLoadFields } from "./LeastLoadFields";

type ClientBalancerFieldsProps = {
  capabilities: HostCapabilities;
  pending: boolean;
};

export function ClientBalancerFields({
  capabilities,
  pending,
}: ClientBalancerFieldsProps) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const clients = useWatch({ control: form.control, name: "balancer_clients" });
  const availableTargets = balancerTargets.filter(
    (target) => !(target in clients) && target in capabilities.strategies,
  );

  const addClient = (value: string) => {
    const target = availableTargets.find((item) => item === value);
    if (target)
      form.setValue(`balancer_clients.${target}`, {}, { shouldDirty: true });
  };

  return (
    <>
      {balancerTargets
        .filter((target) => target in clients)
        .map((target) => (
          <ClientBalancerEditor
            key={target}
            target={target}
            capabilities={capabilities}
            pending={pending}
          />
        ))}
      {availableTargets.length > 0 && (
        <Select value="" disabled={pending} onValueChange={addClient}>
          <SelectTrigger aria-label={t("hostEditor.addClientSettings")}>
            <SelectValue placeholder={t("hostEditor.addClientSettings")} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {availableTargets.map((target) => (
                <SelectItem key={target} value={target}>
                  {t(`subscriptionTemplates.formats.${target}`)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      )}
    </>
  );
}

function ClientBalancerEditor({
  target,
  capabilities,
  pending,
}: ClientBalancerFieldsProps & { target: BalancerTarget }) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const generalStrategy = useWatch({
    control: form.control,
    name: "balancer_strategy",
  });
  const strategy = useWatch({
    control: form.control,
    name: `balancer_clients.${target}.strategy`,
  });
  const name = t(`subscriptionTemplates.formats.${target}`);

  return (
    <FieldGroup>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{name}</span>
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          disabled={pending}
          aria-label={t("hostEditor.removeParameter", { name })}
          onClick={() => form.unregister(`balancer_clients.${target}`)}
        >
          <X />
        </Button>
      </div>
      <Controller
        control={form.control}
        name={`balancer_clients.${target}.strategy`}
        render={({ field }) => (
          <Field>
            <FieldLabel htmlFor={`balancer-${target}-strategy`}>
              {t("hostEditor.strategy")}
            </FieldLabel>
            <Select
              value={field.value ?? "inherit"}
              disabled={pending}
              onValueChange={(value) =>
                field.onChange(value === "inherit" ? undefined : value)
              }
            >
              <SelectTrigger ref={field.ref} id={`balancer-${target}-strategy`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="inherit">
                    {t("hostEditor.inheritStrategy")}
                  </SelectItem>
                  {(capabilities.strategies[target] ?? []).map((value) => (
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
      <BalancerOptionField
        name={`balancer_clients.${target}.probe_url`}
        label={t("hostEditor.probeUrl")}
        kind="text"
        pending={pending}
      />
      <BalancerOptionField
        name={`balancer_clients.${target}.probe_interval`}
        label={t("hostEditor.probeInterval")}
        kind="number"
        min={10}
        max={86400}
        pending={pending}
      />
      {target === "v2ray-json" ? (
        <BalancerOptionField
          name="balancer_clients.v2ray-json.enable_concurrency"
          label={t("hostEditor.enableConcurrency")}
          kind="boolean"
          pending={pending}
        />
      ) : (
        <BalancerOptionField
          name={`balancer_clients.${target}.tolerance`}
          label={t("hostEditor.tolerance")}
          kind="number"
          min={0}
          pending={pending}
        />
      )}
      {target === "clash-meta" && (
        <BalancerOptionField
          name="balancer_clients.clash-meta.lazy"
          label={t("hostEditor.lazy")}
          kind="boolean"
          pending={pending}
        />
      )}
      {target === "sing-box" && (
        <>
          <BalancerOptionField
            name="balancer_clients.sing-box.idle_timeout"
            label={t("hostEditor.idleTimeout")}
            kind="number"
            min={1}
            pending={pending}
          />
          <BalancerOptionField
            name="balancer_clients.sing-box.interrupt_existing_connections"
            label={t("hostEditor.interruptConnections")}
            kind="boolean"
            pending={pending}
          />
        </>
      )}
      {target === "v2ray-json" &&
        (strategy ?? generalStrategy) === "least_load" && (
          <LeastLoadFields pending={pending} />
        )}
    </FieldGroup>
  );
}
