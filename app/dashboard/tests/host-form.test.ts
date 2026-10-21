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

test("clash-meta is the only YAML format in the catalog", () => {
  assert.deepEqual(subscriptionFormats, [
    "v2ray",
    "v2ray-json",
    "clash-meta",
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

test("structured client settings preserve zero, false and least-load arrays", () => {
  const clients = getBalancerClientFormValues({
    "clash-meta": { tolerance: 0, lazy: false },
    "v2ray-json": {
      strategy: "least_load",
      strategy_settings: {
        failure_tolerance: 0,
        baselines_ms: [100, 200],
        costs: [{ host_id: 1, value: 2 }],
      },
    },
  });
  assert.equal(clients["clash-meta"]?.lazy, false);
  assert.deepEqual(serializeBalancerClients(clients, "least_ping"), {
    "clash-meta": { tolerance: 0, lazy: false },
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
      "clash-meta": { probe_url: "https://example.com", tolerance: 0 },
    },
  };
  values.balancer_clients = {
    "clash-meta": { probe_url: undefined, tolerance: 0 },
  };
  const payload = toHostPayload(hostFormSchema.parse(values));
  const settings = payload.balancer_settings as {
    clients: Record<string, unknown>;
  };
  assert.deepEqual(settings.clients, { "clash-meta": { probe_url: null } });
});

test("removing a client deletes its saved settings", () => {
  const values = formValues();
  values.selected = ["composition"];
  values.original_balancer = { clients: { "clash-meta": { lazy: false } } };
  const settings = toHostPayload(hostFormSchema.parse(values))
    .balancer_settings as { clients: Record<string, unknown> };
  assert.deepEqual(settings.clients, { "clash-meta": null });
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
  values.balancer_clients = { "clash-meta": { tolerance: -1 } };
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
