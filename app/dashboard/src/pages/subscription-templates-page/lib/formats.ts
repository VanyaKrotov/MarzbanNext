export const subscriptionFormats = [
  "v2ray",
  "v2ray-json",
  "clash-meta",
  "sing-box",
  "outline",
] as const;

export type SubscriptionFormat = (typeof subscriptionFormats)[number];
export type TemplateBindings = Partial<Record<SubscriptionFormat, number>>;

export const formatLabelKeys: Record<SubscriptionFormat, string> = {
  v2ray: "subscriptionTemplates.formats.v2ray",
  "v2ray-json": "subscriptionTemplates.formats.v2ray-json",
  "clash-meta": "subscriptionTemplates.formats.clash-meta",
  "sing-box": "subscriptionTemplates.formats.sing-box",
  outline: "subscriptionTemplates.formats.outline",
};
