import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";

export const noDirectives: MonacoJsonSchema = {
  not: { required: ["marzban"] },
};

export function stringList(description: string): MonacoJsonSchema {
  return { type: "array", description, items: { type: "string" } };
}

export const portSchema: MonacoJsonSchema = {
  type: "integer",
  minimum: 1,
  maximum: 65535,
  description: "TCP or UDP port, from 1 to 65535.",
};

export const endpointProperties: Record<string, MonacoJsonSchema> = {
  server: {
    type: "string",
    description: "Remote server hostname or IP address.",
  },
  password: {
    type: "string",
    description:
      "Connection password. Generated host credentials are filled by MarzbanNext.",
  },
};
