import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/service/http";

export type RuntimeSettings = {
  sub_profile_title: string;
  sub_support_url: string;
  sub_update_interval: string;
  external_config: string;
  use_custom_json_default: boolean;
  use_custom_json_for_v2rayn: boolean;
  use_custom_json_for_v2rayng: boolean;
  use_custom_json_for_streisand: boolean;
  use_custom_json_for_happ: boolean;
  active_status_text: string;
  expired_status_text: string;
  limited_status_text: string;
  disabled_status_text: string;
  onhold_status_text: string;
  notify_status_change: boolean;
  notify_user_created: boolean;
  notify_user_updated: boolean;
  notify_user_deleted: boolean;
  notify_user_data_used_reset: boolean;
  notify_user_sub_revoked: boolean;
  notify_if_data_usage_percent_reached: boolean;
  notify_if_days_left_reached: boolean;
  notify_login: boolean;
  notify_days_left: number[];
  notify_reached_usage_percent: number[];
  login_notify_white_list: string[];
  webhook_addresses: string[];
  webhook_secret_set: boolean;
  recurrent_notifications_timeout: number;
  number_of_recurrent_notifications: number;
  default_node_config: Record<string, unknown>;
  clash_settings: string;
  singbox_settings: string;
  v2ray_settings: string;
  mux: string;
  user_agent: string;
  grpc_user_agent: string;
};

export type RuntimeSettingsUpdate = Partial<
  Omit<RuntimeSettings, "webhook_secret_set">
> & {
  webhook_secret?: string;
  clear_webhook_secret?: boolean;
};

export const runtimeSettingsQueryKey = ["runtime-settings"] as const;

export function useRuntimeSettingsQuery() {
  return useQuery({
    queryKey: runtimeSettingsQueryKey,
    queryFn: () => api.get<RuntimeSettings>("/settings"),
  });
}

export function useUpdateRuntimeSettingsMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (settings: RuntimeSettingsUpdate) =>
      api.patch<RuntimeSettings>("/settings", settings),
    onSuccess: (settings) => {
      queryClient.setQueryData(runtimeSettingsQueryKey, settings);
    },
  });
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function timestamp() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "");
}

export async function downloadFullBackup() {
  const blob = await api.get<Blob>("/settings/backups/full", {
    responseType: "blob",
  });
  downloadBlob(blob, `marzbannext_full_backup_${timestamp()}.zip`);
}

export async function downloadDatabaseBackup() {
  const blob = await api.get<Blob>("/settings/backups/database", {
    responseType: "blob",
  });
  downloadBlob(blob, `marzbannext_database_${timestamp()}.sql`);
}

export function useRestoreFullBackupMutation() {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.post("/settings/backups/full", formData);
    },
  });
}

export function useRestoreDatabaseBackupMutation() {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.post("/settings/backups/database", formData);
    },
  });
}
