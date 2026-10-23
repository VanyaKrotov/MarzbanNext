import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";
import { xrayCoreSchema } from "@/lib/xray-schemas/core";
import { noDirectives, stringList } from "./shared";

const leastLoadSettings: MonacoJsonSchema = {
  type: "object",
  description:
    "Native leastLoad strategy settings. Other strategies do not use this object.",
  properties: {
    expected: {
      type: "integer",
      minimum: 0,
      description:
        "Number of preferred outbounds between which traffic is distributed.",
    },
    maxRTT: {
      type: "string",
      examples: ["1s"],
      description: "Maximum acceptable round-trip time as an Xray duration.",
    },
    tolerance: {
      type: "number",
      minimum: 0,
      maximum: 1,
      description:
        "Acceptable probe failure ratio, for example 0.01 for one percent.",
    },
    baselines: stringList(
      "Round-trip time baselines, expressed as Xray durations.",
    ),
    costs: {
      type: "array",
      description: "Relative costs for outbound tags or regular expressions.",
      items: {
        type: "object",
        required: ["match", "value"],
        properties: {
          match: {
            type: "string",
            description: "Outbound tag or regular expression to match.",
          },
          regexp: {
            type: "boolean",
            default: false,
            description: "Interpret match as a regular expression.",
          },
          value: {
            type: "number",
            description: "Relative cost assigned to matching outbounds.",
          },
        },
      },
    },
  },
};

export function xrayTemplateSchema(
  directive: MonacoJsonSchema,
): MonacoJsonSchema {
  const properties = xrayCoreSchema.properties!;
  const routing = properties.routing as MonacoJsonSchema;
  const rules = routing.properties!.rules as MonacoJsonSchema;
  const rule = rules.items as MonacoJsonSchema;
  const balancers = routing.properties!.balancers as MonacoJsonSchema;
  const balancer = balancers.items as MonacoJsonSchema;
  const strategy = balancer.properties!.strategy as MonacoJsonSchema;
  const inbounds = properties.inbounds as MonacoJsonSchema;
  const outbounds = properties.outbounds as MonacoJsonSchema;
  return {
    ...xrayCoreSchema,
    title: "Xray subscription template",
    description:
      "Complete Xray client configuration. Host outbounds are generated before static outbounds; marzban metadata is removed.",
    required: ["outbounds"],
    properties: {
      ...properties,
      remarks: {
        type: "string",
        description:
          "Profile name. Replaced with the recipient host remark during generation.",
      },
      meta: {
        type: "object",
        description: "Client profile metadata.",
        additionalProperties: true,
        properties: {
          serverDescription: {
            type: "string",
            description:
              "Profile description. Filled from the recipient host for compatible extended clients.",
            examples: ["Europe"],
          },
        },
      },
      marzban: {
        ...directive,
        description:
          "Generate outbounds from authorized hosts. The recipient is excluded from injectHosts. Each injection must select at least one source.",
        defaultSnippets: [
          {
            label: "marzban",
            body: { addVirtualHostAsOutbound: true, injectHosts: [] },
          },
        ],
      },
      routing: {
        ...routing,
        properties: {
          ...routing.properties,
          // Client rules do not require the managed ruleTag used by server entities.
          rules: { ...rules, items: { ...rule, required: ["type"] } },
          balancers: {
            ...balancers,
            items: {
              ...balancer,
              properties: {
                ...balancer.properties,
                strategy: {
                  ...strategy,
                  properties: {
                    ...strategy.properties,
                    settings: leastLoadSettings,
                  },
                },
              },
            },
          },
        },
      },
      inbounds: {
        ...inbounds,
        description:
          "Local client listeners. These are not managed server inbounds.",
        items: {
          ...(inbounds.items as MonacoJsonSchema),
          ...noDirectives,
          required: ["protocol"],
        },
      },
      outbounds: {
        ...outbounds,
        description:
          "Static outbounds, appended after generated host outbounds. Use [] to generate only host connections.",
        items: {
          ...(outbounds.items as MonacoJsonSchema),
          ...noDirectives,
          required: ["protocol"],
        },
      },
    },
  };
}
