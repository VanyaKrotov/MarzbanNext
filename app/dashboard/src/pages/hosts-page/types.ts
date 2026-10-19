import type { TemplateBindings } from "@/pages/subscription-templates-page/lib/query";

export type HostGroupRef = {
  id: string;
  name: string;
  tags: string[];
};

export type HostGroupType = HostGroupRef & {
  description: string | null;
  created_at: string;
};

export type HostGroupPayload = {
  id: string;
  name: string;
  description: string | null;
  tags: string[];
};

export type HostGroupUpdatePayload = Omit<HostGroupPayload, "id">;

export type HostType = {
  id: number;
  inbound_id: number;
  inbound_tag: string;
  position: number;
  remark: string;
  address: string;
  port: number | null;
  path: string | null;
  sni: string | null;
  host: string | null;
  mux_enable: boolean;
  allowinsecure: boolean | null;
  is_disabled: boolean;
  fragment_setting: string | null;
  noise_setting: string | null;
  random_user_agent: boolean;
  security: string;
  alpn: string;
  fingerprint: string;
  use_sni_as_host: boolean;
  sc_max_buffered_posts: number | null;
  x_padding_obfs_mode: boolean | null;
  uplink_http_method: string | null;
  groups: HostGroupRef[];
  subscription_template_ids: TemplateBindings;
};

export type HostPayload = Omit<
  HostType,
  "id" | "inbound_id" | "inbound_tag" | "position" | "groups"
> & {
  inbound_tag: string;
  position?: number | null;
  group_ids: string[];
};

export type HostsSchema = HostType[];
