import { z } from "zod";
import type { UseFormReturn } from "react-hook-form";

import type { InboundsMap } from "types/Inbound";
import {
  ProxyType,
  User,
  UserCreate,
  UserInbounds,
} from "types/User";

export type UserFormValues = Pick<UserCreate, keyof UserCreate>;

export const formatUserFormValues = (user: User): UserFormValues => ({
  ...user,
  data_limit: user.data_limit
    ? Number((user.data_limit / 1073741824).toFixed(5))
    : user.data_limit,
  on_hold_expire_duration: user.on_hold_expire_duration
    ? Number(user.on_hold_expire_duration / (24 * 60 * 60))
    : user.on_hold_expire_duration,
});

export const getDefaultUserFormValues = (
  availableInbounds: InboundsMap = new Map(),
): UserFormValues => {
  const inbounds: UserInbounds = {};

  for (const [protocol, protocolInbounds] of availableInbounds) {
    inbounds[protocol] = protocolInbounds.map((inbound) => inbound.tag);
  }

  return {
    data_limit: null,
    expire: null,
    username: "",
    data_limit_reset_strategy: "no_reset",
    status: "active",
    on_hold_expire_duration: null,
    note: "",
    inbounds,
    proxies: {
      vless: { id: "", flow: "" },
      vmess: { id: "" },
      trojan: { password: "" },
      shadowsocks: { password: "", method: "chacha20-ietf-poly1305" },
      hysteria: { auth: "" },
    },
  };
};

const mergeProxies = (
  proxyKeys: (keyof ProxyType)[],
  proxyType: ProxyType | undefined,
): ProxyType => {
  const proxies = proxyKeys.reduce<ProxyType>(
    (result, proxy) => ({ ...result, [proxy]: {} }),
    {},
  );

  if (!proxyType) return proxies;

  proxyKeys.forEach((proxy) => {
    if (proxyType[proxy]) proxies[proxy] = proxyType[proxy];
  });
  return proxies;
};

export const toUserPayload = (values: UserFormValues): UserCreate => {
  const selectedProxies = Object.entries(values.inbounds)
    .map(([protocol]) => protocol as keyof ProxyType);

  return {
    ...values,
    expire:
      values.expire === null ? null : Math.floor(Number(values.expire)),
    data_limit: values.data_limit,
    proxies: mergeProxies(selectedProxies, values.proxies),
    data_limit_reset_strategy:
      values.data_limit && values.data_limit > 0
        ? values.data_limit_reset_strategy
        : "no_reset",
    status: ["active", "disabled", "on_hold"].includes(values.status)
      ? (values.status as UserCreate["status"])
      : "active",
  };
};

const baseSchema = {
  username: z.string().min(1),
  note: z.string().nullable(),
  proxies: z
    .record(z.string(), z.record(z.string(), z.any()))
    .transform((value) => {
      const removeEmpty = (
        object: Record<string, unknown> | undefined,
        key: string,
      ) => {
        if (object?.[key] === "") delete object[key];
      };

      removeEmpty(value.vmess, "id");
      removeEmpty(value.vless, "id");
      removeEmpty(value.trojan, "password");
      removeEmpty(value.shadowsocks, "password");
      removeEmpty(value.shadowsocks, "method");
      removeEmpty(value.hysteria, "auth");
      return value;
    }),
  data_limit: z
    .string()
    .min(0)
    .or(z.number())
    .nullable()
    .transform((value) =>
      value ? Number((parseFloat(String(value)) * 1073741824).toFixed(5)) : 0,
    ),
  expire: z.number().int().nonnegative().nullable(),
  data_limit_reset_strategy: z.string(),
  inbounds: z
    .record(z.string(), z.array(z.string()))
    .refine(
      (value) => Object.keys(value).length > 0,
      { message: "userDialog.selectOneProtocol" },
    ),
};

export const userFormSchema = z.discriminatedUnion("status", [
  z.object({ status: z.literal("active"), ...baseSchema }),
  z.object({ status: z.literal("disabled"), ...baseSchema }),
  z.object({ status: z.literal("limited"), ...baseSchema }),
  z.object({ status: z.literal("expired"), ...baseSchema }),
  z.object({
    status: z.literal("on_hold"),
    on_hold_expire_duration: z.coerce
      .number()
      .min(0.1)
      .transform((days) => days * 24 * 60 * 60),
    ...baseSchema,
  }),
]);

export const generateUsername = () => {
  const characters =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  return Array.from({ length: 6 }, () =>
    characters.charAt(Math.floor(Math.random() * characters.length)),
  ).join("");
};

export const applyUserFormServerErrors = (
  error: any,
  form: UseFormReturn<UserFormValues>,
) => {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") return detail;
  if (error?.response?.status !== 422 || !detail || typeof detail !== "object") {
    return null;
  }

  Object.keys(detail).forEach((key) => {
    form.setError(key as keyof UserFormValues, {
      type: "server",
      message: detail[key],
    });
  });

  return String(Object.values(detail)[0] ?? "");
};
