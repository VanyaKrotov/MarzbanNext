import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";
import {
  endpointProperties,
  noDirectives,
  portSchema,
  stringList,
} from "./shared";

const proxySchema: MonacoJsonSchema = {
  type: "object",
  ...noDirectives,
  description:
    "Static proxy or generated host connection. Generated proxies keep their own endpoint and credentials.",
  properties: {
    ...endpointProperties,
    name: {
      type: "string",
      description: "Unique proxy name referenced by groups and rules.",
    },
    type: {
      type: "string",
      examples: ["ss", "vmess", "vless", "trojan", "hysteria2"],
      description: "Native client proxy protocol.",
    },
    port: portSchema,
    uuid: { type: "string", description: "VMess or VLESS account UUID." },
    cipher: {
      type: "string",
      description: "Encryption cipher used by the proxy protocol.",
    },
    network: {
      type: "string",
      examples: ["tcp", "ws", "grpc", "xhttp"],
      description: "Proxy transport.",
    },
    tls: { type: "boolean", description: "Enable TLS for this proxy." },
    servername: { type: "string", description: "TLS server name (SNI)." },
    "skip-cert-verify": {
      type: "boolean",
      description: "Skip verification of the server TLS certificate.",
    },
    alpn: stringList("TLS application protocols, in preference order."),
    "ws-opts": {
      type: "object",
      description: "Native WebSocket path and headers.",
    },
    "grpc-opts": {
      type: "object",
      description: "Native gRPC transport settings.",
    },
    "xhttp-opts": {
      type: "object",
      description: "Native XHTTP transport settings.",
    },
  },
};

export function clashTemplateSchema(
  directive: MonacoJsonSchema,
): MonacoJsonSchema {
  const injection = {
    ...directive,
    description:
      "Select authorized hosts using include-proxies, selector and selectFrom. Groups append names; inline providers replace payload. Hidden hosts require ALL or HIDDEN.",
    defaultSnippets: [
      {
        label: "marzban",
        body: { "include-proxies": true, selectFrom: "VISIBLE" },
      },
    ],
  };
  return {
    type: "object",
    ...noDirectives,
    required: ["proxies"],
    title: "Clash subscription template",
    description:
      "Shared client configuration, rendered as YAML. JSON and YAML template syntax are supported.",
    properties: {
      "mixed-port": portSchema,
      "allow-lan": {
        type: "boolean",
        default: false,
        description: "Allow other devices to access the local proxy.",
      },
      mode: {
        type: "string",
        enum: ["rule", "global", "direct"],
        description: "Traffic routing mode.",
      },
      "log-level": {
        type: "string",
        enum: ["silent", "error", "warning", "info", "debug"],
        description: "Client logging level.",
      },
      dns: {
        type: "object",
        description: "Native DNS resolver configuration.",
      },
      tun: {
        type: "object",
        description: "Native TUN interface configuration.",
      },
      proxies: {
        type: "array",
        description:
          "Static proxies plus visible and explicitly used hidden host connections.",
        items: proxySchema,
      },
      "proxy-groups": {
        type: "array",
        description:
          "Manual selection, latency tests, fallback or load balancing groups.",
        items: {
          type: "object",
          required: ["name", "type"],
          properties: {
            name: {
              type: "string",
              minLength: 1,
              description:
                "Unique group name referenced by rules and other groups.",
            },
            type: {
              type: "string",
              examples: ["select", "url-test", "load-balance", "fallback"],
              description:
                "Group selection strategy. url-test selects by measured latency.",
            },
            proxies: stringList(
              "Explicit proxy or group names. Selected host names are appended without duplicates.",
            ),
            use: stringList("Names of proxy-providers used by this group."),
            url: {
              type: "string",
              description: "HTTP URL used to test connections.",
              examples: ["https://www.gstatic.com/generate_204"],
            },
            interval: {
              type: "integer",
              minimum: 0,
              description: "Health check interval in seconds.",
            },
            tolerance: {
              type: "integer",
              minimum: 0,
              description:
                "Latency difference in milliseconds tolerated before switching.",
            },
            lazy: {
              type: "boolean",
              default: true,
              description:
                "Skip health checks while the group is not selected.",
            },
            strategy: {
              type: "string",
              examples: ["round-robin", "consistent-hashing"],
              description: "Native load-balance group strategy.",
            },
            marzban: injection,
          },
        },
      },
      "proxy-providers": {
        type: "object",
        description:
          "Named proxy sources. Only inline providers support marzban injection.",
        additionalProperties: {
          type: "object",
          required: ["type"],
          properties: {
            type: {
              type: "string",
              examples: ["inline", "http", "file"],
              description:
                "Provider source. Use inline for generated host payloads.",
            },
            payload: {
              type: "array",
              description:
                "Inline proxy payload, replaced when include-proxies is true.",
              items: proxySchema,
            },
            url: {
              type: "string",
              description: "Subscription URL of an HTTP provider.",
            },
            path: {
              type: "string",
              description: "Provider cache or local file path.",
            },
            interval: {
              type: "integer",
              minimum: 0,
              description: "Provider update interval in seconds.",
            },
            marzban: injection,
          },
          if: { required: ["marzban"] },
          then: { properties: { type: { const: "inline" } } },
        },
      },
      rules: stringList(
        "Ordered routing rules. For example MATCH,Best routes all remaining traffic through Best.",
      ),
    },
  };
}
