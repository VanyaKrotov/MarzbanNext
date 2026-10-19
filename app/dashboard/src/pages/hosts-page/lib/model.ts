import type {
  HostGroupRef,
  HostGroupType,
  HostPayload,
  HostType,
  HostsSchema,
} from "../types";

export type HostRow = HostType;

export const getDefaultHost = (): Omit<HostPayload, "inbound_tag"> => ({
  remark: "",
  address: "",
  port: null,
  path: "",
  sni: "",
  host: "",
  mux_enable: false,
  allowinsecure: false,
  is_disabled: false,
  fragment_setting: "",
  noise_setting: "",
  random_user_agent: false,
  security: "inbound_default",
  alpn: "",
  fingerprint: "",
  use_sni_as_host: false,
  sc_max_buffered_posts: null,
  x_padding_obfs_mode: null,
  uplink_http_method: null,
  group_ids: [],
  subscription_template_ids: {},
});

export function toHostPayload(
  values: {
    inboundTag: string;
  } & Omit<HostPayload, "inbound_tag">,
): HostPayload {
  return {
    inbound_tag: values.inboundTag,
    remark: values.remark,
    address: values.address,
    port: values.port,
    path: values.path,
    sni: values.sni,
    host: values.host,
    mux_enable: values.mux_enable,
    allowinsecure: values.allowinsecure,
    is_disabled: values.is_disabled,
    fragment_setting: values.fragment_setting,
    noise_setting: values.noise_setting,
    random_user_agent: values.random_user_agent,
    security: values.security,
    alpn: values.alpn,
    fingerprint: values.fingerprint,
    use_sni_as_host: values.use_sni_as_host,
    sc_max_buffered_posts: values.sc_max_buffered_posts,
    x_padding_obfs_mode: values.x_padding_obfs_mode ? true : null,
    uplink_http_method: values.uplink_http_method || null,
    group_ids: values.group_ids,
    subscription_template_ids: { ...values.subscription_template_ids },
  };
}

export function toHostGroupRefs(
  groupIds: string[],
  hostGroups: HostGroupType[],
): HostGroupRef[] {
  const groupsById = new Map(hostGroups.map((group) => [group.id, group]));
  return groupIds.flatMap((groupId) => {
    const group = groupsById.get(groupId);
    return group ? [{ id: group.id, name: group.name, tags: group.tags }] : [];
  });
}

export function updateHost(
  hosts: HostsSchema,
  hostId: number,
  payload: HostPayload,
  hostGroups: HostGroupType[] = [],
): HostsSchema {
  return hosts.map((host) =>
    host.id === hostId
      ? {
          ...host,
          ...payload,
          inbound_tag: payload.inbound_tag,
          position: payload.position ?? host.position,
          groups: toHostGroupRefs(payload.group_ids, hostGroups),
        }
      : host,
  );
}

export function removeHost(hosts: HostsSchema, hostId: number): HostsSchema {
  return hosts.filter((host) => host.id !== hostId);
}

export function reorderHost(
  hosts: HostsSchema,
  fromIndex: number,
  toIndex: number,
): HostsSchema {
  if (fromIndex === toIndex) return hosts;

  const next = cloneHosts(hosts);
  const [host] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, host);
  return next.map((host, position) => ({ ...host, position }));
}

export function cloneHosts(hosts: HostsSchema): HostsSchema {
  return hosts.map((host) => ({
    ...host,
    groups: host.groups.map((group) => ({ ...group })),
    subscription_template_ids: { ...host.subscription_template_ids },
  }));
}
