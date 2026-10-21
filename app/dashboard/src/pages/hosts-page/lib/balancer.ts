import { z } from "zod";

export const balancerStrategies = [
  "least_ping",
  "least_load",
  "random",
  "round_robin",
] as const;
export const balancerTargets = ["v2ray-json", "clash", "sing-box"] as const;
export type BalancerTarget = (typeof balancerTargets)[number];

const baselinesSchema = z.array(z.number().int().positive());
const costsSchema = z.array(
  z.object({
    host_id: z.number().int().positive(),
    value: z.number().finite().positive(),
  }),
);
const leastLoadSchema = z.object({
  expected: z.number().int().positive().optional(),
  max_rtt_ms: z.number().int().positive().optional(),
  failure_tolerance: z.number().min(0).max(1).optional(),
  baselines_ms: baselinesSchema.optional(),
  costs: costsSchema.optional(),
});

export const balancerClientSchema = z.object({
  strategy: z.enum(balancerStrategies).optional(),
  probe_url: z.string().optional(),
  probe_interval: z.number().int().min(10).max(86400).optional(),
  enable_concurrency: z.boolean().optional(),
  strategy_settings: leastLoadSchema.optional(),
  tolerance: z.number().int().nonnegative().optional(),
  lazy: z.boolean().optional(),
  idle_timeout: z.number().int().positive().optional(),
  interrupt_existing_connections: z.boolean().optional(),
});

export type BalancerClient = z.infer<typeof balancerClientSchema>;
export type BalancerSettings = {
  remark?: string | null;
  strategy: (typeof balancerStrategies)[number];
  probe_url: string;
  probe_interval: number;
  clients: Partial<Record<BalancerTarget, BalancerClient>>;
};

function optionalJsonArray<T>(schema: z.ZodType<T[]>) {
  return z
    .string()
    .superRefine((text, context) => {
      if (!text.trim()) return;
      try {
        const result = schema.safeParse(JSON.parse(text));
        if (result.success) return;
      } catch {
        /* The same field error covers syntax and invalid array entries. */
      }
      context.addIssue({
        code: z.ZodIssueCode.custom,
        params: { translationKey: "hostEditor.invalidJsonArray" },
      });
    })
    .optional();
}

export const balancerClientFormSchema = balancerClientSchema.extend({
  probe_url: z
    .union([
      z.literal(""),
      z
        .string()
        .url()
        .regex(/^https?:\/\//),
    ])
    .optional(),
  strategy_settings: leastLoadSchema
    .extend({
      baselines_ms: optionalJsonArray(baselinesSchema),
      costs: optionalJsonArray(costsSchema),
    })
    .optional(),
});

export type BalancerClientFormValues = z.infer<typeof balancerClientFormSchema>;
export type BalancerClientsFormValues = Partial<
  Record<BalancerTarget, BalancerClientFormValues>
>;

export function getBalancerClientFormValues(
  clients: BalancerSettings["clients"],
): BalancerClientsFormValues {
  return Object.fromEntries(
    Object.entries(clients).map(([target, options]) => {
      const settings = options.strategy_settings;
      return [
        target,
        {
          ...options,
          strategy_settings: settings && {
            ...settings,
            baselines_ms:
              settings.baselines_ms === undefined
                ? undefined
                : JSON.stringify(settings.baselines_ms, null, 2),
            costs:
              settings.costs === undefined
                ? undefined
                : JSON.stringify(settings.costs, null, 2),
          },
        },
      ];
    }),
  );
}

function parseOptionalArray<T>(
  schema: z.ZodType<T[]>,
  text?: string,
): T[] | undefined {
  return text?.trim() ? schema.parse(JSON.parse(text)) : undefined;
}

function omitUndefined<T extends object>(value: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined),
  ) as Partial<T>;
}

export function serializeBalancerClients(
  clients: BalancerClientsFormValues,
  strategy: BalancerSettings["strategy"],
): BalancerSettings["clients"] {
  return Object.fromEntries(
    Object.entries(clients).map(([target, options]) => {
      const settings =
        (options.strategy ?? strategy) === "least_load"
          ? options.strategy_settings
          : undefined;
      const strategySettings =
        settings &&
        omitUndefined({
          ...settings,
          baselines_ms: parseOptionalArray(
            baselinesSchema,
            settings.baselines_ms,
          ),
          costs: parseOptionalArray(costsSchema, settings.costs),
        });
      return [
        target,
        omitUndefined({
          ...options,
          probe_url: options.probe_url || undefined,
          strategy_settings:
            strategySettings && Object.keys(strategySettings).length
              ? strategySettings
              : undefined,
        }),
      ];
    }),
  );
}
