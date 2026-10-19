import { LoaderCircle } from "lucide-react";
import { Controller, useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";

import type { HostFormValues } from "../lib/form";

export function FormActions({
  isEditing,
  pending,
}: {
  isEditing: boolean;
  pending: boolean;
}) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();

  return (
    <div className="flex flex-col gap-x-3 gap-y-5 border-t pt-4 sm:flex-row sm:items-center">
      <Controller
        name="is_disabled"
        control={form.control}
        render={({ field }) => (
          <Field className="w-40" orientation="horizontal">
            <Switch
              id="host-enabled"
              checked={!field.value}
              disabled={pending}
              onCheckedChange={(checked) => field.onChange(!checked)}
            />
            <FieldLabel htmlFor="host-enabled">
              {t(
                field.value
                  ? "hostsPage.disabledState"
                  : "hostsPage.enabledState",
              )}
            </FieldLabel>
          </Field>
        )}
      />
      <Button type="submit" className="w-full sm:flex-1" disabled={pending}>
        {pending && <LoaderCircle className="animate-spin" />}
        {isEditing ? t("core.save") : t("create")}
      </Button>
    </div>
  );
}
