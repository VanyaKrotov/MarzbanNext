import type { HostType, HostsSchema } from "../types";
export type HostRow = HostType;
export const removeHost = (hosts: HostsSchema, id: number) =>
  hosts.filter((host) => host.id !== id);
export function reorderHost(
  hosts: HostsSchema,
  from: number,
  to: number,
): HostsSchema {
  const next = [...hosts];
  const [host] = next.splice(from, 1);
  next.splice(to, 0, host);
  return next.map((item, position) => ({ ...item, position }));
}
