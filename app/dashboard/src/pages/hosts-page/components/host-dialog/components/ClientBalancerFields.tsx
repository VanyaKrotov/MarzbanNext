import { X } from "lucide-react";
import { Controller, useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { HostCapabilities, JsonObject } from "../../../types";
import type { HostFormValues } from "../lib/form";

type OptionDefinition = { key: string; label: string; kind?: "boolean" | "number"; min?: number; max?: number };
const commonOptions: OptionDefinition[] = [
  { key: "probe_url", label: "probeUrl" },
  { key: "probe_interval", label: "probeInterval", kind: "number", min: 10, max: 86400 },
];
const targetOptions: Record<string, OptionDefinition[]> = {
  "v2ray-json": [{ key: "enable_concurrency", label: "enableConcurrency", kind: "boolean" }],
  clash: [{ key: "tolerance", label: "tolerance", kind: "number", min: 0 }, { key: "lazy", label: "lazy", kind: "boolean" }],
  mihomo: [{ key: "tolerance", label: "tolerance", kind: "number", min: 0 }, { key: "lazy", label: "lazy", kind: "boolean" }],
  "sing-box": [{ key: "tolerance", label: "tolerance", kind: "number", min: 0 },
    { key: "idle_timeout", label: "idleTimeout", kind: "number", min: 1 },
    { key: "interrupt_existing_connections", label: "interruptConnections", kind: "boolean" }],
};

export function ClientBalancerFields({ capabilities, pending }: { capabilities: HostCapabilities; pending: boolean }) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const strategy = useWatch({ control: form.control, name: "balancer_strategy" });
  const clients = useWatch({ control: form.control, name: "balancer_clients" });
  return <>
    {Object.keys(clients).map((target) => <Field key={target}>
      <div className="flex items-center justify-between"><span className="text-sm font-medium">{target}</span>
        <Button type="button" size="icon-sm" variant="ghost" disabled={pending} aria-label={t("hostEditor.removeParameter", { name: target })}
          onClick={() => form.unregister(`balancer_clients.${target}`)}><X /></Button></div>
      <Controller control={form.control} name={`balancer_clients.${target}`} render={({ field }) => {
        const options = JSON.parse(field.value || "{}") as JsonObject;
        const change = (key: string, value: unknown) => {
          const next = { ...options };
          if (value === undefined) delete next[key]; else next[key] = value;
          if (key === "strategy" && value !== "least_load") delete next.strategy_settings;
          field.onChange(JSON.stringify(next));
        };
        return <>
          <FieldLabel htmlFor={`balancer-${target}-strategy`}>{t("hostEditor.strategy")}</FieldLabel>
          <Select value={String(options.strategy ?? "__inherit__")} disabled={pending} onValueChange={(strategy) => change("strategy", strategy === "__inherit__" ? undefined : strategy)}>
            <SelectTrigger id={`balancer-${target}-strategy`}><SelectValue /></SelectTrigger><SelectContent><SelectGroup>
              <SelectItem value="__inherit__">{t("hostEditor.inheritStrategy")}</SelectItem>
              {(capabilities.strategies[target] ?? []).map((value) => <SelectItem key={value} value={value}>{t(`hostEditor.strategies.${value}`)}</SelectItem>)}
            </SelectGroup></SelectContent>
          </Select>
          {[...commonOptions, ...targetOptions[target]].map((definition) => <Field key={definition.key}>
            <FieldLabel htmlFor={`balancer-${target}-${definition.key}`}>{t(`hostEditor.${definition.label}`)}</FieldLabel>
            {definition.kind === "boolean" ? <Select disabled={pending} value={String(options[definition.key] ?? "__inherit__")}
              onValueChange={(value) => change(definition.key, value === "__inherit__" ? undefined : value === "true")}>
              <SelectTrigger id={`balancer-${target}-${definition.key}`}><SelectValue /></SelectTrigger><SelectContent><SelectGroup>
                <SelectItem value="__inherit__">{t("hostEditor.defaultValue")}</SelectItem>
                <SelectItem value="true">{t("hostsDialog.enabled")}</SelectItem><SelectItem value="false">{t("hostsDialog.disabled")}</SelectItem>
              </SelectGroup></SelectContent>
            </Select> : <Input id={`balancer-${target}-${definition.key}`} disabled={pending} type={definition.kind === "number" ? "number" : "text"}
              min={definition.min} max={definition.max} placeholder={t("hostEditor.defaultValue")} value={String(options[definition.key] ?? "")}
              onChange={(event) => change(definition.key, event.target.value === "" ? undefined : definition.kind === "number" ? event.target.valueAsNumber : event.target.value)} />}
          </Field>)}
          {target === "v2ray-json" && (options.strategy ?? strategy) === "least_load" && <Field>
            <span className="text-sm font-medium">{t("hostEditor.leastLoadOptions")}</span>
            <LeastLoadFields value={options.strategy_settings} pending={pending} onChange={(value) => change("strategy_settings", value)} />
          </Field>}
          <FieldError errors={[form.formState.errors.parameters?.[`client_${target}`]]} />
        </>;
      }} />
    </Field>)}
    <Select value="" disabled={pending} onValueChange={(target) => form.setValue(`balancer_clients.${target}`, "{}", { shouldDirty: true })}>
      <SelectTrigger aria-label={t("hostEditor.addClientSettings")}><SelectValue placeholder={t("hostEditor.addClientSettings")} /></SelectTrigger><SelectContent><SelectGroup>
        {Object.keys(capabilities.strategies).filter((target) => !(target in clients)).map((target) => <SelectItem key={target} value={target}>{target}</SelectItem>)}
      </SelectGroup></SelectContent>
    </Select>
  </>;
}

function LeastLoadFields({ value, pending, onChange }: { value: unknown; pending: boolean; onChange: (value: unknown) => void }) {
  const { t } = useTranslation();
  const options = (value ?? {}) as JsonObject;
  const change = (key: string, item: unknown) => {
    const next = { ...options };
    if (item === undefined) delete next[key]; else next[key] = item;
    onChange(Object.keys(next).length ? next : undefined);
  };
  return <>
    {["expected", "max_rtt_ms", "failure_tolerance"].map((key) => <Field key={key}>
      <FieldLabel htmlFor={`balancer-${key}`}>{t(`hostEditor.${key}`)}</FieldLabel>
      <Input id={`balancer-${key}`} type="number" step={key === "failure_tolerance" ? "any" : 1} disabled={pending}
        min={key === "failure_tolerance" ? 0 : 1} max={key === "failure_tolerance" ? 1 : undefined}
        placeholder={t("hostEditor.defaultValue")} value={String(options[key] ?? "")}
        onChange={(event) => change(key, event.target.value === "" ? undefined : event.target.valueAsNumber)} />
    </Field>)}
    {["baselines_ms", "costs"].map((key) => <JsonOption key={key} name={key} value={options[key]} disabled={pending} onChange={(item) => change(key, item)} />)}
  </>;
}

function JsonOption({ name, value, disabled, onChange }: { name: string; value: unknown; disabled: boolean; onChange: (value: unknown) => void }) {
  const { t } = useTranslation();
  // Keep incomplete array edits in the textarea; native validity prevents accidental submission.
  return <Field><FieldLabel htmlFor={`balancer-${name}`}>{t(`hostEditor.${name}`)}</FieldLabel>
    <Textarea id={`balancer-${name}`} dir="ltr" disabled={disabled} defaultValue={value === undefined ? "" : JSON.stringify(value, null, 2)}
      placeholder={name === "costs" ? '[{"host_id":1,"value":1}]' : "[100,200]"} onChange={(event) => {
        try {
          const next = event.target.value.trim() ? JSON.parse(event.target.value) : undefined;
          if (next !== undefined && !Array.isArray(next)) throw new Error();
          event.target.setCustomValidity(""); onChange(next);
        } catch { event.target.setCustomValidity(t("hostEditor.invalidJson")); }
      }} />
  </Field>;
}