import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";
import {
  endpointProperties,
  noDirectives,
  portSchema,
  stringList,
} from "./shared";

export function singboxTemplateSchema(
  directive: MonacoJsonSchema,
): MonacoJsonSchema {
  return {
    type: "object",
    ...noDirectives,
    required: ["outbounds"],
    title: "sing-box subscription template",
    description:
      "Shared sing-box client configuration with generated host outbounds and native selection groups.",
    properties: {
      log: {
        type: "object",
        description: "Client logging configuration.",
        properties: {
          level: {
            type: "string",
            examples: [
              "trace",
              "debug",
              "info",
              "warn",
              "error",
              "fatal",
              "panic",
            ],
            description: "Minimum logging level.",
          },
        },
      },
      dns: {
        type: "object",
        description:
          "Native sing-box DNS resolver configuration. The syntax depends on the client version.",
      },
      inbounds: {
        type: "array",
        description: "Local client listeners or TUN interfaces.",
        items: {
          type: "object",
          ...noDirectives,
          required: ["type"],
          properties: {
            type: {
              type: "string",
              examples: ["mixed", "socks", "http", "tun"],
              description: "Local listener type.",
            },
            tag: {
              type: "string",
              description: "Listener tag used by routing rules.",
            },
            listen: {
              type: "string",
              description: "Local listen address, for example 127.0.0.1.",
            },
            listen_port: portSchema,
          },
        },
      },
      route: {
        type: "object",
        description: "Client routing configuration.",
        properties: {
          final: {
            type: "string",
            description:
              "Default outbound tag, for example best for an automatic latency group.",
          },
          rules: {
            type: "array",
            description: "Native routing rules, evaluated in order.",
            items: { type: "object" },
          },
          auto_detect_interface: {
            type: "boolean",
            description: "Automatically select the default network interface.",
          },
        },
      },
      outbounds: {
        type: "array",
        description:
          "Static outbounds and groups. Generated host outbounds are appended automatically.",
        items: {
          type: "object",
          required: ["type", "tag"],
          properties: {
            ...endpointProperties,
            type: {
              type: "string",
              examples: [
                "selector",
                "urltest",
                "direct",
                "shadowsocks",
                "vmess",
                "vless",
                "trojan",
                "hysteria2",
              ],
              description:
                "Native outbound protocol or group type. marzban is supported only by selector and urltest.",
            },
            tag: {
              type: "string",
              minLength: 1,
              description:
                "Unique outbound tag referenced by groups and route.final.",
            },
            server_port: portSchema,
            uuid: {
              type: "string",
              description: "VLESS or VMess account UUID.",
            },
            method: {
              type: "string",
              description: "Shadowsocks encryption method.",
            },
            tls: {
              type: "object",
              description: "Native TLS, SNI, ALPN and Reality settings.",
            },
            transport: {
              type: "object",
              description: "Native WebSocket, HTTP or gRPC transport settings.",
            },
            outbounds: {
              anyOf: [
                stringList("Outbound tags selected by this group."),
                { type: "null" },
              ],
              description:
                "With includeProxies=true, replaced by selected host tags. Without marzban, null enables legacy automatic filling; [] stays empty.",
            },
            default: {
              type: "string",
              description:
                "Initial selector choice; must be in the group's outbounds list.",
            },
            url: {
              type: "string",
              description: "URLTest probe URL.",
              examples: ["https://www.gstatic.com/generate_204"],
            },
            interval: {
              type: "string",
              examples: ["300s"],
              description:
                "URLTest check interval as a duration, for example 300s.",
            },
            tolerance: {
              type: "integer",
              minimum: 0,
              description: "Latency switching tolerance in milliseconds.",
            },
            idle_timeout: {
              type: "string",
              examples: ["30m"],
              description:
                "Duration after which URLTest pauses checks for an idle group.",
            },
            interrupt_exist_connections: {
              type: "boolean",
              default: false,
              description:
                "Interrupt existing inbound connections when the selected outbound changes.",
            },
            marzban: {
              ...directive,
              description:
                "Replace the group list with authorized host tags. Explicit selectors never bypass format or inbound permissions. Hidden hosts require ALL or HIDDEN.",
              defaultSnippets: [
                {
                  label: "marzban",
                  body: { includeProxies: true, selectFrom: "VISIBLE" },
                },
              ],
            },
          },
          if: { required: ["marzban"] },
          then: { properties: { type: { enum: ["selector", "urltest"] } } },
        },
      },
    },
  };
}
