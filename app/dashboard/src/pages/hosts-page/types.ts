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
  is_hidden: boolean;
  overrides: JsonObject;
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
  is_hidden: boolean;
  overrides?: JsonObject | null;
  group_ids?: string[];
  subscription_template_ids?: TemplateBindings;
};

export type HostsSchema = HostType[];
