import { zodResolver } from "@hookform/resolvers/zod";
import { KeyRound, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  generateErrorMessage,
  generateSuccessMessage,
} from "@/utils/toastHandler";

import {
  toWebhookFormValues,
  toWebhookPayload,
  type WebhookSettingsForm,
  webhookSettingsFormSchema,
} from "../lib/form";
import type { RuntimeSettings } from "../lib/query";
import { useUpdateRuntimeSettingsMutation } from "../lib/query";
import {
  Section,
  SettingsActionItem,
  SettingsSaveButton,
  TextInput,
} from "./form-controls";

export function WebhookSettingsSection({
  settings,
}: {
  settings: RuntimeSettings;
}) {
  const { t } = useTranslation();
  const updateSettings = useUpdateRuntimeSettingsMutation();
  const [secretDialogOpen, setSecretDialogOpen] = useState(false);
  const [secretDraft, setSecretDraft] = useState("");
  const form = useForm<WebhookSettingsForm>({
    resolver: zodResolver(webhookSettingsFormSchema),
    mode: "onChange",
    defaultValues: toWebhookFormValues(settings),
  });
  const webhookAddresses = useFieldArray({
    control: form.control,
    name: "webhook_addresses",
  });

  useEffect(() => {
    form.reset(toWebhookFormValues(settings));
  }, [form, settings]);

  const saveSettings = form.handleSubmit((values) => {
    updateSettings.mutate(toWebhookPayload(values), {
      onSuccess: (nextSettings) => {
        form.reset(toWebhookFormValues(nextSettings));
        generateSuccessMessage(t("settingsPage.saved"));
      },
      onError: (error) => generateErrorMessage(error),
    });
  });

  const openSecretDialog = () => {
    setSecretDraft("");
    setSecretDialogOpen(true);
  };

  const saveSecretDraft = () => {
    const nextSecret = secretDraft.trim();
    updateSettings.mutate(
      nextSecret
        ? { webhook_secret: nextSecret }
        : { clear_webhook_secret: true },
      {
        onSuccess: () => {
          setSecretDraft("");
          setSecretDialogOpen(false);
          generateSuccessMessage(t("settingsPage.saved"));
        },
        onError: (error) => generateErrorMessage(error),
      },
    );
  };

  const closeSecretDialog = (open: boolean) => {
    setSecretDialogOpen(open);
    if (!open) {
      setSecretDraft("");
    }
  };

  return (
    <>
      <form onSubmit={saveSettings}>
        <Card>
          <CardHeader>
            <CardTitle>{t("settingsPage.tabs.webhook")}</CardTitle>
            <CardAction>
              <SettingsSaveButton
                isPending={updateSettings.isPending}
                isValid={form.formState.isValid}
                label={t("settingsPage.save")}
              />
            </CardAction>
          </CardHeader>
          <CardContent>
            <Section>
              <TextInput
                form={form}
                name="recurrent_notifications_timeout"
                label={t("settingsPage.fields.recurrentNotificationsTimeout")}
                type="number"
                inputMode="numeric"
              />
              <TextInput
                form={form}
                name="number_of_recurrent_notifications"
                label={t("settingsPage.fields.numberOfRecurrentNotifications")}
                type="number"
                inputMode="numeric"
              />
              <WebhookAddressInputs
                form={form}
                fields={webhookAddresses.fields}
                onAdd={() => webhookAddresses.append({ value: "" })}
                onRemove={(index) => webhookAddresses.remove(index)}
              />
              <SettingsActionItem
                title={t("settingsPage.fields.webhookSecret")}
                description={
                  settings.webhook_secret_set
                    ? t("settingsPage.webhookSecret.filled")
                    : t("settingsPage.webhookSecret.empty")
                }
              >
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={openSecretDialog}
                >
                  <KeyRound />
                  {t("settingsPage.change")}
                </Button>
              </SettingsActionItem>
            </Section>
          </CardContent>
        </Card>
      </form>

      <Dialog open={secretDialogOpen} onOpenChange={closeSecretDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {t("settingsPage.webhookSecret.dialogTitle")}
            </DialogTitle>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="webhook-secret-draft">
              {t("settingsPage.fields.webhookSecret")}
            </FieldLabel>
            <div className="flex gap-2">
              <Input
                id="webhook-secret-draft"
                value={secretDraft}
                onChange={(event) => setSecretDraft(event.target.value)}
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={t("settingsPage.webhookSecret.generate")}
                onClick={() => setSecretDraft(generateSecret())}
              >
                <Sparkles />
              </Button>
            </div>
          </Field>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={updateSettings.isPending}
              onClick={() => closeSecretDialog(false)}
            >
              {t("cancel")}
            </Button>
            <Button
              type="button"
              disabled={updateSettings.isPending}
              onClick={saveSecretDraft}
            >
              {t("settingsPage.webhookSecret.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function WebhookAddressInputs({
  form,
  fields,
  onAdd,
  onRemove,
}: {
  form: ReturnType<typeof useForm<WebhookSettingsForm>>;
  fields: Array<{ id: string }>;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  const { t } = useTranslation();

  return (
    <Field className="md:col-span-2 xl:col-span-3">
      <div className="flex items-center justify-between gap-3">
        <FieldLabel>{t("settingsPage.fields.webhookAddresses")}</FieldLabel>
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          <Plus />
          {t("actions.add")}
        </Button>
      </div>
      <div className="space-y-2">
        {fields.map((field, index) => {
          const error = form.formState.errors.webhook_addresses?.[index]?.value;

          return (
            <div key={field.id} className="flex items-start gap-2">
              <div className="min-w-0 flex-1">
                <Input
                  placeholder="https://example.com/webhook"
                  {...form.register(`webhook_addresses.${index}.value`)}
                />
                <FieldError errors={[error]} />
              </div>
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={t("delete")}
                onClick={() => onRemove(index)}
              >
                <Trash2 />
              </Button>
            </div>
          );
        })}
      </div>
    </Field>
  );
}

function generateSecret() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}
