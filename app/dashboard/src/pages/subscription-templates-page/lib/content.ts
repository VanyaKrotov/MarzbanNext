import type { SubscriptionFormat } from "./query";

export const initialTemplateContent: Record<SubscriptionFormat, string> = {
  v2ray: "{{ links | join('\\n') }}",
  "v2ray-json": '{\n  "outbounds": []\n}',
  clash: "{{ conf | yaml }}\n",
  "sing-box": '{\n  "outbounds": []\n}',
  outline: "{{ config | tojson }}",
};
