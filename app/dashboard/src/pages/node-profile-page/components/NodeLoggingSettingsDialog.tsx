import { FileCog } from "lucide-react";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useUpdateNodeMutation } from "@/pages/nodes-page/lib/query";
import type { NodeType } from "types/Node";
import {
  generateErrorMessage,
  generateSuccessMessage,
} from "utils/toastHandler";

const loggingSettingsSchema = z.object({
  access_log_enabled: z.boolean(),
  error_log_enabled: z.boolean(),
  log_retention_days: z.number().int().positive(),
  log_storage_limit_bytes: z.number().int().positive().nullable(),
});

type LoggingSettings = z.infer<typeof loggingSettingsSchema>;

type NodeLoggingSettingsDialogProps = {
  node: NodeType;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function NodeLoggingSettingsDialog({
  node,
  open,
  onOpenChange,
}: NodeLoggingSettingsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <NodeLoggingSettingsDialogContent node={node} onOpenChange={onOpenChange} />
      </DialogContent>
    </Dialog>
  );
}

function NodeLoggingSettingsDialogContent({
  node,
  onOpenChange,
}: Pick<NodeLoggingSettingsDialogProps, "node" | "onOpenChange">) {
  const { t } = useTranslation();
  const update = useUpdateNodeMutation();
  const form = useForm<LoggingSettings>({
    resolver: zodResolver(loggingSettingsSchema),
    defaultValues: getLoggingSettings(node),
  });

  useEffect(() => {
    form.reset(getLoggingSettings(node));
  }, [form, node]);

  const submit = (settings: LoggingSettings) => {
    update.mutate(
      { ...node, ...settings },
      {
        onSuccess: () => {
          generateSuccessMessage(t("nodeLoggingSettings.saveSuccess", { name: node.name }));
          onOpenChange(false);
        },
        onError: (error) => generateErrorMessage(error),
      },
    );
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <FileCog className="size-5 text-primary" />
          {t("nodeLoggingSettings.title")}
        </DialogTitle>
        <DialogDescription>{node.name}</DialogDescription>
      </DialogHeader>

      <form className="space-y-4" onSubmit={form.handleSubmit(submit)}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Controller
            name="access_log_enabled"
            control={form.control}
            render={({ field }) => (
              <Field orientation="horizontal">
                <Switch
                  id="node-access-log"
                  checked={field.value}
                  disabled={update.isPending}
                  onCheckedChange={field.onChange}
                />
                <FieldLabel htmlFor="node-access-log">{t("nodes.accessLog")}</FieldLabel>
              </Field>
            )}
          />
          <Controller
            name="error_log_enabled"
            control={form.control}
            render={({ field }) => (
              <Field orientation="horizontal">
                <Switch
                  id="node-error-log"
                  checked={field.value}
                  disabled={update.isPending}
                  onCheckedChange={field.onChange}
                />
                <FieldLabel htmlFor="node-error-log">{t("nodes.errorLog")}</FieldLabel>
              </Field>
            )}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field data-invalid={Boolean(form.formState.errors.log_retention_days)}>
            <FieldLabel htmlFor="node-log-retention-days">
              {t("nodes.logRetentionDays")}
            </FieldLabel>
            <Input
              id="node-log-retention-days"
              type="number"
              min="1"
              step="1"
              disabled={update.isPending}
              {...form.register("log_retention_days", { valueAsNumber: true })}
            />
            <FieldError errors={[form.formState.errors.log_retention_days]} />
          </Field>
          <Field data-invalid={Boolean(form.formState.errors.log_storage_limit_bytes)}>
            <FieldLabel htmlFor="node-log-storage-limit">
              {t("nodes.logStorageLimit")}
            </FieldLabel>
            <Input
              id="node-log-storage-limit"
              type="number"
              min="1"
              step="1"
              disabled={update.isPending}
              value={
                form.watch("log_storage_limit_bytes")
                  ? Math.round((form.watch("log_storage_limit_bytes") ?? 0) / 1024 / 1024)
                  : ""
              }
              onChange={(event) =>
                form.setValue(
                  "log_storage_limit_bytes",
                  event.target.valueAsNumber > 0
                    ? event.target.valueAsNumber * 1024 * 1024
                    : null,
                  { shouldValidate: true },
                )
              }
            />
            <FieldError errors={[form.formState.errors.log_storage_limit_bytes]} />
          </Field>
        </div>

        <Button className="w-full" type="submit" disabled={update.isPending}>
          {t("settingsPage.save")}
        </Button>
      </form>
    </>
  );
}

function getLoggingSettings(node: NodeType): LoggingSettings {
  return {
    access_log_enabled: node.access_log_enabled ?? false,
    error_log_enabled: node.error_log_enabled ?? false,
    log_retention_days: node.log_retention_days ?? 14,
    log_storage_limit_bytes: node.log_storage_limit_bytes ?? null,
  };
}
