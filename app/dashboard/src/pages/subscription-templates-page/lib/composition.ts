import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";
import { xrayCoreSchema } from "@/lib/xray-schemas/core";
import type { SubscriptionFormat } from "./formats";

type DirectiveSchema = MonacoJsonSchema & {
  $defs?: Record<string, MonacoJsonSchema>;
};

const noDirectives: MonacoJsonSchema = {
  not: { required: ["marzban"] },
};
const stringList: MonacoJsonSchema = { type: "array", items: { type: "string" } };

function xrayTemplateSchema(directive: MonacoJsonSchema): MonacoJsonSchema {
  const properties = xrayCoreSchema.properties!;
  const routing = properties.routing as MonacoJsonSchema;
  const rules = routing.properties!.rules as MonacoJsonSchema;
  const rule = rules.items as MonacoJsonSchema;
  const inboundList = properties.inbounds as MonacoJsonSchema;
  const inbound = inboundList.items as MonacoJsonSchema;
  const outboundList = properties.outbounds as MonacoJsonSchema;
  const outbound = outboundList.items as MonacoJsonSchema;
  return {
    ...xrayCoreSchema,
    title: "Xray subscription template",
    description: "Client configuration with native routing and marzban source injection.",
    properties: {
      ...properties,
      remarks: { type: "string" },
      marzban: {
        ...directive,
        defaultSnippets: [{
          label: "marzban",
          body: { addVirtualHostAsOutbound: true, injectHosts: [] },
        }],
      },
      routing: {
        ...routing,
        properties: {
          ...routing.properties,
          // Client rules do not require the managed ruleTag used by server entities.
          rules: { ...rules, items: { ...rule, required: ["type"] } },
        },
      },
      inbounds: {
        ...inboundList,
        description: "Client listeners.",
        items: { ...inbound, ...noDirectives },
      },
      outbounds: {
        ...outboundList,
        items: { ...outbound, ...noDirectives, required: ["protocol"] },
      },
    },
  };
}

function singboxTemplateSchema(directive: MonacoJsonSchema): MonacoJsonSchema {
  return {
    type: "object",
    ...noDirectives,
    properties: {
      log: { type: "object" },
      dns: { type: "object" },
      inbounds: { type: "array", items: { type: "object", ...noDirectives } },
      route: { type: "object", properties: { final: { type: "string" }, rules: { type: "array" } } },
      outbounds: {
        type: "array",
        items: {
          type: "object",
          properties: {
            type: { type: "string", examples: ["selector", "urltest", "direct", "block"] },
            tag: { type: "string", minLength: 1 },
            outbounds: stringList,
            default: { type: "string" },
            url: { type: "string" },
            interval: { type: "string", examples: ["300s"] },
            tolerance: { type: "integer", minimum: 0 },
            idle_timeout: { type: "string" },
            interrupt_exist_connections: { type: "boolean" },
            marzban: {
              ...directive,
              defaultSnippets: [{
                label: "marzban",
                body: { includeProxies: true, selectFrom: "VISIBLE" },
              }],
            },
          },
          if: { required: ["marzban"] },
          then: { required: ["type"], properties: { type: { enum: ["selector", "urltest"] } } },
        },
      },
    },
  };
}

function clashTemplateSchema(directive: MonacoJsonSchema): MonacoJsonSchema {
  return {
    type: "object",
    ...noDirectives,
    properties: {
      proxies: { type: "array", items: { type: "object", ...noDirectives } },
      "proxy-groups": {
        type: "array",
        items: {
          type: "object",
          properties: {
            name: { type: "string" },
            type: { type: "string", examples: ["select", "url-test", "load-balance", "fallback"] },
            proxies: stringList,
            use: stringList,
            url: { type: "string" },
            interval: { type: "integer", minimum: 0 },
            tolerance: { type: "integer", minimum: 0 },
            lazy: { type: "boolean" },
            strategy: { type: "string", examples: ["round-robin", "consistent-hashing"] },
            marzban: directive,
          },
        },
      },
      "proxy-providers": {
        type: "object",
        additionalProperties: {
          type: "object",
          properties: {
            type: { type: "string", examples: ["inline", "http", "file"] },
            payload: { type: "array", items: { type: "object", ...noDirectives } },
            marzban: directive,
          },
          if: { required: ["marzban"] },
          then: { required: ["type"], properties: { type: { const: "inline" } } },
        },
      },
      rules: stringList,
    },
  };
}

const schemaBuilders = {
  "v2ray-json": xrayTemplateSchema,
  "sing-box": singboxTemplateSchema,
  clash: clashTemplateSchema,
};

export function compositionSchema(
  format: SubscriptionFormat,
  capabilities?: DirectiveSchema,
): MonacoJsonSchema | undefined {
  if (format !== "v2ray-json" && format !== "sing-box" && format !== "clash") return;
  const { $defs: definitions, ...directive } = capabilities ?? { type: "object" };
  const document = schemaBuilders[format](directive);
  // Hoist shared Pydantic definitions so nested directives resolve references at the document root.
  return JSON.parse(JSON.stringify({
    $schema: "http://json-schema.org/draft-07/schema#",
    ...document,
    definitions,
  }, (key, value) => key === "$ref" && typeof value === "string"
    ? value.replace(/^#\/\$defs\//, "#/definitions/") : value));
}

export function templateLanguage(format: SubscriptionFormat, content: string): "json" | "yaml" | "text" {
  if (format === "v2ray") return "text";
  if (format === "clash" && !/^\{\s*(?:"|}|$)/.test(content.trimStart())) return "yaml";
  return "json";
}
