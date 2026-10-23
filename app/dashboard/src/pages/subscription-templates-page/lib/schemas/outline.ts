import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";
import { endpointProperties, noDirectives, portSchema } from "./shared";

export const outlineTemplateSchema: MonacoJsonSchema = {
  type: "object",
  ...noDirectives,
  title: "Outline subscription template",
  description:
    "Outline Shadowsocks configuration or a custom JSON wrapper. Use {{ config | tojson }} to preserve the generated connection. Composition is not supported.",
  properties: {
    ...endpointProperties,
    server_port: portSchema,
    method: {
      type: "string",
      description:
        "Shadowsocks encryption method, copied from the generated connection.",
    },
    tag: {
      type: "string",
      description: "Connection name from the selected host remark.",
    },
  },
};
