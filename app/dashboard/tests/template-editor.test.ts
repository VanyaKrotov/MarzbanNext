import assert from "node:assert/strict";
import { test } from "node:test";
import {
  subscriptionTemplateSchema,
  supportsComposition,
  templateLanguage,
} from "../src/pages/subscription-templates-page/lib/template-editor";
import {
  containsTemplateExpression,
  templateExpressionPrefix,
} from "../src/components/monaco-template-support";
import { templateVariables } from "../src/pages/subscription-templates-page/lib/template-variables";
import { xrayCoreSchema } from "../src/lib/xray-schemas/core";
import type { MonacoJsonSchema } from "../src/components/MonacoJsonEditor";

const capabilities = {
  type: "object",
  additionalProperties: false,
  properties: {
    injectHosts: { type: "array", items: { $ref: "#/$defs/InjectHosts" } },
  },
  $defs: {
    InjectHosts: {
      type: "object",
      required: ["tagPrefix"],
      properties: {
        tagPrefix: { type: "string", minLength: 1, maxLength: 256 },
        selector: { $ref: "#/$defs/Selector" },
      },
    },
    Selector: {
      type: "object",
      required: ["type"],
      properties: {
        type: { enum: ["ids", "groups", "sameGroupsAsRecipient"] },
        values: { type: "array" },
      },
    },
  },
};

test("nested backend schema references resolve at the client document root without modifying the response", () => {
  const before = structuredClone(capabilities);
  for (const format of ["v2ray-json", "sing-box", "clash"] as const) {
    const schema = subscriptionTemplateSchema(format, capabilities)!;
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
  const schema = subscriptionTemplateSchema("v2ray-json", capabilities)!;
  const routing = schema.properties!.routing as MonacoJsonSchema;
  const rules = routing.properties!.rules as MonacoJsonSchema;
  const outbounds = schema.properties!.outbounds as MonacoJsonSchema;
  assert.deepEqual((rules.items as MonacoJsonSchema).required, ["type"]);
  assert.deepEqual((outbounds.items as MonacoJsonSchema).required, [
    "protocol",
  ]);
  assert.ok(server.properties?.routing);
  assert.deepEqual(xrayCoreSchema, server);
});

test("Clash JSON receives JSON schema support while YAML and Jinja retain their language", () => {
  for (const content of [
    '{"proxies": []}',
    '{\n  "proxy-groups": []}',
    "{",
    "{}",
  ])
    assert.equal(templateLanguage("clash", content), "json");
  for (const content of [
    "proxies: []",
    "{{ conf | yaml }}",
    "{% set a = 1 %}\nproxies: []",
    "{proxies: []}",
  ])
    assert.equal(templateLanguage("clash", content), "yaml");
  assert.equal(templateLanguage("sing-box", "{}"), "json");
  assert.equal(templateLanguage("v2ray", "{{ links }}"), "text");
});

test("link and Outline formats do not advertise composition directives", () => {
  for (const format of ["v2ray", "outline"] as const)
    assert.equal(supportsComposition(format), false);
  assert.equal(subscriptionTemplateSchema("v2ray", capabilities), undefined);
  const outline = subscriptionTemplateSchema("outline", capabilities)!;
  assert.ok(outline.properties?.server_port);
  assert.equal(outline.properties?.marzban, undefined);
});

test("template schemas document every advertised top-level field", () => {
  for (const format of [
    "v2ray-json",
    "sing-box",
    "clash",
    "outline",
  ] as const) {
    const schema = subscriptionTemplateSchema(format, capabilities)!;
    assert.ok(schema.description, format);
    for (const [name, field] of Object.entries(schema.properties!))
      assert.ok(
        (field as MonacoJsonSchema).description,
        `${format}.${name} has no explanation`,
      );
  }
});

test("Xray subscriptions retain detailed native transport, DNS and balancing schemas", () => {
  const schema = subscriptionTemplateSchema("v2ray-json", capabilities)!;
  const native = JSON.parse(JSON.stringify(xrayCoreSchema)) as MonacoJsonSchema;
  for (const key of ["dns", "observatory", "burstObservatory", "policy"])
    assert.deepEqual(schema.properties![key], native.properties![key]);
  const outbound = (schema.properties!.outbounds as MonacoJsonSchema)
    .items as MonacoJsonSchema;
  assert.ok(outbound.allOf?.length);
  const serverOutbound = (native.properties!.outbounds as MonacoJsonSchema)
    .items as MonacoJsonSchema;
  assert.deepEqual(
    outbound.properties?.streamSettings,
    serverOutbound.properties?.streamSettings,
  );
  const routing = schema.properties!.routing as MonacoJsonSchema;
  const balancer = (routing.properties!.balancers as MonacoJsonSchema)
    .items as MonacoJsonSchema;
  const strategy = balancer.properties!.strategy as MonacoJsonSchema;
  assert.ok(
    (strategy.properties!.settings as MonacoJsonSchema).properties?.costs,
  );
});

test("Jinja completion context is isolated by format and active expression", () => {
  assert.equal(templateExpressionPrefix("outbounds: []\n{{ host."), " host.");
  assert.equal(
    templateExpressionPrefix("{{ host.id }}\nproxies: []"),
    undefined,
  );
  assert.equal(templateExpressionPrefix("{% if host_ids"), " if host_ids");
  assert.equal(containsTemplateExpression('{"outbounds":[]}'), false);
  assert.equal(containsTemplateExpression("{{ config | tojson }}"), true);
  assert.equal(containsTemplateExpression("{# comment #}"), true);
  assert.ok(templateVariables.v2ray.some(({ label }) => label === "links"));
  assert.ok(templateVariables.outline.some(({ label }) => label === "config"));
  assert.ok(
    !templateVariables["sing-box"].some(({ label }) => label === "host"),
  );
});
