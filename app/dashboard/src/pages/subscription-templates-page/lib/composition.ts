import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";
import type { SubscriptionFormat } from "./formats";

export type SourceSelection =
  { type: "ids"; values: number[] } | { type: "groups"; values: string[] };

export function compositionExample(
  format: SubscriptionFormat,
  selector: SourceSelection,
): string {
  const selection = { selector, selectFrom: "ALL" };
  if (format === "v2ray-json") {
    return JSON.stringify(
      {
        marzban: {
          addVirtualHostAsOutbound: false,
          injectHosts: [{ ...selection, tagPrefix: "pool" }],
        },
        outbounds: [],
        observatory: {
          subjectSelector: ["pool"],
          probeUrl: "https://www.gstatic.com/generate_204",
          probeInterval: "300s",
        },
        routing: {
          balancers: [
            {
              tag: "best",
              selector: ["pool"],
              strategy: { type: "leastPing" },
            },
          ],
          rules: [{ type: "field", network: "tcp,udp", balancerTag: "best" }],
        },
      },
      null,
      2,
    );
  }
  if (format === "sing-box") {
    return JSON.stringify(
      {
        outbounds: [
          { type: "selector", tag: "proxy", outbounds: ["best"] },
          {
            type: "urltest",
            tag: "best",
            outbounds: [],
            url: "https://www.gstatic.com/generate_204",
            interval: "300s",
            tolerance: 50,
            marzban: { includeProxies: true, ...selection },
          },
        ],
        route: { final: "proxy" },
      },
      null,
      2,
    );
  }
  if (format === "clash") {
    return `proxies: []\nproxy-groups:\n  - name: proxy\n    type: select\n    proxies: [best]\n    marzban:\n      include-proxies: false\n  - name: best\n    type: url-test\n    proxies: []\n    url: https://www.gstatic.com/generate_204\n    interval: 300\n    marzban:\n      include-proxies: true\n      selectFrom: ALL\n      selector:\n        type: ${selector.type}\n        values: ${JSON.stringify(selector.values)}\nrules:\n  - MATCH,proxy\n`;
  }
  throw new Error("This format does not support composition");
}

const selectorSchema: MonacoJsonSchema = {
  type: "object",
  additionalProperties: false,
  required: ["type"],
  properties: {
    type: { enum: ["ids", "groups", "sameGroupsAsRecipient"] },
    values: { type: "array", items: { type: ["integer", "string"] } },
  },
};
const selectionProperties = {
  selector: selectorSchema,
  selectFrom: { enum: ["ALL", "HIDDEN", "VISIBLE"] },
};

export function compositionSchema(
  format: SubscriptionFormat,
): MonacoJsonSchema | undefined {
  if (format === "v2ray-json")
    return {
      type: "object",
      properties: {
        marzban: {
          type: "object",
          additionalProperties: false,
          properties: {
            addVirtualHostAsOutbound: { type: "boolean", default: true },
            injectHosts: {
              type: "array",
              items: {
                type: "object",
                additionalProperties: false,
                required: ["tagPrefix"],
                properties: {
                  ...selectionProperties,
                  tagPrefix: { type: "string", minLength: 1 },
                },
              },
            },
          },
        },
        outbounds: { type: "array", items: { type: "object" } },
      },
    };
  if (format === "sing-box")
    return {
      type: "object",
      properties: {
        outbounds: {
          type: "array",
          items: {
            type: "object",
            properties: {
              marzban: {
                type: "object",
                additionalProperties: false,
                properties: {
                  ...selectionProperties,
                  selector: {
                    ...selectorSchema,
                    properties: {
                      ...selectorSchema.properties,
                      type: { enum: ["ids", "groups"] },
                    },
                  },
                  includeProxies: { type: "boolean", default: true },
                },
              },
            },
          },
        },
      },
    };
  return undefined;
}
