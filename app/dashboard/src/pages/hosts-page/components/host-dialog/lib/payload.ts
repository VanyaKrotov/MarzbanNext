import type { HostPayload, JsonObject } from "../../../types";
import type { HostFormValues } from "./form";
import { parseJsonObject } from "./json-parameters";
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
    value = definition.id === "alpn" ? JSON.parse(text) : parseJsonObject(text);
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
    const preserveEmpty =
      definition.kind === "text" ||
      // An added switch overrides the default even before its first toggle.
      definition.kind === "boolean" ||
      (definition.kind === "select" && definition.preserveEmptyValue);
    if (text === "" && !preserveEmpty) {
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

export function toHostPayload(values: HostFormValues): HostPayload {
  const overrides = buildOverrides(values);
  return {
    inbound_id: values.inbound_id,
    remark: values.remark,
    address: values.address,
    port: values.port,
    enabled: values.enabled,
    is_hidden: values.is_hidden,
    overrides: overridePatch(values.original_overrides, overrides),
    group_ids: values.group_ids,
    ...(values.selected.includes("templates")
      ? { subscription_template_ids: values.subscription_template_ids }
      : {}),
  };
}
