import assert from "node:assert/strict";
import { test } from "node:test";
import { compositionExample } from "../src/pages/subscription-templates-page/lib/composition";

test("Xray example selects numeric source IDs and uses native observatory routing", () => {
  const document = JSON.parse(
    compositionExample("v2ray-json", { type: "ids", values: [12, 11] }),
  );
  assert.deepEqual(document.marzban.injectHosts[0].selector.values, [12, 11]);
  assert.equal(
    document.routing.rules[0].balancerTag,
    document.routing.balancers[0].tag,
  );
  assert.deepEqual(
    document.observatory.subjectSelector,
    document.routing.balancers[0].selector,
  );
  assert.equal("remnawave" in document, false);
});

test("sing-box example keeps an explicit native selector and puts source selection on urltest", () => {
  const document = JSON.parse(
    compositionExample("sing-box", { type: "groups", values: ["eu", 'a"b'] }),
  );
  assert.deepEqual(document.outbounds[0].outbounds, [
    document.outbounds[1].tag,
  ]);
  assert.deepEqual(document.outbounds[1].marzban.selector, {
    type: "groups",
    values: ["eu", 'a"b'],
  });
  assert.equal(document.outbounds[1].marzban.includeProxies, true);
});

test("Clash example quotes group IDs and uses the canonical hyphenated directive", () => {
  const content = compositionExample("clash", {
    type: "groups",
    values: ["eu", 'a"b'],
  });
  assert.ok(content.includes('values: ["eu","a\\"b"]'));
  assert.ok(content.includes("include-proxies: true"));
  assert.ok(content.includes("include-proxies: false"));
  assert.equal(content.includes("includeProxies"), false);
});

test("link and Outline formats cannot create balancing examples", () => {
  for (const format of ["v2ray", "outline"] as const) {
    assert.throws(() =>
      compositionExample(format, { type: "ids", values: [1] }),
    );
  }
});
