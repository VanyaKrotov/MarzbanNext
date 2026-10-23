import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { getLanguageService } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageService.js";
import { TextDocument } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageTypes.js";
import { jsonParameterSchema } from "../src/pages/hosts-page/components/host-dialog/lib/json-parameters";

const native = JSON.parse(
  readFileSync(
    new URL("./fixtures/xhttp-schema.json", import.meta.url),
    "utf8",
  ),
);
const schema = jsonParameterSchema(["transport", "xhttp", "extra"], {
  $defs: native.$defs,
  properties: {
    transport: {
      properties: {
        xhttp: { properties: { extra: { $ref: "#/$defs/XhttpExtra" } } },
      },
    },
  },
});
const uri = "inmemory://xhttp.json";
const service = getLanguageService({});
service.configure({
  validate: true,
  schemas: [{ uri: "inmemory://xhttp.schema.json", fileMatch: [uri], schema }],
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

test("XHTTP Monaco accepts all range representations and separate downstream settings", async () => {
  const valid = [
    {},
    { uplinkHTTPMethod: "PUT", xPaddingObfsMode: false, scMaxBufferedPosts: 0 },
    {
      xmux: { maxConnections: "4-2", maxConcurrency: 0, hKeepAlivePeriod: -1 },
    },
    {
      sessionIDTable: "Base62",
      sessionIDLength: "16-24",
      seqPlacement: "header",
      uplinkChunkSize: "4000-3000",
    },
    { scMaxConcurrentPosts: 100 },
    {
      downloadSettings: {
        address: "download.example.com",
        port: 443,
        network: "xhttp",
        security: "tls",
        tlsSettings: { serverName: "download.example.com", alpn: ["h2"] },
        sockopt: { tcpFastOpen: false },
        xhttpSettings: {
          path: "/down",
          mode: "packet-up",
          extra: { uplinkHTTPMethod: "GET" },
        },
      },
    },
  ];
  valid.push({
    downloadSettings: {
      address: "download.example.com",
      port: 443,
      network: "xhttp",
      xhttpSettings: {
        mode: "stream-one",
        uplinkHTTPMethod: "GET",
        sessionIDTable: "Base62",
        extra: {},
      },
    },
  });
  for (const value of valid)
    assert.deepEqual(await errors(value), [], JSON.stringify(value));
  for (const value of [
    0,
    -1,
    "",
    "0",
    "4-2",
    "-2--1",
    "+1--2",
    -2147483648,
    2147483647,
  ]) {
    assert.deepEqual(
      await errors({ xmux: { maxConnections: value } }),
      [],
      String(value),
    );
  }
});

test("XHTTP Monaco rejects unknown keys, nulls, malformed ranges, incompatible reuse and headers", async () => {
  const invalid = [
    { unknown: 1 },
    { mode: "packet-up" },
    { uplinkHTTPMethod: "GET /" },
    { xPaddingMethod: "invalid" },
    { xPaddingPlacement: "path" },
    { xPaddingBytes: "0-10" },
    { xPaddingBytes: -1 },
    { headers: { Host: "example.com" } },
    { headers: { "X-Test": "a\nb" } },
    { noGRPCHeader: null },
    { headers: null },
    { xmux: { maxConnections: null } },
    { xmux: { maxConnections: "2-4", maxConcurrency: "4-0" } },
    { sessionIDTable: "Base62" },
    { sessionIDTable: "hex", sessionIDLength: 0 },
    { serverMaxHeaderBytes: -1 },
    { scMaxBufferedPosts: -1 },
    { sessionIDTable: "ä", sessionIDLength: 16 },
  ];
  for (const value of invalid)
    assert.ok((await errors(value)).length, JSON.stringify(value));
  for (const value of [
    true,
    1.5,
    "1.5",
    "invalid",
    "1 - 2",
    "1-",
    "--1",
    2147483648,
    "1-2147483648",
    "-2147483649",
  ]) {
    assert.ok(
      (await errors({ xmux: { maxConnections: value } })).length,
      JSON.stringify(value),
    );
  }
});

test("XHTTP Monaco checks native downstream mode constraints and nested socket schemas", async () => {
  const base = { address: "download.example.com", port: 443, network: "xhttp" };
  for (const settings of [
    { mode: "stream-up", uplinkHTTPMethod: "GET" },
    { mode: "stream-up", extra: { uplinkDataPlacement: "header" } },
    { mode: "stream-one", extra: { downloadSettings: base } },
  ]) {
    assert.ok(
      (await errors({ downloadSettings: { ...base, xhttpSettings: settings } }))
        .length,
      JSON.stringify(settings),
    );
  }
  for (const download of [
    { ...base, network: "tcp" },
    { ...base, port: 0 },
    { ...base, address: "" },
    { address: "example.com", port: 443 },
    { ...base, security: "reality" },
    { ...base, sockopt: { tcpFastOpen: "true" } },
  ]) {
    assert.ok(
      (await errors({ downloadSettings: download })).length,
      JSON.stringify(download),
    );
  }
});

test("XHTTP Monaco completes fields, placement values, methods, session alphabets and XMUX ranges", async () => {
  const root = (await completions("{ }", 2)).map((item) => item.label);
  for (const field of Object.keys(native.$defs.XhttpExtra.properties))
    assert.ok(root.includes(field), field);
  for (const [field, values] of [
    ["uplinkHTTPMethod", ["GET", "PUT", "POST"]],
    ["xPaddingMethod", ["repeat-x", "tokenish"]],
    ["sessionIDPlacement", ["path", "header", "cookie", "query"]],
    ["sessionIDTable", ["Base62", "hex", "number"]],
  ] as const) {
    const text = `{"${field}": }`;
    const items = (await completions(text, text.indexOf(":") + 2)).map(
      (item) => item.label,
    );
    for (const value of values)
      assert.ok(items.includes(`"${value}"`), `${field}: ${value}`);
  }
  const text = '{"xmux":{ }}';
  const fields = (await completions(text, text.indexOf("{ }") + 2)).map(
    (item) => item.label,
  );
  for (const name of [
    "maxConcurrency",
    "maxConnections",
    "cMaxReuseTimes",
    "hMaxRequestTimes",
    "hMaxReusableSecs",
    "hKeepAlivePeriod",
  ]) {
    assert.ok(fields.includes(name), name);
  }
});

test("XHTTP Monaco shows method restrictions and units on hover and offers usable root examples", async () => {
  for (const [field, explanation] of [
    ["uplinkHTTPMethod", /GET.*packet.*up/],
    ["scMinPostsIntervalMs", /milliseconds/],
    ["uplinkChunkSize", /bytes/],
    ["downloadSettings", /stream.*one/],
    ["scMaxConcurrentPosts", /Legacy/],
  ] as const) {
    const source = document(`{"${field}":null}`);
    const hover = await service.doHover(
      source,
      source.positionAt(3),
      service.parseJSONDocument(source),
    );
    assert.match(JSON.stringify(hover?.contents), explanation);
  }
  const labels = (await completions("", 0)).map((item) => item.label);
  for (const snippet of native.$defs.XhttpExtra.defaultSnippets) {
    assert.ok(labels.includes(snippet.label), snippet.label);
    assert.deepEqual(await errors(snippet.body), [], snippet.label);
  }
});
