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
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import {
  formatLabelKeys,
  commonTemplateFormats,
  hostTemplateFormats,
} from "@/pages/subscription-templates-page/lib/formats";
import type { SubscriptionTemplate } from "@/pages/subscription-templates-page/lib/query";
import type { HostFormValues } from "../lib/form";
import {
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
  const groups = useMemo(
    () =>
      hostTemplateFormats
        .map((format) => ({
          value: format,
          items: templates.filter((template) => template.format === format),
        }))
        .filter((group) => group.items.length > 0),
    [templates],
  );

  const selected = useMemo(
    () =>
      groups
        .flatMap((group) => group.items)
        .filter((template) => field.value[template.format] === template.id),
    [groups, field.value],
  );

  return (
    <FieldGroup>
      {commonTemplateFormats.map((format) => {
        const defaultTemplate = templates.find(
          (template) => template.format === format && template.is_default,
        );
        const switchId = `${id}-${format}`;
        return (
          <Field key={format} orientation="horizontal" data-disabled={pending}>
            <Switch
              id={switchId}
              checked={field.value[format] !== undefined}
              disabled={pending || !defaultTemplate}
              onBlur={field.onBlur}
              onCheckedChange={(checked) => {
                const bindings = { ...field.value };
                if (checked && defaultTemplate)
                  bindings[format] = defaultTemplate.id;
                else delete bindings[format];
                field.onChange(bindings);
              }}
            />
            <FieldLabel htmlFor={switchId}>
              {t(formatLabelKeys[format])}
            </FieldLabel>
          </Field>
        );
      })}
      <FieldDescription>{t("hostEditor.commonTemplateHint")}</FieldDescription>
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
            field.onChange(
              templateBindingsFromSelection(
                values,
                field.value,
                hostTemplateFormats,
              ),
            );
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
                  <ComboboxLabel>
                    {t(formatLabelKeys[group.value])}
                  </ComboboxLabel>
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
    </FieldGroup>
  );
}
