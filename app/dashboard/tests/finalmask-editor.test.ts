import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { getLanguageService } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageService.js";
import { TextDocument } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageTypes.js";
import { jsonParameterSchema } from "../src/pages/hosts-page/components/host-dialog/lib/json-parameters";

// The Python tests verify this snapshot against the model served by capabilities.
const { $defs, ...finalMask } = JSON.parse(
  readFileSync(
    new URL("./fixtures/finalmask-schema.json", import.meta.url),
    "utf8",
  ),
);
const schema = jsonParameterSchema(["stream", "final_mask"], {
  $defs,
  properties: { stream: { properties: { final_mask: finalMask } } },
});
const uri = "inmemory://final-mask.json";
const service = getLanguageService({});
service.configure({
  validate: true,
  schemas: [
    { uri: "inmemory://final-mask.schema.json", fileMatch: [uri], schema },
  ],
});

function document(text: string) {
  return TextDocument.create(uri, "json", 1, text);
}

async function errors(value: unknown) {
  const source = document(JSON.stringify(value));
  return (
    await service.doValidation(source, service.parseJSONDocument(source), {
      schemaValidation: "error",
    })
  ).filter((item) => item.severity === 1);
}

async function completions(text: string, offset: number) {
  const source = document(text);
  return (
    await service.doComplete(
      source,
      source.positionAt(offset),
      service.parseJSONDocument(source),
    )
  ).items;
}

test("Final mask Monaco accepts every supported TCP/UDP mask and legacy representations", async () => {
  const tcp = [
    { type: "filter", settings: { blockedSourceIPs: ["192.0.2.0/24"] } },
    {
      type: "header-custom",
      settings: { clients: [[{ type: "hex", packet: "0001", delay: 10 }]] },
    },
    {
      type: "fragment",
      settings: {
        packets: "tlshello",
        lengths: [0, "100-200"],
        delays: ["0-10"],
      },
    },
    {
      type: "sudoku",
      settings: { custom_table: "xpxpvvvv", padding_min: 0, padding_max: 100 },
    },
    {
      type: "xmc",
      settings: {
        password: "shared",
        profiles: [
          {
            username: "player",
            uuid: "12345678-1234-5678-1234-567812345678",
            texturesValue: "payload",
            texturesSignature: "signature",
          },
        ],
      },
    },
  ];
  const udp = [
    { type: "filter" },
    {
      type: "header-custom",
      settings: {
        mode: "prefix",
        client: [
          {
            transform: {
              op: "concat",
              args: [
                { bytes: [1] },
                { transform: { op: "be16", args: [{ u64: 0 }] } },
              ],
            },
          },
        ],
      },
    },
    {
      type: "mkcp-legacy",
      settings: { header: "dns", value: "dns.example.com" },
    },
    {
      type: "noise",
      settings: {
        noise: [{ type: "exp", packet: "<b 0001><r 8-16><t><c><n>", delay: 0 }],
      },
    },
    {
      type: "salamander",
      settings: { password: "shared", packetSize: "1024-1280" },
    },
    { type: "sudoku", settings: { ascii: "prefer_ascii" } },
    {
      type: "xdns",
      settings: {
        domains: [{ names: ["tunnel.example.com"], types: [1, 5, 16, 28] }],
        resolvers: [
          {
            addrs: ["https://dns.example.com/dns-query"],
            tlsConfig: { alpn: ["h2"] },
            quicConfig: { congestion: "bbr" },
          },
        ],
        extraPoll: 3,
      },
    },
    {
      type: "xicmp",
      settings: { dgram: false, ips: ["192.0.2.1", "2001:db8::1"] },
    },
    {
      type: "realm",
      settings: {
        url: "realm://token@signal.example.com/id",
        stunServers: ["stun.example.com:3478"],
        portMapping: { enabled: false },
      },
    },
    {
      type: "udphop",
      settings: {
        mode: "intervalremote",
        interval: "5-30",
        remotePorts: "443,20000-50000",
      },
    },
  ];
  for (const [family, masks] of Object.entries({ tcp, udp })) {
    for (const mask of masks)
      assert.deepEqual(
        await errors({ [family]: [mask] }),
        [],
        `${family}: ${mask.type}`,
      );
  }
  assert.deepEqual(
    await errors({
      tcp: [{ type: "fragment", settings: { length: "200-100", delay: "" } }],
      quicParams: {
        brutalUp: "60 mbps",
        disableGSO: false,
        udpHop: { ports: 443, interval: "5-30" },
      },
    }),
    [],
  );
});

test("Final mask Monaco rejects wrong mask families, unknown fields and malformed values", async () => {
  const invalid = [
    { tcp: [{ type: "noise" }] },
    { udp: [{ type: "fragment", settings: { length: 100 } }] },
    { tcp: [{ type: "unknown" }] },
    { tcp: [{ type: "fragment", settings: {} }] },
    { tcp: [{ type: "fragment", settings: { length: -1 } }] },
    { tcp: [{ type: "fragment", settings: { length: true } }] },
    { udp: [{ type: "salamander", settings: { unknown: true } }] },
    { udp: [{ type: "salamander", settings: { packetSize: 2049 } }] },
    { udp: [{ type: "header-custom", settings: { client: [{ delay: 1 }] } }] },
    {
      udp: [
        {
          type: "header-custom",
          settings: { client: [{ type: "hex", packet: "xyz" }] },
        },
      ],
    },
    {
      udp: [
        {
          type: "header-custom",
          settings: { client: [{ randRange: "0-256" }] },
        },
      ],
    },
    {
      udp: [
        {
          type: "header-custom",
          settings: {
            client: [
              { transform: { op: "be16", args: [{ u64: 0, bytes: [] }] } },
            ],
          },
        },
      ],
    },
    {
      udp: [
        {
          type: "header-custom",
          settings: {
            client: [
              { transform: { op: "be16", args: [{ u64: 0 }, { u64: 1 }] } },
            ],
          },
        },
      ],
    },
    {
      udp: [
        {
          type: "noise",
          settings: { script: "return {}", noise: [{ rand: 1 }] },
        },
      ],
    },
    {
      udp: [
        {
          type: "noise",
          settings: { noise: [{ type: "exp", packet: "<unknown>" }] },
        },
      ],
    },
    { udp: [{ type: "xdns", settings: { extraPoll: 4 } }] },
    { udp: [{ type: "udphop", settings: { mode: "random" } }] },
    {
      udp: [
        {
          type: "udphop",
          settings: { mode: "intervalremote", remotePorts: "65536" },
        },
      ],
    },
    { quicParams: { maxIdleTimeout: 3 } },
    { quicParams: { keepAlivePeriod: 61 } },
    { quicParams: { initStreamReceiveWindow: 16383 } },
    { quicParams: { congestion: "force-brutal" } },
    { unknown: true },
  ];
  for (const value of invalid)
    assert.ok((await errors(value)).length, JSON.stringify(value));
});

test("Final mask Monaco suggests only the selected mask settings and correct transport types", async () => {
  const root = (await completions("{ }", 2)).map((item) => item.label);
  for (const key of ["tcp", "udp", "quicParams"]) assert.ok(root.includes(key));
  for (const [family, expected, absent] of [
    ["tcp", "fragment", "noise"],
    ["udp", "noise", "fragment"],
  ]) {
    const text = `{"${family}":[{"type": }]}`;
    const labels = (await completions(text, text.lastIndexOf(":") + 2)).map(
      (item) => item.label,
    );
    assert.ok(labels.includes(`"${expected}"`));
    assert.ok(!labels.includes(`"${absent}"`));
  }
  for (const [family, type, expected, absent] of [
    ["tcp", "fragment", "lengths", "password"],
    ["udp", "salamander", "password", "lengths"],
    ["udp", "header-custom", "client", "clients"],
  ]) {
    const text = `{"${family}":[{"type":"${type}","settings":{ }}]}`;
    const labels = (await completions(text, text.indexOf("{ }") + 2)).map(
      (item) => item.label,
    );
    assert.ok(labels.includes(expected));
    assert.ok(!labels.includes(absent));
  }
});

test("Final mask Monaco explains parameters on hover and offers usable root examples", async () => {
  const text =
    '{"tcp":[{"type":"fragment","settings":{"lengths":["100-200"]}}]}';
  const source = document(text);
  const hover = await service.doHover(
    source,
    source.positionAt(text.indexOf('"lengths"') + 2),
    service.parseJSONDocument(source),
  );
  assert.match(JSON.stringify(hover?.contents), /length ranges in bytes/);
  const labels = (await completions("", 0)).map((item) => item.label);
  for (const label of [
    "TCP: TLS ClientHello fragmentation",
    "UDP: Salamander",
    "UDP: noise expressions",
  ])
    assert.ok(labels.includes(label));
});
