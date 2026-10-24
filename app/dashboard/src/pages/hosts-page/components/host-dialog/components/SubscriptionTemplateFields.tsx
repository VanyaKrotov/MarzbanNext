import { useId, useMemo, useState } from "react";
import { useController, useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";
import {
  Combobox,
  ComboboxChip,
  ComboboxChips,
  ComboboxChipsInput,
  ComboboxCollection,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxGroup,
  ComboboxItem,
  ComboboxLabel,
  ComboboxList,
  ComboboxValue,
  useComboboxAnchor,
} from "@/components/ui/combobox";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import {
  formatLabelKeys,
  subscriptionFormats,
} from "@/pages/subscription-templates-page/lib/formats";
import type { SubscriptionTemplate } from "@/pages/subscription-templates-page/lib/query";
import type { HostFormValues } from "../lib/form";
import {
  getHostTemplateOptions,
  getSelectedHostTemplates,
  templateBindingsFromSelection,
  templateChipLabel,
} from "../lib/template-selection";

type TemplateGroup = {
  value: SubscriptionTemplate["format"];
  items: SubscriptionTemplate[];
};

export function SubscriptionTemplateFields({
  templates,
  pending,
}: {
  templates: SubscriptionTemplate[];
  pending: boolean;
}) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  const { field, fieldState } = useController({
    control,
    name: "subscription_template_ids",
  });
  const id = useId();
  const anchor = useComboboxAnchor();
  const [search, setSearch] = useState("");
  const options = useMemo(() => getHostTemplateOptions(templates), [templates]);
  const groups = useMemo(
    () =>
      subscriptionFormats
        .map((format) => ({
          value: format,
          items: options.filter((template) => template.format === format),
        }))
        .filter((group) => group.items.length > 0),
    [options],
  );

  const selected = useMemo(
    () => getSelectedHostTemplates(options, field.value),
    [options, field.value],
  );

  return (
    <Field data-invalid={fieldState.invalid}>
      <FieldLabel htmlFor={id} className="sr-only">
        {t("hostEditor.templates")}
      </FieldLabel>
      <Combobox<SubscriptionTemplate, true>
        multiple
        items={groups}
        value={selected}
        inputValue={search}
        onInputValueChange={setSearch}
        onOpenChange={(open, details) => {
          // Keep the picker ready for another format after selecting a search result.
          if (!open && details.reason === "item-press") details.cancel();
        }}
        disabled={pending}
        itemToStringLabel={templateChipLabel}
        isItemEqualToValue={(left, right) => left.id === right.id}
        onValueChange={(values) => {
          field.onChange(templateBindingsFromSelection(values, field.value));
          setSearch("");
        }}
      >
        <ComboboxChips ref={anchor}>
          <ComboboxValue>
            {(values: SubscriptionTemplate[]) =>
              values.map((template) => (
                <ComboboxChip
                  key={template.id}
                  className="min-w-0 max-w-full"
                  removeLabel={t("hostEditor.removeParameter", {
                    name: templateChipLabel(template),
                  })}
                >
                  <span className="min-w-0 truncate">
                    {templateChipLabel(template)}
                  </span>
                </ComboboxChip>
              ))
            }
          </ComboboxValue>
          <ComboboxChipsInput
            id={id}
            ref={field.ref}
            disabled={pending}
            onBlur={field.onBlur}
            aria-invalid={fieldState.invalid}
            placeholder={t("subscriptionTemplates.search")}
          />
        </ComboboxChips>
        <ComboboxContent anchor={anchor}>
          <ComboboxEmpty>{t("subscriptionTemplates.empty")}</ComboboxEmpty>
          <ComboboxList>
            {(group: TemplateGroup) => (
              <ComboboxGroup key={group.value} items={group.items}>
                <ComboboxLabel>{t(formatLabelKeys[group.value])}</ComboboxLabel>
                <ComboboxCollection>
                  {(template: SubscriptionTemplate) => (
                    <ComboboxItem key={template.id} value={template}>
                      {template.name}
                    </ComboboxItem>
                  )}
                </ComboboxCollection>
              </ComboboxGroup>
            )}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
      <FieldError errors={[fieldState.error]} />
    </Field>
  );
}
