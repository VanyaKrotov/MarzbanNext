import assert from "node:assert/strict";
import { test } from "node:test";

import {
  getHostFormValues,
  hostFormSchema,
} from "../src/pages/hosts-page/components/host-dialog/lib/form";
import { toHostPayload } from "../src/pages/hosts-page/components/host-dialog/lib/payload";
import {
  commonTemplateFormats,
  hostTemplateFormats,
  subscriptionFormats,
} from "../src/pages/subscription-templates-page/lib/formats";
import {
  getAvailableParameterGroups,
  getPath,
  getParameterSelectOptions,
  hostParameters,
  setPath,
} from "../src/pages/hosts-page/components/host-dialog/lib/parameters";
import {
  jsonParameterSchema,
  parseJsonObject,
  type HostOverridesSchema,
} from "../src/pages/hosts-page/components/host-dialog/lib/json-parameters";
import type { HostType, JsonObject } from "../src/pages/hosts-page/types";
import {
  alpnOptions,
  getAlpnSelection,
} from "../src/pages/hosts-page/components/host-dialog/lib/alpn";
import {
  getHostTemplateOptions,
  getSelectedHostTemplates,
  templateBindingsFromSelection,
  templateChipLabel,
} from "../src/pages/hosts-page/components/host-dialog/lib/template-selection";

function formValues() {
  return { ...getHostFormValues(1), remark: "Example", address: "example.com" };
}

function storedHost(overrides: JsonObject): HostType {
  return {
    id: 1,
    inbound_id: 1,
    inbound_tag: "VLESS",
    inbound_port: 443,
    position: 0,
    remark: "Example",
    address: "example.com",
    port: null,
    enabled: true,
    is_hidden: false,
    overrides,
    groups: [],
    subscription_template_ids: {},
    created_at: "2024-01-01T00:00:00",
    updated_at: "2024-01-01T00:00:00",
  };
}

test("fingerprint select preserves empty client defaults and stored version-specific profiles", () => {
  const fingerprint = hostParameters.find(
    (parameter) => parameter.id === "fingerprint",
  );
  assert.equal(fingerprint?.kind, "select");
  if (fingerprint?.kind !== "select") return;
  const presets = fingerprint.options.map(([value]) => value);
  for (const value of ["", ...presets, "hellochrome_131"]) {
    const original = storedHost({ security: { fingerprint: value } });
    const form = getHostFormValues(1, original);
    assert.equal(form.parameters.fingerprint, value);
    assert.deepEqual(toHostPayload(hostFormSchema.parse(form)).overrides, {});
    if (value) {
      assert.ok(
        getParameterSelectOptions(fingerprint, value).some(
          ([option]) => option === value,
        ),
      );
    }
    form.selected = form.selected.filter((id) => id !== "fingerprint");
    assert.deepEqual(toHostPayload(hostFormSchema.parse(form)).overrides, {
      security: null,
    });
  }
  assert.equal(
    fingerprint.options.some(([value]) => value === "hellochrome_131"),
    false,
  );
});

test("choosing client default fingerprint explicitly clears the inherited fingerprint", () => {
  const form = formValues();
  form.selected = ["fingerprint"];
  form.parameters.fingerprint = "";
  assert.deepEqual(toHostPayload(hostFormSchema.parse(form)).overrides, {
    security: { fingerprint: "" },
  });
  form.parameters.fingerprint = "chrome";
  assert.deepEqual(toHostPayload(hostFormSchema.parse(form)).overrides, {
    security: { fingerprint: "chrome" },
  });
});

test("client JSON preserves nested values, false and an empty description", () => {
  const values = formValues();
  values.selected = ["clients"];
  values.parameters.clients = JSON.stringify({
    clash: { ip_version: "ipv6-prefer", x25519: false },
    server_description: "",
  });
  assert.deepEqual(toHostPayload(hostFormSchema.parse(values)).overrides, {
    clients: {
      clash: { ip_version: "ipv6-prefer", x25519: false },
      server_description: "",
    },
  });
});

test("saved client JSON opens as one field and saves without changing data", () => {
  const host = storedHost({
    clients: {
      clash: { ip_version: "dual", x25519: false },
      server_description: "Europe",
    },
  });
  const before = structuredClone(host);
  const values = getHostFormValues(1, host);
  assert.ok(values.selected.includes("clients"));
  for (const id of ["ip_version", "x25519", "server_description"]) {
    assert.equal(values.selected.includes(id), false);
  }
  assert.deepEqual(
    JSON.parse(values.parameters.clients),
    host.overrides.clients,
  );
  assert.deepEqual(toHostPayload(hostFormSchema.parse(values)).overrides, {});
  assert.deepEqual(host, before);
});

test("editing client JSON deletes omitted nested keys and preserves other overrides", () => {
  const values = getHostFormValues(
    1,
    storedHost({
      clients: {
        clash: { ip_version: "dual", x25519: false },
        server_description: "Europe",
      },
      security: { sni: "example.com" },
    }),
  );
  values.parameters.clients = JSON.stringify({
    clash: { ip_version: "ipv4" },
    server_description: "",
  });
  assert.deepEqual(toHostPayload(hostFormSchema.parse(values)).overrides, {
    clients: {
      clash: { ip_version: "ipv4", x25519: null },
      server_description: "",
    },
  });
  values.selected = values.selected.filter((id) => id !== "clients");
  assert.deepEqual(toHostPayload(hostFormSchema.parse(values)).overrides, {
    clients: null,
  });
});

test("the dynamic menu offers one client JSON field and excludes it once added", () => {
  const group = getAvailableParameterGroups([], true).find(
    (item) => item.id === "subscription",
  );
  const ids = group?.options.map((option) => option.id);
  assert.ok(ids?.includes("clients"));
  assert.equal(ids?.includes("ip_version"), false);
  assert.equal(ids?.includes("server_description"), false);
  assert.equal(ids?.includes("x25519"), false);
  assert.equal(
    getAvailableParameterGroups(["clients"], true)
      .flatMap((item) => item.options)
      .some((item) => item.id === "clients"),
    false,
  );
});

test("JSON object editors reject empty text, arrays, primitives and malformed JSON", () => {
  for (const text of [
    "",
    "null",
    "[]",
    "false",
    "1",
    '"value"',
    "{",
    '{"key":1,}',
  ]) {
    assert.throws(() => parseJsonObject(text));
    const values = formValues();
    values.selected = ["clients"];
    values.parameters.clients = text;
    if (text)
      assert.throws(() => toHostPayload(values), { parameter: "clients" });
  }
  assert.deepEqual(parseJsonObject('{"enabled":false,"count":0,"name":""}'), {
    enabled: false,
    count: 0,
    name: "",
  });
});

test("all JSON object fields round trip through the form without losing stored settings", () => {
  const overrides = {
    transport: {
      xhttp: {
        extra: {
          scMaxBufferedPosts: 0,
          xPaddingObfsMode: false,
          uplinkHTTPMethod: "PUT",
        },
      },
    },
    mux: { enabled: false, xray: { concurrency: 0 } },
    stream: { sockopt: { tcpFastOpen: false }, final_mask: { tcp: [] } },
    clients: {
      clash: { ip_version: "ipv4", x25519: false },
      server_description: "",
    },
    mapper: { clash: [{ op: "set", to: "udp", value: false }] },
  };
  const host = storedHost(overrides);
  const before = structuredClone(host);
  const values = getHostFormValues(1, host);
  for (const definition of hostParameters.filter(
    (item) => item.kind === "json" && item.id !== "alpn",
  )) {
    assert.ok(values.selected.includes(definition.id));
    assert.doesNotThrow(() =>
      parseJsonObject(values.parameters[definition.id]),
    );
  }
  assert.deepEqual(toHostPayload(values).overrides, {});
  assert.deepEqual(host, before);
});

test("field schemas resolve nullable parent references and keep shared definitions intact", () => {
  const root: HostOverridesSchema = {
    type: "object",
    properties: {
      transport: { anyOf: [{ $ref: "#/$defs/Transport" }, { type: "null" }] },
    },
    $defs: {
      Transport: {
        type: "object",
        properties: {
          xhttp: { anyOf: [{ $ref: "#/$defs/Xhttp" }, { type: "null" }] },
        },
      },
      Xhttp: {
        type: "object",
        properties: {
          extra: { anyOf: [{ $ref: "#/$defs/Extra" }, { type: "null" }] },
        },
      },
      Extra: {
        type: "object",
        properties: { uplinkHTTPMethod: { type: "string" } },
        additionalProperties: false,
      },
    },
  };
  const before = structuredClone(root);
  const schema = jsonParameterSchema(["transport", "xhttp", "extra"], root);
  assert.equal(schema.type, "object");
  assert.equal(schema.allOf?.[0].anyOf?.[0].$ref, "#/definitions/Extra");
  assert.deepEqual(schema.definitions?.Extra, root.$defs?.Extra);
  assert.equal(
    schema.definitions?.Transport.properties?.xhttp.anyOf?.[0].$ref,
    "#/definitions/Xhttp",
  );
  assert.deepEqual(root, before);
  assert.equal(jsonParameterSchema(["clients"]).type, "object");
});

test("ALPN selection preserves protocol order, custom stored values and explicit empty arrays", () => {
  assert.deepEqual(alpnOptions, ["h3", "h2", "http/1.1"]);
  const values = formValues();
  values.selected = ["alpn"];
  for (const protocols of [["h2", "http/1.1"], ["custom-alpn", "h3"], []]) {
    values.parameters.alpn = JSON.stringify(protocols);
    assert.deepEqual(getAlpnSelection(values.parameters.alpn), protocols);
    assert.deepEqual(toHostPayload(hostFormSchema.parse(values)).overrides, {
      security: { alpn: protocols },
    });
  }
  values.original_overrides = { security: { alpn: ["h2"] } };
  values.selected = [];
  assert.deepEqual(toHostPayload(hostFormSchema.parse(values)).overrides, {
    security: null,
  });
});

test("ALPN input tolerates absent and malformed stored text without changing the payload", () => {
  assert.deepEqual(getAlpnSelection(""), []);
  assert.deepEqual(getAlpnSelection("not JSON"), []);
  assert.deepEqual(getAlpnSelection('["h2",1]'), []);
  assert.deepEqual(getAlpnSelection('["h2","h2","http/1.1"]'), [
    "h2",
    "http/1.1",
  ]);
  const values = formValues();
  values.selected = ["alpn"];
  values.parameters.alpn = "not JSON";
  assert.throws(() => toHostPayload(hostFormSchema.parse(values)), {
    parameter: "alpn",
  });
});

test("a new host starts without optional parameters or explicit template bindings", () => {
  const values = formValues();
  const payload = toHostPayload(hostFormSchema.parse(values));
  assert.deepEqual(values.selected, []);
  assert.equal(payload.port, null);
  assert.equal(payload.enabled, true);
  assert.equal("subscription_template_ids" in payload, false);
});

test("clash is the only YAML format in the catalog", () => {
  assert.deepEqual(subscriptionFormats, [
    "v2ray",
    "v2ray-json",
    "clash",
    "sing-box",
    "outline",
  ]);
});

test("XHTTP extra preserves zero and false and normalizes the method", () => {
  const values = formValues();
  values.selected = ["xhttp_extra"];
  values.parameters.xhttp_extra =
    '{"scMaxBufferedPosts":0,"xPaddingObfsMode":false,"uplinkHTTPMethod":" put "}';
  values.original_overrides = {
    transport: { xhttp: { extra: { xPaddingBytes: "100-200" } } },
  };
  const payload = toHostPayload(hostFormSchema.parse(values));
  assert.deepEqual(payload.overrides, {
    transport: {
      xhttp: {
        extra: {
          scMaxBufferedPosts: 0,
          xPaddingObfsMode: false,
          uplinkHTTPMethod: "PUT",
        },
      },
    },
  });
});

test("removing an optional override sends a deletion", () => {
  const values = formValues();
  values.original_overrides = { security: { sni: "old.example.com" } };
  assert.deepEqual(toHostPayload(hostFormSchema.parse(values)).overrides, {
    security: null,
  });
});

test("selected text fields preserve both empty and filled input values", () => {
  const values = formValues();
  values.selected = ["sni", "path", "fingerprint"];
  values.parameters = { sni: "", path: "/custom", fingerprint: "" };
  values.original_overrides = { security: { sni: "old.example.com" } };
  assert.deepEqual(toHostPayload(hostFormSchema.parse(values)).overrides, {
    security: { sni: "", fingerprint: "" },
    transport: { path: "/custom" },
  });
  values.selected = [];
  assert.deepEqual(toHostPayload(hostFormSchema.parse(values)).overrides, {
    security: null,
  });
});

test("selected boolean switches default to false and groups do not require an optional section", () => {
  const values = formValues();
  values.selected = ["allow_insecure", "security"];
  values.group_ids = ["basic"];
  const payload = toHostPayload(hostFormSchema.parse(values));
  assert.deepEqual(payload.overrides, { security: { allow_insecure: false } });
  assert.deepEqual(payload.group_ids, ["basic"]);
});

test("each newly added boolean switch saves its initial off state explicitly", () => {
  for (const definition of hostParameters.filter(
    (item) => item.kind === "boolean",
  )) {
    for (const value of [undefined, "", "false"]) {
      const values = formValues();
      values.selected = [definition.id];
      if (value !== undefined) values.parameters[definition.id] = value;
      const expected: JsonObject = {};
      setPath(expected, definition.path, false);
      assert.deepEqual(
        toHostPayload(hostFormSchema.parse(values)).overrides,
        expected,
      );
      values.selected = [];
      assert.deepEqual(
        toHostPayload(hostFormSchema.parse(values)).overrides,
        {},
      );
    }
  }
});

test("boolean switches preserve saved values, toggle explicitly and delete only their override", () => {
  for (const definition of hostParameters.filter(
    (item) => item.kind === "boolean",
  )) {
    for (const enabled of [false, true]) {
      const overrides: JsonObject = {
        security: { sni: "example.com" },
        transport: { path: "/proxy" },
      };
      setPath(overrides, definition.path, enabled);
      const before = structuredClone(overrides);
      const values = getHostFormValues(1, storedHost(overrides));
      assert.ok(values.selected.includes(definition.id));
      assert.equal(values.parameters[definition.id], String(enabled));
      assert.deepEqual(
        toHostPayload(hostFormSchema.parse(values)).overrides,
        {},
      );

      values.parameters[definition.id] = String(!enabled);
      const toggled = toHostPayload(hostFormSchema.parse(values)).overrides;
      assert.equal(getPath(toggled, definition.path), !enabled);

      values.selected = values.selected.filter((id) => id !== definition.id);
      const expected: JsonObject = {};
      setPath(expected, definition.path, null);
      assert.deepEqual(
        toHostPayload(hostFormSchema.parse(values)).overrides,
        expected,
      );
      assert.deepEqual(overrides, before);
    }
  }
});

test("the grouped option menu excludes selected parameters and incompatible XHTTP", () => {
  const groups = getAvailableParameterGroups(["sni", "templates"], false);
  const options = groups.flatMap((group) =>
    group.options.map((option) => option.id),
  );
  assert.equal(options.includes("sni"), false);
  assert.equal(options.includes("templates"), false);
  assert.equal(options.includes("groups"), false);
  assert.equal(options.includes("xhttp_extra"), false);
  assert.equal(options.includes("keep_sni_blank"), false);
  assert.ok(
    groups
      .find((group) => group.id === "security")
      ?.options.some((option) => option.id === "alpn"),
  );
  assert.ok(
    getAvailableParameterGroups([], true)
      .flatMap((group) => group.options)
      .some((option) => option.id === "xhttp_extra"),
  );
});

test("selecting a template replaces only the existing binding of its format", () => {
  const previous = { clash: 1, "sing-box": 3 };
  for (const selected of [
    [
      { id: 1, format: "clash" },
      { id: 2, format: "clash" },
      { id: 3, format: "sing-box" },
    ],
    [
      { id: 2, format: "clash" },
      { id: 1, format: "clash" },
      { id: 3, format: "sing-box" },
    ],
  ] as const) {
    assert.deepEqual(templateBindingsFromSelection(selected, previous), {
      clash: 2,
      "sing-box": 3,
    });
  }
  assert.deepEqual(previous, { clash: 1, "sing-box": 3 });
});

function templateChoices() {
  return subscriptionFormats.flatMap((format, index) => [
    { id: index + 1, format, name: "Main", is_default: true },
    { id: index + 11, format, name: "Custom", is_default: false },
  ]);
}

test("all formats are available in the picker but common formats only offer their current default", () => {
  const templates = templateChoices();
  const before = structuredClone(templates);
  const options = getHostTemplateOptions(templates);
  for (const format of commonTemplateFormats) {
    const choices = options.filter((template) => template.format === format);
    assert.equal(choices.length, 1);
    assert.equal(choices[0].is_default, true);
  }
  for (const format of hostTemplateFormats) {
    assert.equal(
      options.filter((template) => template.format === format).length,
      2,
    );
  }
  assert.deepEqual(templates, before);
});

test("common chips display the current default for legacy bindings while personal chips keep their choice", () => {
  const templates = templateChoices();
  const bindings = { v2ray: 11, "v2ray-json": 12, clash: 13, "sing-box": 14 };
  const selected = getSelectedHostTemplates(
    getHostTemplateOptions(templates),
    bindings,
  );
  assert.deepEqual(
    selected.map((template) => template.id),
    [11, 12, 3, 4],
  );
  const changedDefaults = templates.map((template) =>
    template.format === "clash"
      ? { ...template, is_default: template.id === 13 }
      : template,
  );
  assert.deepEqual(
    getSelectedHostTemplates(
      getHostTemplateOptions(changedDefaults),
      bindings,
    ).map((template) => template.id),
    [11, 12, 13, 4],
  );
  assert.deepEqual(bindings, {
    v2ray: 11,
    "v2ray-json": 12,
    clash: 13,
    "sing-box": 14,
  });
});

test("removing and reselecting common chips disables and enables only the selected format", () => {
  const options = getHostTemplateOptions(templateChoices());
  const bindings = {
    v2ray: 11,
    "v2ray-json": 12,
    clash: 13,
    "sing-box": 14,
    outline: 15,
  };
  const selected = getSelectedHostTemplates(options, bindings);
  for (const format of commonTemplateFormats) {
    const remaining = templateBindingsFromSelection(
      selected.filter((template) => template.format !== format),
      bindings,
    );
    assert.equal(remaining[format], undefined);
    assert.equal(remaining.v2ray, 11);
    assert.equal(remaining["v2ray-json"], 12);
    const defaultTemplate = options.find(
      (template) => template.format === format,
    )!;
    const restored = templateBindingsFromSelection(
      [...getSelectedHostTemplates(options, remaining), defaultTemplate],
      remaining,
    );
    assert.equal(restored[format], defaultTemplate.id);
    assert.equal(restored.v2ray, 11);
    assert.equal(restored["v2ray-json"], 12);
  }
  assert.deepEqual(templateBindingsFromSelection([], bindings), {});
});

test("removing a template chip excludes its format and clearing all chips disables all formats", () => {
  const previous = { clash: 1, "sing-box": 3 };
  const remaining = templateBindingsFromSelection(
    [{ id: 3, format: "sing-box" }],
    previous,
  );
  assert.deepEqual(remaining, { "sing-box": 3 });
  const values = formValues();
  values.selected = ["templates"];
  values.subscription_template_ids = templateBindingsFromSelection(
    [],
    previous,
  );
  assert.deepEqual(
    toHostPayload(hostFormSchema.parse(values)).subscription_template_ids,
    {},
  );
  assert.equal(
    templateChipLabel({ format: "clash", name: "Mobile" }),
    "clash:Mobile",
  );
});

test("visibility uses only the new host contract", () => {
  const values = formValues();
  values.is_hidden = true;
  const payload = toHostPayload(hostFormSchema.parse(values));
  assert.equal(payload.is_hidden, true);
  assert.equal("linked_host_ids" in payload, false);
  assert.equal("balancer_settings" in payload, false);
});
