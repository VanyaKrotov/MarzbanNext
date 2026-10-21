import assert from "node:assert/strict";
import { test } from "node:test";

import {
  getHostFormValues,
  hostFormSchema,
} from "../src/pages/hosts-page/components/host-dialog/lib/form";
import { toHostPayload } from "../src/pages/hosts-page/components/host-dialog/lib/payload";
import { subscriptionFormats } from "../src/pages/subscription-templates-page/lib/formats";
import { getAvailableParameterGroups } from "../src/pages/hosts-page/components/host-dialog/lib/parameters";
import {
  alpnOptions,
  getAlpnSelection,
} from "../src/pages/hosts-page/components/host-dialog/lib/alpn";
import {
  templateBindingsFromSelection,
  templateChipLabel,
} from "../src/pages/hosts-page/components/host-dialog/lib/template-selection";

function formValues() {
  return { ...getHostFormValues(1), remark: "Example", address: "example.com" };
}

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

test("empty boolean selections still inherit and groups do not require an optional section", () => {
  const values = formValues();
  values.selected = ["allow_insecure", "security"];
  values.group_ids = ["basic"];
  const payload = toHostPayload(hostFormSchema.parse(values));
  assert.deepEqual(payload.overrides, {});
  assert.deepEqual(payload.group_ids, ["basic"]);
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
