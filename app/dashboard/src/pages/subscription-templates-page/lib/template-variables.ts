import type { TemplateVariable } from "@/components/monaco-template-support";
import type { SubscriptionFormat } from "./formats";

const common: TemplateVariable[] = [
  {
    label: "now()",
    description: "Current time. Available in every subscription template.",
  },
  {
    label: "tojson",
    description:
      "Serialize a value as JSON. Use for strings and objects to preserve escaping.",
  },
];
const host: TemplateVariable[] = [
  {
    label: "host",
    description:
      "Resolved host connection with id, remark, address, port, inbound and settings.",
  },
  { label: "host.id", description: "Numeric ID of the current host." },
  { label: "host.remark", description: "Resolved connection name." },
  { label: "host.address", description: "Resolved server address." },
  {
    label: "host.port",
    description: "Explicit host port or the inherited inbound port.",
  },
  {
    label: "host.inbound",
    description: "Normalized inbound settings of this connection.",
  },
  {
    label: "host.settings",
    description: "User account credentials for this connection's protocol.",
  },
];
const sources: TemplateVariable = {
  label: "host_ids",
  description:
    "IDs of all authorized sources of this format, including hidden hosts, before recipient filtering.",
};

export const templateVariables: Record<
  SubscriptionFormat,
  readonly TemplateVariable[]
> = {
  v2ray: [
    ...host,
    ...common,
    {
      label: "links",
      description:
        "Generated client URI list. Render with links | join('\\n'); one URI per line. JSON Schema does not apply to URI text.",
    },
    {
      label: "join",
      description:
        "Join a list with a separator, for example links | join('\\n').",
    },
  ],
  "v2ray-json": [
    ...host,
    ...common,
    sources,
    {
      label: "remarks",
      description: "Resolved name of the recipient's Xray profile.",
    },
  ],
  clash: [
    ...common,
    sources,
    {
      label: "conf",
      description:
        "Generated Clash configuration containing visible proxies. Render with conf | yaml.",
    },
    {
      label: "conf.proxies",
      description:
        "Visible generated host connections. Explicitly selected hidden sources are added by composition.",
    },
    {
      label: "proxy_remarks",
      description: "Names of visible generated connections.",
    },
    { label: "yaml", description: "Serialize a value as YAML." },
  ],
  "sing-box": [...common, sources],
  outline: [
    ...common,
    {
      label: "config",
      description:
        "Generated Outline Shadowsocks object with server, server_port, method, password and tag. Render with config | tojson.",
    },
  ],
};
