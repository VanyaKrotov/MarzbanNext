import type { JsonObject } from "../../../types";

type ParameterKind = "text" | "boolean" | "json" | "security";
export const specialHostParameters = [
  { id: "templates", labelKey: "subscriptionTemplates.title" },
  { id: "is_hidden", labelKey: "hostEditor.isHidden" },
] as const;
export type HostParameterDefinition = {
  id: string;
  path: string[];
  labelKey: string;
  kind: ParameterKind;
  xhttpOnly?: boolean;
};

export const hostParameters: readonly HostParameterDefinition[] = [
  {
    id: "sni",
    path: ["security", "sni"],
    labelKey: "hostsDialog.sni",
    kind: "text",
  },
  {
    id: "security",
    path: ["security", "mode"],
    labelKey: "hostEditor.security",
    kind: "security",
  },
  {
    id: "keep_sni_blank",
    path: ["security", "keep_sni_blank"],
    labelKey: "hostEditor.keepSniBlank",
    kind: "boolean",
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
    kind: "json",
  },
  {
    id: "fingerprint",
    path: ["security", "fingerprint"],
    labelKey: "hostsDialog.fingerprint",
    kind: "text",
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
    kind: "text",
  },
  {
    id: "path",
    path: ["transport", "path"],
    labelKey: "hostsDialog.path",
    kind: "text",
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
    kind: "json",
    xhttpOnly: true,
  },
  { id: "mux", path: ["mux"], labelKey: "hostEditor.muxOptions", kind: "json" },
  {
    id: "fragment",
    path: ["fragment"],
    labelKey: "hostsDialog.fragment",
    kind: "text",
  },
  { id: "noise", path: ["noise"], labelKey: "hostsDialog.noise", kind: "text" },
  {
    id: "sockopt",
    path: ["stream", "sockopt"],
    labelKey: "hostEditor.sockopt",
    kind: "json",
  },
  {
    id: "final_mask",
    path: ["stream", "final_mask"],
    labelKey: "hostEditor.finalMask",
    kind: "json",
  },
  {
    id: "clients",
    path: ["clients"],
    labelKey: "hostEditor.clientOptions",
    kind: "json",
  },
  {
    id: "mapper",
    path: ["mapper"],
    labelKey: "hostEditor.mapper",
    kind: "json",
  },
];

const parameterGroups = [
  {
    id: "security",
    ids: [
      "security",
      "sni",
      "keep_sni_blank",
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
  { id: "subscription", ids: ["templates", "clients", "mapper"] },
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
