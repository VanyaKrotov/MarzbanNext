import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";
import type { JsonObject } from "../../../types";

export type HostOverridesSchema = MonacoJsonSchema & {
  $defs?: Record<string, MonacoJsonSchema>;
};

export function parseJsonObject(text: string): JsonObject {
  const value: unknown = JSON.parse(text);
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Expected a JSON object");
  }
  return value as JsonObject;
}

function resolveSchema(
  schema: MonacoJsonSchema | boolean,
  root: HostOverridesSchema,
): MonacoJsonSchema {
  if (typeof schema === "boolean") return schema ? {} : { not: {} };
  if (schema.$ref?.startsWith("#/$defs/")) {
    return resolveSchema(root.$defs?.[schema.$ref.slice(8)] ?? {}, root);
  }
  const alternative = schema.anyOf?.find(
    (item) => typeof item === "object" && item.type !== "null",
  );
  return alternative ? resolveSchema(alternative, root) : schema;
}

export function jsonParameterSchema(
  path: readonly string[],
  root?: HostOverridesSchema,
): MonacoJsonSchema {
  let schema: MonacoJsonSchema | boolean = root ?? {};
  for (const key of path) {
    schema = resolveSchema(schema, root ?? {}).properties?.[key] ?? {};
  }
  // Pydantic references are rooted in the full overrides document, even for a single field.
  return JSON.parse(
    JSON.stringify(
      {
        $schema: "http://json-schema.org/draft-07/schema#",
        type: "object",
        allOf: [schema],
        definitions: root?.$defs,
      },
      (key, value) =>
        key === "$ref" && typeof value === "string"
          ? value.replace(/^#\/\$defs\//, "#/definitions/")
          : value,
    ),
  );
}
