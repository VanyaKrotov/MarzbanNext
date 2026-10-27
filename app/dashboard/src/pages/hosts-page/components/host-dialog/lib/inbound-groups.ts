import type { InboundNodeRef, InboundType } from "@/types/Inbound";

type InboundGroup = {
  key: string;
  nodes: InboundNodeRef[];
  inbounds: InboundType[];
};

export function groupInboundsByNodes(inbounds: InboundType[]): InboundGroup[] {
  const groups = new Map<string, InboundGroup>();

  for (const inbound of inbounds) {
    const nodes = [...inbound.nodes].sort((a, b) => a.id - b.id);
    const key = nodes.map((node) => node.id).join(",");
    const group = groups.get(key);
    if (group) {
      group.inbounds.push(inbound);
    } else {
      groups.set(key, { key, nodes, inbounds: [inbound] });
    }
  }

  return [...groups.values()];
}
