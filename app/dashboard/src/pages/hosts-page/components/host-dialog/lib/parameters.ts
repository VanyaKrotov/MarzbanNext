import type { JsonObject } from "../../../types";
import { TLS_FINGERPRINTS } from "./constants";

export const specialHostParameters = [
  { id: "templates", labelKey: "hostEditor.templates" },
  { id: "is_hidden", labelKey: "hostEditor.isHidden" },
] as const;
export type HostParameterDefinition = {
  id: string;
  path: string[];
  labelKey: string;
  hintKey?: string;
  hintListKeys?: readonly string[];
  xhttpOnly?: boolean;
} & (
  | { kind: "text"; placeholder: string }
  | { kind: "boolean" | "json" }
  | {
      kind: "select";
      options: readonly (readonly [string, string])[];
      preserveEmptyValue?: boolean;
      preserveStoredValue?: boolean;
      emptyLabelKey?: string;
    }
);

export const hostParameters: readonly HostParameterDefinition[] = [
  {
    id: "sni",
    path: ["security", "sni"],
    labelKey: "hostsDialog.sni",
    hintKey: "hostsDialog.sni.info",
    kind: "text",
    placeholder: "www.example.com",
  },
  {
    id: "security",
    path: ["security", "mode"],
    labelKey: "hostEditor.security",
    kind: "select",
    options: [
      ["tls", "TLS"],
      ["none", "hostEditor.noSecurity"],
    ],
  },
  {
    id: "sni_from_address",
    path: ["security", "sni_from_address"],
    labelKey: "hostEditor.sniFromAddress",
    kind: "boolean",
  },
  {
    id: "alpn",
    path: ["security", "alpn"],
    labelKey: "hostsDialog.alpn",
    hintKey: "hostEditor.alpnHint",
    kind: "json",
  },
  {
    id: "fingerprint",
    path: ["security", "fingerprint"],
    labelKey: "hostsDialog.fingerprint",
    hintKey: "hostsDialog.fingerprint.info",
    hintListKeys: [
      "hostsDialog.fingerprint.info.profiles",
      "hostsDialog.fingerprint.info.random",
      "hostsDialog.fingerprint.info.randomized",
      "hostsDialog.fingerprint.info.randomizednoalpn",
      "hostsDialog.fingerprint.info.unsafe",
      "hostsDialog.fingerprint.info.default",
    ],
    kind: "select",
    options: TLS_FINGERPRINTS.map((value) => [value, value] as const),
    preserveEmptyValue: true,
    preserveStoredValue: true,
    emptyLabelKey: "hostEditor.clientDefault",
  },
  {
    id: "allow_insecure",
    path: ["security", "allow_insecure"],
    labelKey: "hostsDialog.allowinsecure",
    kind: "boolean",
  },
  {
    id: "host",
    path: ["transport", "host"],
    labelKey: "hostsDialog.host",
    hintKey: "hostsDialog.host.info",
    kind: "text",
    placeholder: "cdn.example.com",
  },
  {
    id: "path",
    path: ["transport", "path"],
    labelKey: "hostsDialog.path",
    hintKey: "hostsDialog.path.info",
    kind: "text",
    placeholder: "/proxy",
  },
  {
    id: "use_sni_as_host",
    path: ["transport", "use_sni_as_host"],
    labelKey: "hostsDialog.useSniAsHost",
    kind: "boolean",
  },
  {
    id: "random_user_agent",
    path: ["transport", "random_user_agent"],
    labelKey: "hostsDialog.randomUserAgent",
    kind: "boolean",
  },
  {
    id: "xhttp_extra",
    path: ["transport", "xhttp", "extra"],
    labelKey: "hostEditor.xhttpExtra",
    hintKey: "hostEditor.extraHint",
    kind: "json",
    xhttpOnly: true,
  },
  {
    id: "mux",
    path: ["mux"],
    labelKey: "hostEditor.muxOptions",
    kind: "json",
    hintKey: "hostEditor.muxHint",
  },
  {
    id: "fragment",
    path: ["fragment"],
    labelKey: "hostsDialog.fragment",
    hintKey: "hostsDialog.fragment.info",
    kind: "text",
    placeholder: "100-200,10-20,tlshello",
  },
  {
    id: "noise",
    path: ["noise"],
    labelKey: "hostsDialog.noise",
    kind: "text",
    hintKey: "hostsDialog.noise.info",
    placeholder: "rand:10-20,10-20",
  },
  {
    id: "sockopt",
    path: ["stream", "sockopt"],
    labelKey: "hostEditor.sockopt",
    hintKey: "hostEditor.sockoptHint",
    kind: "json",
  },
  {
    id: "final_mask",
    path: ["stream", "final_mask"],
    labelKey: "hostEditor.finalMask",
    hintKey: "hostEditor.finalMaskHint",
    kind: "json",
  },
  {
    id: "clients",
    path: ["clients"],
    labelKey: "hostEditor.clientOptions",
    hintKey: "hostEditor.clientOptionsHint",
    kind: "json",
  },
  {
    id: "mapper",
    path: ["mapper"],
    labelKey: "hostEditor.mapper",
    hintKey: "hostEditor.mapperHint",
    kind: "json",
  },
];

export function getParameterSelectOptions(
  definition: Extract<HostParameterDefinition, { kind: "select" }>,
  value: string,
) {
  // Keep a saved version-specific fingerprint selectable even when absent from the preset list.
  return definition.preserveStoredValue &&
    value &&
    !definition.options.some(([option]) => option === value)
    ? [...definition.options, [value, value] as const]
    : definition.options;
}

const parameterGroups = [
  {
    id: "security",
    ids: [
      "security",
      "sni",
      "sni_from_address",
      "alpn",
      "fingerprint",
      "allow_insecure",
    ],
  },
  {
    id: "transport",
    ids: [
      "host",
      "path",
      "use_sni_as_host",
      "random_user_agent",
      "xhttp_extra",
    ],
  },
  {
    id: "connection",
    ids: ["mux", "fragment", "noise", "sockopt", "final_mask"],
  },
  {
    id: "subscription",
    ids: ["templates", "clients", "mapper"],
  },
  { id: "visibility", ids: ["is_hidden"] },
] as const;

export function getAvailableParameterGroups(
  selected: readonly string[],
  supportsXhttp: boolean,
) {
  const options = [
    ...hostParameters.filter((item) => !item.xhttpOnly || supportsXhttp),
    ...specialHostParameters,
  ].filter((item) => !selected.includes(item.id));
  return parameterGroups
    .map((group) => ({
      id: group.id,
      options: options.filter((item) =>
        (group.ids as readonly string[]).includes(item.id),
      ),
    }))
    .filter((group) => group.options.length > 0);
}

export function getPath(object: JsonObject, path: readonly string[]): unknown {
  let value: unknown = object;
  for (const key of path) {
    if (value === null || typeof value !== "object" || Array.isArray(value))
      return undefined;
    value = (value as JsonObject)[key];
  }
  return value;
}

export function setPath(
  object: JsonObject,
  path: readonly string[],
  value: unknown,
) {
  let parent = object;
  for (const key of path.slice(0, -1)) {
    parent[key] ??= {};
    parent = parent[key] as JsonObject;
  }
  parent[path[path.length - 1]] = value;
}

export function overridePatch(
  before: JsonObject,
  after: JsonObject,
  path: string[] = [],
): JsonObject {
  const patch: JsonObject = {};
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
    if (!(key in after)) patch[key] = null;
    else if (JSON.stringify(before[key]) !== JSON.stringify(after[key])) {
      const currentPath = [...path, key];
      const atomic = currentPath.join(".") === "transport.xhttp.extra";
      const value = after[key];
      patch[key] =
        !atomic &&
        value !== null &&
        typeof value === "object" &&
        !Array.isArray(value)
          ? overridePatch(
              (before[key] ?? {}) as JsonObject,
              value as JsonObject,
              currentPath,
            )
          : value;
    }
  }
  return patch;
}
