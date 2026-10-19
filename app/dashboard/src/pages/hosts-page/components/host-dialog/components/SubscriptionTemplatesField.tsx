import { Controller, useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  formatLabelKeys,
  subscriptionFormats,
  type SubscriptionTemplate,
} from "@/pages/subscription-templates-page/lib/query";

import type { HostFormValues } from "../lib/form";

export function SubscriptionTemplatesField({
  templates,
  pending,
}: {
  templates: SubscriptionTemplate[];
  pending: boolean;
}) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  return (
    <Field className="rounded-lg border p-4">
      <FieldLabel>{t("subscriptionTemplates.title")}</FieldLabel>
      <FieldDescription>
        {t("subscriptionTemplates.hostDescription")}
      </FieldDescription>
      <Controller
        control={control}
        name="subscription_template_ids"
        render={({ field }) => (
          <div className="space-y-3">
            {subscriptionFormats.map((format) => {
              const options = templates.filter(
                (item) => item.format === format,
              );
              const selected = field.value[format];
              const defaultTemplate =
                options.find((item) => item.is_default) ?? options[0];
              const setSelection = (id?: number) => {
                const next = { ...field.value };
                if (id === undefined) delete next[format];
                else next[format] = id;
                field.onChange(next);
              };
              return (
                <div
                  key={format}
                  className="grid grid-cols-[auto_1fr] items-center gap-3 sm:grid-cols-[auto_8rem_1fr]"
                >
                  <Switch
                    id={`format-${format}`}
                    checked={selected !== undefined}
                    disabled={pending || !options.length}
                    onCheckedChange={(checked) =>
                      setSelection(checked ? defaultTemplate?.id : undefined)
                    }
                  />
                  <label htmlFor={`format-${format}`} className="text-sm">
                    {t(formatLabelKeys[format])}
                  </label>
                  <Select
                    value={selected?.toString() ?? ""}
                    onValueChange={(value) => setSelection(Number(value))}
                    disabled={pending || selected === undefined}
                  >
                    <SelectTrigger
                      aria-label={t(formatLabelKeys[format])}
                      className="col-span-2 w-full sm:col-span-1"
                    >
                      <SelectValue
                        placeholder={t("subscriptionTemplates.disabled")}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {options.map((item) => (
                        <SelectItem key={item.id} value={String(item.id)}>
                          {item.name}
                          {item.is_default
                            ? ` (${t("subscriptionTemplates.default")})`
                            : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              );
            })}
          </div>
        )}
      />
    </Field>
  );
}
