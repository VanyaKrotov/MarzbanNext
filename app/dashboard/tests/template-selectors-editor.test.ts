import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { getLanguageService } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageService.js";
import { TextDocument } from "../node_modules/monaco-editor/esm/external/vscode-json-languageservice/lib/esm/jsonLanguageTypes.js";
import { subscriptionTemplateSchema } from "../src/pages/subscription-templates-page/lib/template-editor";

// Python tests keep the fixture synchronized with the capabilities endpoint.
const capabilities = JSON.parse(
  readFileSync(
    new URL("./fixtures/template-directives-schema.json", import.meta.url),
    "utf8",
  ),
);
const formats = ["v2ray-json", "clash", "sing-box"] as const;

function setup(format: (typeof formats)[number]) {
  const uri = `inmemory://selectors-${format}.json`;
  const schema = subscriptionTemplateSchema(format, capabilities[format])!;
  const service = getLanguageService({});
  service.configure({
    validate: true,
    schemas: [{ uri: `${uri}.schema`, fileMatch: [uri], schema }],
  });
  function source(text: string) {
    return TextDocument.create(uri, "json", 1, text);
  }
  function configuration(selector: unknown) {
    if (format === "v2ray-json")
      return {
        outbounds: [],
        marzban: { injectHosts: [{ tagPrefix: "pool", selector }] },
      };
    if (format === "clash")
      return {
        proxies: [],
        "proxy-groups": [
          {
            name: "Best",
            type: "url-test",
            proxies: [],
            url: "https://example.com",
            interval: 30,
            marzban: { "include-proxies": true, selector },
          },
        ],
      };
    return {
      outbounds: [
        {
          tag: "Best",
          type: "urltest",
          outbounds: [],
          marzban: { includeProxies: true, selector },
        },
      ],
    };
  }
  async function errors(selector: unknown) {
    const document = source(JSON.stringify(configuration(selector)));
    return (
      await service.doValidation(
        document,
        service.parseJSONDocument(document),
        { schemaValidation: "error" },
      )
    ).filter((item) => item.severity === 1);
  }
  return { service, source, configuration, errors };
}

test("all template editors validate exact names, literal prefixes and regex selector structure", async () => {
  const valid = [
    { type: "ids", values: [11, 12] },
    { type: "groups", values: ["eu"] },
    { type: "remarks", values: ["EU-test", "Finland"] },
    { type: "remarkPrefix", prefix: "EU-" },
    { type: "remarkRegex", pattern: "^(NL|FI)-" },
  ];
  const invalid = [
    { type: "remarks" },
    { type: "remarks", values: [] },
    { type: "remarks", values: [1] },
    { type: "remarks", values: [""] },
    { type: "remarkPrefix" },
    { type: "remarkPrefix", prefix: "" },
    { type: "remarkPrefix", prefix: null },
    { type: "remarkPrefix", prefix: "EU", values: [] },
    { type: "remarkRegex" },
    { type: "remarkRegex", pattern: 1 },
    { type: "remarkRegex", pattern: "" },
    { type: "remarkRegex", pattern: "a".repeat(1025) },
    { type: "ids", values: ["1"] },
    { type: "remarkRegex", pattern: "EU", prefix: "EU" },
  ];
  for (const format of formats) {
    const editor = setup(format);
    for (const selector of valid)
      assert.deepEqual(
        await editor.errors(selector),
        [],
        `${format}: ${JSON.stringify(selector)}`,
      );
    for (const selector of invalid)
      assert.ok(
        (await editor.errors(selector)).length,
        `${format}: ${JSON.stringify(selector)}`,
      );
    const sameGroupsErrors = await editor.errors({
      type: "sameGroupsAsRecipient",
    });
    assert.equal(sameGroupsErrors.length === 0, format === "v2ray-json");
  }
});

test("Monaco offers name selector types, examples and descriptions in each format", async () => {
  for (const format of formats) {
    const editor = setup(format);
    const text = JSON.stringify(editor.configuration({ type: "" }));
    const document = editor.source(text);
    const offset = text.indexOf('"type":""') + '"type":"'.length;
    const completion = await editor.service.doComplete(
      document,
      document.positionAt(offset),
      editor.service.parseJSONDocument(document),
    );
    for (const kind of ["remarks", "remarkPrefix", "remarkRegex"])
      assert.ok(
        completion.items.some((item) => item.label === `"${kind}"`),
        `${format}: ${kind}`,
      );
    const schema = subscriptionTemplateSchema(format, capabilities[format])!;
    const selector = schema.definitions!.Selector as {
      defaultSnippets: unknown[];
      properties: Record<string, { description?: string }>;
    };
    assert.equal(selector.defaultSnippets.length, 4);
    for (const field of ["type", "values", "prefix", "pattern"])
      assert.ok(selector.properties[field].description, field);
    const prefixText = JSON.stringify(
      editor.configuration({ type: "remarkPrefix", prefix: "EU-" }),
    );
    const prefixDocument = editor.source(prefixText);
    const hover = await editor.service.doHover(
      prefixDocument,
      prefixDocument.positionAt(prefixText.indexOf('"prefix"') + 3),
      editor.service.parseJSONDocument(prefixDocument),
    );
    assert.match(JSON.stringify(hover), /rendered host name/);
  }
});
