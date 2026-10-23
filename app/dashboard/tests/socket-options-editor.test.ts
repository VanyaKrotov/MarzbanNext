import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { getLanguageService } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageService.js";
import { TextDocument } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageTypes.js";
import { jsonParameterSchema } from "../src/pages/hosts-page/components/host-dialog/lib/json-parameters";

// Python tests keep this fixture synchronized with the capabilities response.
const { $defs, ...socketOptions } = JSON.parse(
  readFileSync(
    new URL("./fixtures/socket-options-schema.json", import.meta.url),
    "utf8",
  ),
);
const schema = jsonParameterSchema(["stream", "sockopt"], {
  $defs,
  properties: { stream: { properties: { sockopt: socketOptions } } },
});
const uri = "inmemory://socket-options.json";
const service = getLanguageService({});
service.configure({
  validate: true,
  schemas: [
    { uri: "inmemory://socket-options.schema.json", fileMatch: [uri], schema },
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
  ).filter((diagnostic) => diagnostic.severity === 1);
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

test("socket Monaco schema accepts signed values, both Fast Open types, aliases and custom options", async () => {
  const valid = [
    {},
    { tcpFastOpen: false },
    { tcpFastOpen: true },
    { tcpFastOpen: 0 },
    { tcpFastOpen: 256 },
    { tcpFastOpen: -1 },
    { mark: -2147483648, tcpKeepAliveIdle: -1, tcpKeepAliveInterval: 0 },
    {
      tcpMaxSeg: 1440,
      tcpWindowClamp: 600,
      tcpUserTimeout: 10000,
      tcpMptcp: false,
    },
    {
      tcpCongestion: "cubic",
      tcpcongestion: "bbr",
      V6Only: true,
      v6only: false,
    },
    {
      acceptProxyProtocol: false,
      trustedXForwardedFor: [],
      penetrate: false,
      interface: "",
      dialerProxy: "",
    },
    {
      domainStrategy: "useip",
      addressPortStrategy: "SRVPORTONLY",
      tproxy: "TPROXY",
    },
    {
      domainStrategy: "UseIP",
      happyEyeballs: {
        tryDelayMs: 250,
        prioritizeIPv6: false,
        interleave: 1,
        maxConcurrentTry: 4,
      },
    },
    { happyEyeballs: { interleave: 0, maxConcurrentTry: 0 } },
    {
      customSockopt: [
        {
          type: "int",
          opt: "1",
          value: "-1",
          level: "",
          system: "windows",
          network: "tcp4",
        },
      ],
    },
    {
      customSockopt: [
        {
          type: "str",
          opt: "13",
          value: "bbr",
          level: "6",
          system: "linux",
          network: "tcp",
        },
      ],
    },
    { customSockopt: [{ type: "str", opt: "13", value: "" }] },
    { customSockopt: [] },
  ];
  for (const value of valid)
    assert.deepEqual(await errors(value), [], JSON.stringify(value));
});

test("socket Monaco schema rejects malformed values, unknown fields and contradictory KeepAlive signs", async () => {
  const invalid = [
    { unknown: true },
    { tcpFastOpen: "true" },
    { tcpFastOpen: 1.5 },
    { tcpFastOpen: 2147483648 },
    { mark: true },
    { mark: 2147483648 },
    { tcpMptcp: 1 },
    { tcpKeepAliveIdle: -2147483649 },
    { domainStrategy: "IPv4" },
    { addressPortStrategy: "SRV" },
    { tproxy: "enabled" },
    { tcpKeepAliveIdle: -1, tcpKeepAliveInterval: 1 },
    { tcpKeepAliveIdle: 45, tcpKeepAliveInterval: -1 },
    { happyEyeballs: { unknown: 1 } },
    { happyEyeballs: { tryDelayMs: -1 } },
    { happyEyeballs: { interleave: 4294967296 } },
    { happyEyeballs: { maxConcurrentTry: true } },
    { customSockopt: [{}] },
    { customSockopt: [{ type: "int", value: "1" }] },
    { customSockopt: [{ type: "str", opt: "13" }] },
    { customSockopt: [{ type: "bool", opt: "1", value: "1" }] },
    { customSockopt: [{ type: "int", opt: 1, value: "1" }] },
    { customSockopt: [{ type: "int", opt: "0x1", value: "1" }] },
    { customSockopt: [{ type: "int", opt: "1", value: 1 }] },
    { customSockopt: [{ type: "int", opt: "1", value: "bbr" }] },
    { customSockopt: [{ type: "int", opt: "1", value: "1.5" }] },
    {
      customSockopt: [
        { type: "str", opt: "13", value: "bbr", system: "windows" },
      ],
    },
    { customSockopt: [{ type: "int", opt: "1", value: "1", network: "http" }] },
    { customSockopt: [{ type: "int", opt: "1", value: "1", extra: true }] },
  ];
  for (const value of invalid)
    assert.ok((await errors(value)).length, JSON.stringify(value));
});

test("socket Monaco completes all fields, DNS strategies and nested option parameters", async () => {
  const root = (await completions("{ }", 2)).map((item) => item.label);
  for (const name of Object.keys(socketOptions.properties))
    assert.ok(root.includes(name), name);

  const strategy = '{"domainStrategy": }';
  const strategies = (
    await completions(strategy, strategy.indexOf(":") + 2)
  ).map((item) => item.label);
  for (const name of [
    "AsIs",
    "UseIP",
    "UseIPv4v6",
    "UseIPv6v4",
    "ForceIP",
    "ForceIPv6",
  ])
    assert.ok(strategies.includes(`"${name}"`), name);

  const happy = '{"happyEyeballs":{ }}';
  const happyFields = (await completions(happy, happy.indexOf("{ }") + 2)).map(
    (item) => item.label,
  );
  for (const name of [
    "tryDelayMs",
    "prioritizeIPv6",
    "interleave",
    "maxConcurrentTry",
  ])
    assert.ok(happyFields.includes(name), name);

  const custom = '{"customSockopt":[{"type":"int", }]}';
  const customFields = (await completions(custom, custom.indexOf(",") + 2)).map(
    (item) => item.label,
  );
  for (const name of ["system", "network", "level", "opt", "value"])
    assert.ok(customFields.includes(name), name);

  const type = '{"customSockopt":[{"type": }]}';
  const types = (await completions(type, type.indexOf(":", 17) + 2)).map(
    (item) => item.label,
  );
  for (const name of ["int", "str"])
    assert.ok(types.includes(`"${name}"`), name);
});

test("socket Monaco hover explains units and root completion offers configuration examples", async () => {
  for (const [field, explanation] of [
    ["tcpKeepAliveIdle", /seconds/],
    ["tcpUserTimeout", /milliseconds/],
    ["penetrate", /downloadSettings/],
    ["dialerProxy", /fragment.*noise/],
  ]) {
    const text = `{"${field}":null}`;
    const source = document(text);
    const hover = await service.doHover(
      source,
      source.positionAt(3),
      service.parseJSONDocument(source),
    );
    assert.match(JSON.stringify(hover?.contents), explanation);
  }
  const labels = (await completions("", 0)).map((item) => item.label);
  for (const label of [
    "TCP: Fast Open and KeepAlive",
    "DNS: Happy Eyeballs",
    "Linux: custom TCP congestion option",
  ])
    assert.ok(labels.includes(label), label);
});
