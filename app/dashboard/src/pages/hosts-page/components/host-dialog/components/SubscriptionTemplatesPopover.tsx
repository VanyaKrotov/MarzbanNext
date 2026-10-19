import { SlidersHorizontal } from "lucide-react";
import { useId } from "react";
import { Controller, useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  Popover,
  PopoverContent,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  formatLabelKeys,
  subscriptionFormats,
  type SubscriptionTemplate,
} from "@/pages/subscription-templates-page/lib/query";

import type { HostFormValues } from "../lib/form";

export function SubscriptionTemplatesPopover({
  templates,
  pending,
}: {
  templates: SubscriptionTemplate[];
  pending: boolean;
}) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  const id = useId();
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="icon"
          disabled={pending}
          aria-label={t("subscriptionTemplates.title")}
          title={t("subscriptionTemplates.title")}
        >
          <SlidersHorizontal />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        collisionPadding={16}
        className="max-h-(--radix-popover-content-available-height) w-96 max-w-[calc(100vw-2rem)] overflow-y-auto"
        aria-labelledby={`${id}-title`}
      >
        <PopoverHeader>
          <PopoverTitle id={`${id}-title`}>
            {t("subscriptionTemplates.title")}
          </PopoverTitle>
        </PopoverHeader>
        <Controller
          control={control}
          name="subscription_template_ids"
          render={({ field }) => (
            <FieldGroup className="gap-3">
              {subscriptionFormats.map((format) => {
                const options = templates.filter(
                  (item) => item.format === format,
                );
                const selected = field.value[format];
                const setSelection = (templateId: number | null) => {
                  const next = { ...field.value };
                  if (templateId === null) delete next[format];
                  else next[format] = templateId;
                  field.onChange(next);
                };
                return (
                  <Field
                    key={format}
                    orientation="horizontal"
                    className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)] gap-3"
                  >
                    <FieldLabel htmlFor={`${id}-${format}`}>
                      {t(formatLabelKeys[format])}
                    </FieldLabel>
                    <Select
                      value={selected?.toString() ?? "__none__"}
                      onValueChange={(value) =>
                        setSelection(value === "__none__" ? null : Number(value))
                      }
                      disabled={pending}
                    >
                      <SelectTrigger
                        id={`${id}-${format}`}
                        className="w-full min-w-0"
                        onBlur={field.onBlur}
                      >
                        <SelectValue>
                          {options.find((item) => item.id === selected)?.name ??
                            t("subscriptionTemplates.excluded")}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectItem value="__none__">
                            {t("subscriptionTemplates.excluded")}
                          </SelectItem>
                          {options.map((item) => (
                            <SelectItem key={item.id} value={String(item.id)}>
                              {item.name}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </Field>
                );
              })}
            </FieldGroup>
          )}
        />
      </PopoverContent>
    </Popover>
  );
}
