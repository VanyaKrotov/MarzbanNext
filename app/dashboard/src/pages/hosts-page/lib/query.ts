import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useInboundsListQuery } from "hooks/useInboundsQuery";
import type {
  HostGroupType,
  HostGroupPayload,
  HostGroupUpdatePayload,
  HostPayload,
  HostType,
  HostsSchema,
} from "../types";
import { api } from "service/http";
import { fetchAllPages } from "@/service/pagination";
import type { HostOverridesSchema } from "../components/host-dialog/lib/json-parameters";

export const hostsQueryKey = ["hosts", "unified"] as const;
export const hostGroupsQueryKey = ["host-groups"] as const;

export function useHostCapabilitiesQuery() {
  return useQuery({
    queryKey: ["hosts", "capabilities"],
    queryFn: ({ signal }) =>
      api.get<{ overrides_schema: HostOverridesSchema }>(
        "/hosts/capabilities",
        { signal },
      ),
    staleTime: Infinity,
  });
}

export function useHostsQuery(groupIds: string[] = [], search = "") {
  return useQuery({
    queryKey: [...hostsQueryKey, groupIds, search],
    queryFn: ({ signal }) =>
      fetchAllPages((offset) =>
        api.get<{ items: HostsSchema; total: number }>("/hosts", {
          signal,
          params: {
            limit: 1000,
            offset,
            groups: groupIds.length ? groupIds.join(",") : undefined,
            search: search.trim() || undefined,
          },
        }),
      ),
  });
}

export function useHostGroupsQuery() {
  return useQuery({
    queryKey: hostGroupsQueryKey,
    queryFn: ({ signal }) =>
      api.get<HostGroupType[]>("/host-groups", { signal }),
  });
}

export function useCreateHostGroupMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (group: HostGroupPayload) =>
      api.post<HostGroupType>("/host-groups", group),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: hostGroupsQueryKey }),
  });
}

export function useUpdateHostGroupMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      group,
    }: {
      id: string;
      group: HostGroupUpdatePayload;
    }) => api.put<HostGroupType>(`/host-groups/${id}`, group),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: hostsQueryKey }),
        queryClient.invalidateQueries({ queryKey: hostGroupsQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["users"] }),
      ]),
  });
}

export function useDeleteHostGroupMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/host-groups/${id}`),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: hostsQueryKey }),
        queryClient.invalidateQueries({ queryKey: hostGroupsQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["users"] }),
      ]),
  });
}

function useHostsMutation<TData, TVariables>(
  mutationFn: (variables: TVariables) => Promise<TData>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: hostsQueryKey }),
        queryClient.invalidateQueries({ queryKey: hostGroupsQueryKey }),
        queryClient.invalidateQueries({ queryKey: ["users"] }),
      ]),
  });
}

export function useCreateHostMutation() {
  return useHostsMutation((host: HostPayload) =>
    api.post<HostType>("/hosts", host),
  );
}

export function useCloneHostMutation() {
  return useHostsMutation(({ id, remark }: { id: number; remark: string }) =>
    api.post<HostType>(`/hosts/${id}/clone`, { remark }),
  );
}

export function useUpdateHostMutation() {
  return useHostsMutation(
    ({ id, host }: { id: number; host: Partial<HostPayload> }) =>
      api.patch<HostType>(`/hosts/${id}`, host),
  );
}

export function useDeleteHostMutation() {
  return useHostsMutation((id: number) => api.delete(`/hosts/${id}`));
}

export function useReorderHostsMutation() {
  return useHostsMutation((hostIds: number[]) =>
    api.post<HostsSchema>("/hosts/reorder", { host_ids: hostIds }),
  );
}

export function useInboundsQuery(includeTag?: string) {
  return useInboundsListQuery({ assignedOnly: true, includeTag });
}
