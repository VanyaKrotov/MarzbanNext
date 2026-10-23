import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";
import { clashTemplateSchema } from "./schemas/clash";
import { outlineTemplateSchema } from "./schemas/outline";
import { singboxTemplateSchema } from "./schemas/sing-box";
import { xrayTemplateSchema } from "./schemas/xray";
import type { SubscriptionFormat } from "./formats";

type DirectiveSchema = MonacoJsonSchema & {
  $defs?: Record<string, MonacoJsonSchema>;
};

export function supportsComposition(format: SubscriptionFormat): boolean {
  return format === "v2ray-json" || format === "sing-box" || format === "clash";
}

const schemaBuilders = {
  "v2ray-json": xrayTemplateSchema,
  "sing-box": singboxTemplateSchema,
  clash: clashTemplateSchema,
};

export function subscriptionTemplateSchema(
  format: SubscriptionFormat,
  capabilities?: DirectiveSchema,
): MonacoJsonSchema | undefined {
  if (format === "v2ray") return;
  if (format === "outline") return outlineTemplateSchema;
  const { $defs: definitions, ...directive } = capabilities ?? {
    type: "object",
  };
  const document = schemaBuilders[format](directive);
  // Hoist shared Pydantic definitions so nested directives resolve references at the document root.
  return JSON.parse(
    JSON.stringify(
      {
        $schema: "http://json-schema.org/draft-07/schema#",
        ...document,
        definitions,
      },
      (key, value) =>
        key === "$ref" && typeof value === "string"
          ? value.replace(/^#\/\$defs\//, "#/definitions/")
          : value,
    ),
  );
}

export function templateLanguage(
  format: SubscriptionFormat,
  content: string,
): "json" | "yaml" | "text" {
  if (format === "v2ray") return "text";
  if (format === "clash" && !/^\{\s*(?:"|}|$)/.test(content.trimStart()))
    return "yaml";
  return "json";
}
