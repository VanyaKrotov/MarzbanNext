import assert from "node:assert/strict";
import { test } from "node:test";

import { groupInboundsByNodes } from "../src/pages/hosts-page/components/host-dialog/lib/inbound-groups";
import type { InboundNodeRef, InboundType } from "../src/types/Inbound";

function inbound(id: number, nodes: InboundNodeRef[]): InboundType {
  return {
    id,
    tag: `inbound-${id}`,
    protocol: "vless",
    network: "tcp",
    tls: "tls",
    nodes,
  };
}

test("groups by node identity, keeping shared and unassigned inbounds selectable once", () => {
  const first = { id: 1, name: "Node" };
  const second = { id: 2, name: "Node" };
  const inbounds = [
    inbound(1, [first]),
    inbound(2, [second]),
    inbound(3, [second, first]),
    inbound(4, []),
    inbound(5, [first]),
    inbound(6, [first, second]),
    inbound(7, []),
  ];
  const snapshot = structuredClone(inbounds);
  const groups = groupInboundsByNodes(inbounds);

  assert.deepEqual(
    groups.map((group) => group.inbounds.map((item) => item.id)),
    [[1, 5], [2], [3, 6], [4, 7]],
  );
  assert.deepEqual(groups[2].nodes, [first, second]);
  assert.deepEqual(groups[3].nodes, []);
  assert.equal(new Set(groups.map((group) => group.key)).size, groups.length);
  assert.deepEqual(inbounds, snapshot);
  assert.deepEqual(groupInboundsByNodes([]), []);
});
