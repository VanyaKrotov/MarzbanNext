import {
  balancerClientFormSchema,
  balancerTargets,
  balancerStrategies,
  getBalancerClientFormValues,
} from "../../../lib/balancer";
import { z } from "zod";
import {
  subscriptionFormats,
  type TemplateBindings,
} from "@/pages/subscription-templates-page/lib/formats";
import type { HostType } from "../../../types";
import { getPath, hostParameters } from "./parameters";

export const hostFormSchema = z.object({
  inbound_id: z.number().int().positive(),
  remark: z
    .string()
    .min(1)
    .max(256)
    .refine((value) => Boolean(value.trim())),
  address: z
    .string()
    .min(1)
    .max(256)
    .refine((value) => Boolean(value.trim())),
  port: z.number().int().min(1).max(65535).nullable(),
  enabled: z.boolean(),
  show_when_composed: z.boolean(),
  selected: z.array(z.string()),
  parameters: z.record(z.string()),
  original_overrides: z.record(z.unknown()),
  original_balancer: z.record(z.unknown()).nullable(),
  linked_host_ids: z.array(z.number().int().positive()),
  group_ids: z.array(z.string()),
  subscription_template_ids: z.record(
    z.enum(subscriptionFormats),
    z.number().int().positive(),
  ),
  balancer_remark: z.string(),
  balancer_strategy: z.enum(balancerStrategies),
  balancer_probe_url: z.string(),
  balancer_probe_interval: z.number().int().min(10).max(86400),
  balancer_clients: z.record(z.enum(balancerTargets), balancerClientFormSchema),
});
export type HostFormValues = z.infer<typeof hostFormSchema>;

export function getHostFormValues(
  inboundId: number,
  host?: HostType | null,
  bindings: TemplateBindings = {},
): HostFormValues {
  const parameters: Record<string, string> = {};
  const selected: string[] = [];
  for (const definition of hostParameters) {
    const value = getPath(host?.overrides ?? {}, definition.path);
    if (value === undefined) continue;
    selected.push(definition.id);
    parameters[definition.id] =
      definition.kind === "json"
        ? JSON.stringify(value, null, 2)
        : String(value);
  }
  if (host) selected.push("templates");
  if (host?.balancer_settings || host?.linked_host_ids.length)
    selected.push("composition");
  if (host?.show_when_composed === false) selected.push("show_when_composed");
  const balancer = host?.balancer_settings;
  return {
    inbound_id: host?.inbound_id ?? inboundId,
    remark: host?.remark ?? "",
    address: host?.address ?? "",
    port: host?.port ?? null,
    enabled: host?.enabled ?? true,
    show_when_composed: host?.show_when_composed ?? true,
    selected,
    parameters,
    original_overrides: host?.overrides ?? {},
    original_balancer: host?.balancer_settings ?? null,
    linked_host_ids: host?.linked_host_ids ?? [],
    group_ids: host?.groups.map((group) => group.id) ?? [],
    subscription_template_ids: host?.subscription_template_ids ?? bindings,
    balancer_remark: String(balancer?.remark ?? ""),
    balancer_strategy: balancer?.strategy ?? "least_ping",
    balancer_probe_url: String(
      balancer?.probe_url ?? "https://www.gstatic.com/generate_204",
    ),
    balancer_probe_interval: Number(balancer?.probe_interval ?? 300),
    balancer_clients: getBalancerClientFormValues(balancer?.clients ?? {}),
  };
}
