import { z } from "zod";
import { subscriptionFormats, type TemplateBindings } from "@/pages/subscription-templates-page/lib/query";
import type { HostType, HostPayload, JsonObject } from "../../../types";
import { getPath, hostParameters, overridePatch, setPath } from "./parameters";

export const hostFormSchema = z.object({
  inbound_id: z.number().int().positive(),
  remark: z.string().min(1).max(256).refine((value) => Boolean(value.trim())),
  address: z.string().min(1).max(256).refine((value) => Boolean(value.trim())),
  port: z.number().int().min(1).max(65535).nullable(),
  enabled: z.boolean(),
  show_when_composed: z.boolean(),
  selected: z.array(z.string()),
  parameters: z.record(z.string()),
  explicit_empty: z.array(z.string()),
  original_overrides: z.record(z.unknown()),
  original_balancer: z.record(z.unknown()).nullable(),
  linked_host_ids: z.array(z.number().int().positive()),
  group_ids: z.array(z.string()),
  subscription_template_ids: z.record(z.enum(subscriptionFormats), z.number().int().positive()),
  balancer_remark: z.string(),
  balancer_strategy: z.enum(["least_ping", "least_load", "random", "round_robin"]),
  balancer_probe_url: z.string(),
  balancer_probe_interval: z.number().int().min(10).max(86400),
  balancer_clients: z.record(z.string()),
});
export type HostFormValues = z.infer<typeof hostFormSchema>;

export function getHostFormValues(inboundId: number, host?: HostType | null, bindings: TemplateBindings = {}): HostFormValues {
  const parameters: Record<string, string> = {};
  const selected: string[] = [];
  const explicitEmpty: string[] = [];
  for (const definition of hostParameters) {
    const value = getPath(host?.overrides ?? {}, definition.path);
    if (value === undefined) continue;
    selected.push(definition.id);
    parameters[definition.id] = definition.kind === "json" ? JSON.stringify(value, null, 2) : String(value);
    if (value === "") explicitEmpty.push(definition.id);
  }
  if (host?.groups.length) selected.push("groups");
  if (host) selected.push("templates");
  if (host?.balancer_settings || host?.linked_host_ids.length) selected.push("composition");
  if (host?.show_when_composed === false) selected.push("show_when_composed");
  const balancer = host?.balancer_settings ?? {};
  const clients = (balancer.clients ?? {}) as JsonObject;
  return {
    inbound_id: host?.inbound_id ?? inboundId, remark: host?.remark ?? "", address: host?.address ?? "",
    port: host?.port ?? null, enabled: host?.enabled ?? true, show_when_composed: host?.show_when_composed ?? true,
    selected, parameters, explicit_empty: explicitEmpty, original_overrides: host?.overrides ?? {},
    original_balancer: host?.balancer_settings ?? null,
    linked_host_ids: host?.linked_host_ids ?? [], group_ids: host?.groups.map((group) => group.id) ?? [],
    subscription_template_ids: host?.subscription_template_ids ?? bindings,
    balancer_remark: String(balancer.remark ?? ""),
    balancer_strategy: (balancer.strategy ?? "least_ping") as HostFormValues["balancer_strategy"],
    balancer_probe_url: String(balancer.probe_url ?? "https://www.gstatic.com/generate_204"),
    balancer_probe_interval: Number(balancer.probe_interval ?? 300),
    balancer_clients: Object.fromEntries(Object.entries(clients).map(([key, value]) => [key, JSON.stringify(value, null, 2)])),
  };
}

export class ParameterError extends Error {
  constructor(public parameter: string, message: string) { super(message); }
}

export function toHostPayload(values: HostFormValues): HostPayload {
  const overrides: JsonObject = {};
  for (const definition of hostParameters) {
    if (!values.selected.includes(definition.id)) continue;
    const text = values.parameters[definition.id] ?? "";
    if (text === "" && !values.explicit_empty.includes(definition.id)) {
      if (definition.kind === "json" && getPath(values.original_overrides, definition.path) !== undefined) {
        throw new ParameterError(definition.id, "hostEditor.invalidJson");
      }
      continue;
    }
    let value: unknown = text;
    if (definition.kind === "json") {
      try { value = JSON.parse(text); }
      catch { throw new ParameterError(definition.id, "hostEditor.invalidJson"); }
      const arrayExpected = definition.id === "alpn";
      if (value === null || typeof value !== "object" || Array.isArray(value) !== arrayExpected) {
        throw new ParameterError(definition.id, "hostEditor.invalidJson");
      }
      if (definition.id === "xhttp_extra") {
        const extra = value as JsonObject;
        if (typeof extra.uplinkHTTPMethod === "string") extra.uplinkHTTPMethod = extra.uplinkHTTPMethod.trim().toUpperCase();
      }
    } else if (definition.kind === "boolean") value = text === "true";
    setPath(overrides, definition.path, value);
  }
  let balancer: JsonObject | null = null;
  if (values.selected.includes("composition")) {
    const clients: JsonObject = {};
    for (const [target, text] of Object.entries(values.balancer_clients)) {
      if (!text.trim()) continue;
      try {
        const options: unknown = JSON.parse(text);
        if (options === null || typeof options !== "object" || Array.isArray(options)) throw new Error();
        clients[target] = options;
      } catch { throw new ParameterError(`client_${target}`, "hostEditor.invalidJson"); }
    }
    balancer = { remark: values.balancer_remark || null, strategy: values.balancer_strategy,
      probe_url: values.balancer_probe_url, probe_interval: values.balancer_probe_interval, clients };
  }
  return {
    inbound_id: values.inbound_id, remark: values.remark, address: values.address, port: values.port,
    enabled: values.enabled, show_when_composed: values.show_when_composed,
    overrides: overridePatch(values.original_overrides, overrides),
    balancer_settings: balancer === null ? null : overridePatch(values.original_balancer ?? {}, balancer),
    linked_host_ids: balancer === null ? [] : values.linked_host_ids,
    group_ids: values.selected.includes("groups") ? values.group_ids : [],
    ...(values.selected.includes("templates") ? { subscription_template_ids: values.subscription_template_ids } : {}),
  };
}
