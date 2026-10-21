import type { BalancerSettings } from "./lib/balancer";
import type { TemplateBindings } from "@/pages/subscription-templates-page/lib/formats";

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

export type JsonObject = Record<string, unknown>;

export type HostType = {
  id: number;
  inbound_id: number;
  inbound_tag: string;
  inbound_port: number | string | null;
  position: number;
  remark: string;
  address: string;
  port: number | null;
  enabled: boolean;
  show_when_composed: boolean;
  overrides: JsonObject;
  balancer_settings: BalancerSettings | null;
  linked_host_ids: number[];
  member_of: { id: number; remark: string }[];
  groups: HostGroupRef[];
  subscription_template_ids: TemplateBindings;
  created_at: string;
  updated_at: string;
};

export type HostPayload = {
  inbound_id: number;
  remark: string;
  address: string;
  port: number | null;
  enabled: boolean;
  show_when_composed: boolean;
  overrides?: JsonObject | null;
  balancer_settings?: JsonObject | null;
  linked_host_ids?: number[];
  group_ids?: string[];
  subscription_template_ids?: TemplateBindings;
};

export type HostsSchema = HostType[];
export type HostCapabilities = {
  schema_version: number;
  strategies: Record<string, string[]>;
};
