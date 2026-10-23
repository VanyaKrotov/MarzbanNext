import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

// Exercise the editor's own language service, including completion and hover behavior.
import { getLanguageService } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageService.js";
import { TextDocument } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageTypes.js";
import { jsonParameterSchema } from "../src/pages/hosts-page/components/host-dialog/lib/json-parameters";

// The Python schema test verifies this fixture against the actual capabilities model.
const { $defs, ...mapper } = JSON.parse(
  readFileSync(
    new URL("./fixtures/host-mapper-schema.json", import.meta.url),
    "utf8",
  ),
);
const schema = jsonParameterSchema(["mapper"], {
  $defs,
  properties: { mapper },
});
const documentUri = "inmemory://host-mapper.json";
const service = getLanguageService({});
service.configure({
  validate: true,
  allowComments: false,
  schemas: [
    {
      uri: "inmemory://host-mapper.schema.json",
      fileMatch: [documentUri],
      schema,
    },
  ],
});

function document(text: string) {
  return TextDocument.create(documentUri, "json", 1, text);
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

test("Monaco accepts all mapper operations and JSON value types in every output family", async () => {
  for (const target of ["xrayJson", "clash", "singbox", "base64"]) {
    for (const value of [
      "",
      0,
      -1,
      1.5,
      false,
      true,
      null,
      [],
      {},
      [null, { key: false }],
    ]) {
      assert.deepEqual(
        await errors({
          [target]: [
            { op: "set", to: "custom.option", value },
            { op: "copy", from: "$host.port", to: "custom.port" },
            { op: "unset", to: "custom.obsolete" },
          ],
        }),
        [],
        `${target}: ${JSON.stringify(value)}`,
      );
    }
  }
  assert.deepEqual(await errors({}), []);
  assert.deepEqual(
    await errors({ clash: null, xrayJson: [], singbox: [], base64: [] }),
    [],
  );
});

test("Monaco rejects missing, incompatible and unknown operation fields", async () => {
  const invalid = [
    {},
    { op: "move", to: "udp" },
    { op: "set", value: true },
    { op: "set", to: "udp" },
    { op: "copy", to: "udp" },
    { op: "copy", to: "udp", from: "" },
    { op: "copy", to: "udp", from: null },
    { op: "copy", to: "udp", from: 1 },
    { op: "set", to: "udp", value: true, from: "$host.port" },
    { op: "copy", to: "udp", from: "$host.port", value: true },
    { op: "unset", to: "udp", value: null },
    { op: "unset", to: "udp", from: "$host.port" },
    { op: "unset", to: "udp", unknown: true },
    ...["", 1, null, "a.__proto__.b", "constructor", "__class__"].map((to) => ({
      op: "unset",
      to,
    })),
  ];
  for (const target of ["xrayJson", "clash", "singbox", "base64"]) {
    for (const operation of invalid) {
      assert.ok(
        (await errors({ [target]: [operation] })).length,
        `${target}: ${JSON.stringify(operation)}`,
      );
    }
  }
  for (const target of [
    "outline",
    "v2ray-json",
    "sing-box",
    "clash-meta",
    "mihomo",
  ]) {
    assert.ok((await errors({ [target]: [] })).length, target);
  }
});

test("Monaco suggests only the fields belonging to the selected operation", async () => {
  for (const op of ["set", "copy", "unset"]) {
    const text = `{"clash":[{"op":"${op}", }]}`;
    const labels = (await completions(text, text.indexOf(",") + 2)).map(
      (item) => item.label,
    );
    assert.ok(labels.includes("to"));
    assert.equal(labels.includes("value"), op === "set");
    assert.equal(labels.includes("from"), op === "copy");
  }
});

test("Monaco completes format names, operation names and resolved host/inbound sources", async () => {
  const families = (await completions("{ }", 2)).map((item) => item.label);
  for (const target of ["xrayJson", "clash", "singbox", "base64"])
    assert.ok(families.includes(target));

  const operation = '{"clash":[{"op": }]}';
  const actions = (
    await completions(operation, operation.indexOf(":", 10) + 1)
  ).map((item) => item.label);
  for (const action of ["set", "copy", "unset"])
    assert.ok(actions.includes(`"${action}"`));

  const source = '{"clash":[{"op":"copy","to":"sni","from": }]}';
  const sources = await completions(source, source.lastIndexOf(":") + 2);
  for (const path of [
    "$host.address",
    "$host.port",
    "$host.protocolOptions.id",
    "$host.metadata.remark",
    "settings.clients[0].id",
  ]) {
    assert.ok(
      sources.some((item) => item.label === `"${path}"`),
      path,
    );
  }
  const address = sources.find((item) => item.label === '"$host.address"');
  assert.ok(
    address?.insertText?.includes("\\$host.address"),
    "host placeholders must insert a literal dollar sign",
  );
});

test("Monaco hover explains copy sources and root templates cover all four output families", async () => {
  const text = '{"clash":[{"op":"copy","to":"sni","from":"$host.address"}]}';
  const source = document(text);
  const hover = await service.doHover(
    source,
    source.positionAt(text.indexOf('"from"') + 2),
    service.parseJSONDocument(source),
  );
  assert.match(
    JSON.stringify(hover?.contents),
    /Source path in the raw inbound/,
  );
  const labels = (await completions("", 0)).map((item) => item.label);
  for (const label of [
    "Xray JSON",
    "Clash: set, copy and unset",
    "sing-box",
    "URI / VMess",
  ]) {
    assert.ok(labels.includes(label), label);
  }
});
