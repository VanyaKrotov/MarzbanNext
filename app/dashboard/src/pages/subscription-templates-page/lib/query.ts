import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/service/http";

export const subscriptionFormats = [
  "v2ray",
  "v2ray-json",
  "clash",
  "sing-box",
  "outline",
] as const;
export type SubscriptionFormat = (typeof subscriptionFormats)[number];
export type TemplateBindings = Partial<Record<SubscriptionFormat, number>>;

export const formatLabelKeys: Record<SubscriptionFormat, string> = {
  v2ray: "subscriptionTemplates.formats.v2ray",
  "v2ray-json": "subscriptionTemplates.formats.v2ray-json",
  clash: "subscriptionTemplates.formats.clash",
  "sing-box": "subscriptionTemplates.formats.sing-box",
  outline: "subscriptionTemplates.formats.outline",
};

export type SubscriptionTemplate = {
  id: number;
  name: string;
  format: SubscriptionFormat;
  is_default: boolean;
  created_at: string;
  updated_at: string;
};
export type TemplateDocument = SubscriptionTemplate & { content: string };
type TemplateList = { items: SubscriptionTemplate[]; total: number };

export const subscriptionTemplatesQueryKey = [
  "subscription-templates",
] as const;

export function useTemplatesQuery(format = "", search = "", offset = 0, limit = 50) {
  return useQuery({
    queryKey: [
      ...subscriptionTemplatesQueryKey,
      "list",
      format,
      search,
      offset,
      limit,
    ],
    queryFn: ({ signal }) =>
      api.get<TemplateList>("/subscription-templates", {
        signal,
        params: {
          format: format || undefined,
          search: search || undefined,
          offset,
          limit,
        },
      }),
  });
}

export function useAllTemplatesQuery() {
  return useQuery({
    queryKey: [...subscriptionTemplatesQueryKey, "all"],
    refetchOnMount: "always",
    queryFn: async ({ signal }) => {
      const items: SubscriptionTemplate[] = [];
      let total = 1;
      while (items.length < total) {
        const page = await api.get<TemplateList>("/subscription-templates", {
          signal,
          params: { offset: items.length, limit: 1000 },
        });
        items.push(...page.items);
        total = page.total;
        if (!page.items.length) break;
      }
      return items;
    },
  });
}

export function useTemplateQuery(id?: number) {
  return useQuery({
    queryKey: [...subscriptionTemplatesQueryKey, "detail", id],
    queryFn: ({ signal }) =>
      api.get<TemplateDocument>(`/subscription-templates/${id}`, { signal }),
    enabled: id !== undefined,
    refetchOnMount: "always",
  });
}

export function useTemplateMutation<T>(
  mutationFn: (payload: T) => Promise<unknown>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: subscriptionTemplatesQueryKey }),
        client.invalidateQueries({ queryKey: ["hosts"] }),
        client.invalidateQueries({ queryKey: ["users"] }),
      ]),
  });
}

export function defaultBindings(
  templates: SubscriptionTemplate[],
): TemplateBindings {
  return Object.fromEntries(
    templates
      .filter((item) => item.is_default)
      .map((item) => [item.format, item.id]),
  );
}
