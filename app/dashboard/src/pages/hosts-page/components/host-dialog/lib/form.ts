import { z } from "zod";
import {
  subscriptionFormats,
  type TemplateBindings,
} from "@/pages/subscription-templates-page/lib/query";

import type { HostType } from "../../../types";

export const hostFormSchema = z.object({
  inboundTag: z.string().min(1),
  remark: z.string().min(1),
  address: z.string().min(1),
  port: z.number().nullable(),
  path: z.string().nullable(),
  sni: z.string().nullable(),
  host: z.string().nullable(),
  mux_enable: z.boolean(),
  allowinsecure: z.boolean().nullable(),
  is_disabled: z.boolean(),
  fragment_setting: z.string().nullable(),
  noise_setting: z.string().nullable(),
  random_user_agent: z.boolean(),
  security: z.string(),
  alpn: z.string(),
  fingerprint: z.string(),
  use_sni_as_host: z.boolean(),
  sc_max_buffered_posts: z.number().int().nonnegative().nullable(),
  x_padding_obfs_mode: z.boolean().nullable(),
  uplink_http_method: z
    .string()
    .trim()
    .regex(/^[!#$%&'*+.^_`|~0-9A-Za-z-]*$/)
    .transform((value) => value.toUpperCase())
    .nullable(),
  group_ids: z.array(z.string()),
  subscription_template_ids: z.record(
    z.enum(subscriptionFormats),
    z.number().int().positive(),
  ),
});

export type HostFormValues = z.infer<typeof hostFormSchema>;

export function getHostFormValues(
  inboundTag: string,
  host?: HostType | null,
  templateBindings: TemplateBindings = {},
): HostFormValues {
  return {
    inboundTag,
    ...(host
      ? {
          ...host,
          x_padding_obfs_mode: host.x_padding_obfs_mode || null,
          group_ids: host.groups.map((group) => group.id),
        }
      : {
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
          subscription_template_ids: templateBindings,
        }),
  };
}
