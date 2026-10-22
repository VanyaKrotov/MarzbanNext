import assert from "node:assert/strict";
import { test } from "node:test";
import { compositionSchema, templateLanguage } from "../src/pages/subscription-templates-page/lib/composition";
import { xrayCoreSchema } from "../src/lib/xray-schemas/core";
import type { MonacoJsonSchema } from "../src/components/MonacoJsonEditor";

const capabilities = {
  type: "object",
  additionalProperties: false,
  properties: { injectHosts: { type: "array", items: { $ref: "#/$defs/InjectHosts" } } },
  $defs: {
    InjectHosts: { type: "object", required: ["tagPrefix"], properties: {
      tagPrefix: { type: "string", minLength: 1, maxLength: 256 },
      selector: { $ref: "#/$defs/Selector" },
    } },
    Selector: { type: "object", required: ["type"], properties: {
      type: { enum: ["ids", "groups", "sameGroupsAsRecipient"] },
      values: { type: "array" },
    } },
  },
};

test("nested backend schema references resolve at the client document root without modifying the response", () => {
  const before = structuredClone(capabilities);
  for (const format of ["v2ray-json", "sing-box", "clash"] as const) {
    const schema = compositionSchema(format, capabilities)!;
    const references: string[] = [];
    JSON.stringify(schema, (key, value) => {
      if (key === "$ref") references.push(value);
      return value;
    });
    assert.ok(references.length > 0);
    for (const reference of references) {
      assert.ok(reference.startsWith("#/definitions/"));
      let target: unknown = schema;
      for (const key of reference.slice(2).split("/")) {
        assert.ok(target && typeof target === "object");
        target = (target as Record<string, unknown>)[key];
      }
      assert.ok(target, `Unresolved schema reference: ${reference}`);
    }
    assert.deepEqual(schema.definitions?.Selector, capabilities.$defs.Selector);
  }
  assert.deepEqual(capabilities, before);
});

test("client Xray rules accept optional managed tags without changing the server schema", () => {
  const server = structuredClone(xrayCoreSchema);
  const schema = compositionSchema("v2ray-json", capabilities)!;
  const routing = schema.properties!.routing as MonacoJsonSchema;
  const rules = routing.properties!.rules as MonacoJsonSchema;
  const outbounds = schema.properties!.outbounds as MonacoJsonSchema;
  assert.deepEqual((rules.items as MonacoJsonSchema).required, ["type"]);
  assert.deepEqual((outbounds.items as MonacoJsonSchema).required, ["protocol"]);
  assert.ok(server.properties?.routing);
  assert.deepEqual(xrayCoreSchema, server);
});

test("Clash JSON receives JSON schema support while YAML and Jinja retain their language", () => {
  for (const content of ['{"proxies": []}', '{\n  "proxy-groups": []}', "{", "{}"])
    assert.equal(templateLanguage("clash", content), "json");
  for (const content of ["proxies: []", "{{ conf | yaml }}", "{% set a = 1 %}\nproxies: []", "{proxies: []}"])
    assert.equal(templateLanguage("clash", content), "yaml");
  assert.equal(templateLanguage("sing-box", "{}"), "json");
  assert.equal(templateLanguage("v2ray", "{{ links }}"), "text");
});

test("link and Outline formats do not advertise composition directives", () => {
  for (const format of ["v2ray", "outline"] as const)
    assert.equal(compositionSchema(format, capabilities), undefined);
});
