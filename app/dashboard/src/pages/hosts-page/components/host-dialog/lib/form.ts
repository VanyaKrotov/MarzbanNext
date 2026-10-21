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
  is_hidden: z.boolean(),
  selected: z.array(z.string()),
  parameters: z.record(z.string()),
  original_overrides: z.record(z.unknown()),
  group_ids: z.array(z.string()),
  subscription_template_ids: z.record(
    z.enum(subscriptionFormats),
    z.number().int().positive(),
  ),
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
  if (host?.is_hidden) selected.push("is_hidden");
  return {
    inbound_id: host?.inbound_id ?? inboundId,
    remark: host?.remark ?? "",
    address: host?.address ?? "",
    port: host?.port ?? null,
    enabled: host?.enabled ?? true,
    is_hidden: host?.is_hidden ?? false,
    selected,
    parameters,
    original_overrides: host?.overrides ?? {},
    group_ids: host?.groups.map((group) => group.id) ?? [],
    subscription_template_ids: host?.subscription_template_ids ?? bindings,
  };
}
