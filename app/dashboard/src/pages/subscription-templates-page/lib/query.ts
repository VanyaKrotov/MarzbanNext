import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/service/http";
import { fetchAllPages } from "@/service/pagination";
import type { MonacoJsonSchema } from "@/components/MonacoJsonEditor";

import type { SubscriptionFormat, TemplateBindings } from "./formats";
export { subscriptionFormats, formatLabelKeys } from "./formats";
export type { SubscriptionFormat, TemplateBindings } from "./formats";

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
export type TemplateCapabilities = Partial<
  Record<SubscriptionFormat, MonacoJsonSchema>
>;

export const subscriptionTemplatesQueryKey = [
  "subscription-templates",
] as const;

export function useTemplatesQuery(
  format = "",
  search = "",
  offset = 0,
  limit = 50,
) {
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
    queryFn: ({ signal }) =>
      fetchAllPages((offset) =>
        api.get<TemplateList>("/subscription-templates", {
          signal,
          params: { offset, limit: 1000 },
        }),
      ),
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

export function useTemplateCapabilitiesQuery(enabled: boolean) {
  return useQuery({
    queryKey: [...subscriptionTemplatesQueryKey, "capabilities"],
    queryFn: ({ signal }) =>
      api.get<TemplateCapabilities>("/subscription-templates/capabilities", {
        signal,
      }),
    enabled,
    staleTime: Infinity,
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
