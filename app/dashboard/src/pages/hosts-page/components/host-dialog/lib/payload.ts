import type { HostPayload, JsonObject } from "../../../types";
import { serializeBalancerClients } from "../../../lib/balancer";
import type { HostFormValues } from "./form";
import {
  getPath,
  hostParameters,
  overridePatch,
  setPath,
  type HostParameterDefinition,
} from "./parameters";

export class ParameterError extends Error {
  constructor(
    public parameter: string,
    message: string,
  ) {
    super(message);
  }
}

function parseParameterValue(
  definition: HostParameterDefinition,
  text: string,
): unknown {
  if (definition.kind === "boolean") return text === "true";
  if (definition.kind !== "json") return text;
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new ParameterError(definition.id, "hostEditor.invalidJson");
  }
  const arrayExpected = definition.id === "alpn";
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) !== arrayExpected
  ) {
    throw new ParameterError(definition.id, "hostEditor.invalidJson");
  }
  if (definition.id === "xhttp_extra") {
    const extra = value as JsonObject;
    if (typeof extra.uplinkHTTPMethod === "string")
      extra.uplinkHTTPMethod = extra.uplinkHTTPMethod.trim().toUpperCase();
  }
  return value;
}

function buildOverrides(values: HostFormValues): JsonObject {
  const overrides: JsonObject = {};
  for (const definition of hostParameters) {
    if (!values.selected.includes(definition.id)) continue;
    const text = values.parameters[definition.id] ?? "";
    if (text === "" && !values.explicit_empty.includes(definition.id)) {
      if (
        definition.kind === "json" &&
        getPath(values.original_overrides, definition.path) !== undefined
      ) {
        throw new ParameterError(definition.id, "hostEditor.invalidJson");
      }
      continue;
    }
    const value = parseParameterValue(definition, text);
    setPath(overrides, definition.path, value);
  }
  return overrides;
}

function buildBalancer(values: HostFormValues): JsonObject | null {
  if (!values.selected.includes("composition")) return null;
  const clients = serializeBalancerClients(
    values.balancer_clients,
    values.balancer_strategy,
  );
  return {
    remark: values.balancer_remark || null,
    strategy: values.balancer_strategy,
    probe_url: values.balancer_probe_url,
    probe_interval: values.balancer_probe_interval,
    clients,
  };
}

export function toHostPayload(values: HostFormValues): HostPayload {
  const overrides = buildOverrides(values);
  const balancer = buildBalancer(values);
  return {
    inbound_id: values.inbound_id,
    remark: values.remark,
    address: values.address,
    port: values.port,
    enabled: values.enabled,
    show_when_composed: values.show_when_composed,
    overrides: overridePatch(values.original_overrides, overrides),
    balancer_settings:
      balancer === null
        ? null
        : overridePatch(values.original_balancer ?? {}, balancer),
    linked_host_ids: balancer === null ? [] : values.linked_host_ids,
    group_ids: values.selected.includes("groups") ? values.group_ids : [],
    ...(values.selected.includes("templates")
      ? { subscription_template_ids: values.subscription_template_ids }
      : {}),
  };
}
