import assert from "node:assert/strict";
import { test } from "node:test";

import {
  getHostFormValues,
  hostFormSchema,
} from "../src/pages/hosts-page/components/host-dialog/lib/form";
import { toHostPayload } from "../src/pages/hosts-page/components/host-dialog/lib/payload";
import {
  getBalancerClientFormValues,
  serializeBalancerClients,
} from "../src/pages/hosts-page/lib/balancer";
import { subscriptionFormats } from "../src/pages/subscription-templates-page/lib/formats";
import { getAvailableParameterGroups } from "../src/pages/hosts-page/components/host-dialog/lib/parameters";
import {
  templateBindingsFromSelection,
  templateChipLabel,
} from "../src/pages/hosts-page/components/host-dialog/lib/template-selection";

function formValues() {
  return { ...getHostFormValues(1), remark: "Example", address: "example.com" };
}

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

test("structured client settings preserve zero, false and least-load arrays", () => {
  const clients = getBalancerClientFormValues({
    clash: { tolerance: 0, lazy: false },
    "v2ray-json": {
      strategy: "least_load",
      strategy_settings: {
        failure_tolerance: 0,
        baselines_ms: [100, 200],
        costs: [{ host_id: 1, value: 2 }],
      },
    },
  });
  assert.equal(clients["clash"]?.lazy, false);
  assert.deepEqual(serializeBalancerClients(clients, "least_ping"), {
    clash: { tolerance: 0, lazy: false },
    "v2ray-json": {
      strategy: "least_load",
      strategy_settings: {
        failure_tolerance: 0,
        baselines_ms: [100, 200],
        costs: [{ host_id: 1, value: 2 }],
      },
    },
  });
});

test("clearing a client option sends null while retaining other settings", () => {
  const values = formValues();
  values.selected = ["composition"];
  values.original_balancer = {
    clients: {
      clash: { probe_url: "https://example.com", tolerance: 0 },
    },
  };
  values.balancer_clients = {
    clash: { probe_url: undefined, tolerance: 0 },
  };
  const payload = toHostPayload(hostFormSchema.parse(values));
  const settings = payload.balancer_settings as {
    clients: Record<string, unknown>;
  };
  assert.deepEqual(settings.clients, { clash: { probe_url: null } });
});

test("removing a client deletes its saved settings", () => {
  const values = formValues();
  values.selected = ["composition"];
  values.original_balancer = { clients: { clash: { lazy: false } } };
  const settings = toHostPayload(hostFormSchema.parse(values))
    .balancer_settings as { clients: Record<string, unknown> };
  assert.deepEqual(settings.clients, { clash: null });
});

test("invalid JSON arrays report their actual form path", () => {
  const values = formValues();
  values.balancer_clients = {
    "v2ray-json": { strategy_settings: { costs: "[" } },
  };
  const result = hostFormSchema.safeParse(values);
  assert.equal(result.success, false);
  if (!result.success) {
    assert.deepEqual(result.error.issues[0].path, [
      "balancer_clients",
      "v2ray-json",
      "strategy_settings",
      "costs",
    ]);
  }
});

test("cost entries and numeric fields validate their ranges", () => {
  const values = formValues();
  values.balancer_clients = {
    "v2ray-json": { strategy_settings: { costs: '[{"host_id":1,"value":0}]' } },
  };
  assert.equal(hostFormSchema.safeParse(values).success, false);
  values.balancer_clients = { clash: { tolerance: -1 } };
  assert.equal(hostFormSchema.safeParse(values).success, false);
});

test("changing strategy removes inapplicable least-load settings", () => {
  assert.deepEqual(
    serializeBalancerClients(
      {
        "v2ray-json": {
          strategy: "round_robin",
          strategy_settings: { expected: 2, baselines_ms: "[100]" },
        },
      },
      "least_ping",
    ),
    { "v2ray-json": { strategy: "round_robin" } },
  );
});
