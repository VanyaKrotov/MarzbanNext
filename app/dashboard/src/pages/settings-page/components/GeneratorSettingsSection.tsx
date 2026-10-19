import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { MonacoJsonEditor } from "@/components/MonacoJsonEditor";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  generateErrorMessage,
  generateSuccessMessage,
} from "@/utils/toastHandler";

import {
  useUpdateRuntimeSettingsMutation,
  type RuntimeSettings,
} from "../lib/query";

const generatorKeys = [
  "clash_settings",
  "singbox_settings",
  "v2ray_settings",
  "mux",
  "user_agent",
  "grpc_user_agent",
] as const;
type GeneratorKey = (typeof generatorKeys)[number];

export function GeneratorSettingsSection({
  settings,
}: {
  settings: RuntimeSettings;
}) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("subscriptionTemplates.generatorSettings")}</CardTitle>
        <CardDescription>
          {t("subscriptionTemplates.generatorDescription")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Accordion type="multiple" className="rounded-md border">
          {generatorKeys.map((field) => (
            <AccordionItem key={field} value={field} className="px-3">
              <AccordionTrigger>
                {t(`subscriptionTemplates.generators.${field}`)}
              </AccordionTrigger>
              <AccordionContent>
                <GeneratorField field={field} content={settings[field]} />
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  );
}

function GeneratorField({
  field,
  content,
}: {
  field: GeneratorKey;
  content: string;
}) {
  const { t } = useTranslation();
  const form = useForm({ defaultValues: { content } });
  const mutation = useUpdateRuntimeSettingsMutation();
  return (
    <form
      className="space-y-3"
      onSubmit={form.handleSubmit((values) =>
        mutation.mutate(
          { [field]: values.content },
          {
            onSuccess: () => {
              form.reset(values);
              generateSuccessMessage(t("settingsPage.saved"));
            },
            onError: (error) => {
              generateErrorMessage(error);
            },
          },
        ),
      )}
    >
      <Controller
        control={form.control}
        name="content"
        render={({ field: editor }) => (
          <MonacoJsonEditor
            value={editor.value}
            onChange={editor.onChange}
            language={field === "clash_settings" ? "yaml" : "json"}
            disabled={mutation.isPending}
            className="h-96"
          />
        )}
      />
      <div className="flex justify-end">
        <Button
          type="submit"
          size="sm"
          disabled={mutation.isPending || !form.formState.isDirty}
        >
          {t("settingsPage.save")}
        </Button>
      </div>
    </form>
  );
}
