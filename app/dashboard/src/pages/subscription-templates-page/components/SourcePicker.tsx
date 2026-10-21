import { useId } from "react";
import { useTranslation } from "react-i18next";
import {
  Combobox,
  ComboboxChip,
  ComboboxChips,
  ComboboxChipsInput,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxValue,
  useComboboxAnchor,
} from "@/components/ui/combobox";
import { Field, FieldLabel } from "@/components/ui/field";

export type SourceOption = { id: string; label: string };

export function SourcePicker({
  label,
  options,
  value,
  onChange,
  disabled,
}: {
  label: string;
  options: SourceOption[];
  value: SourceOption[];
  onChange: (value: SourceOption[]) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const anchor = useComboboxAnchor();
  const { t } = useTranslation();
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Combobox<SourceOption, true>
        multiple
        items={options}
        value={value}
        onValueChange={onChange}
        disabled={disabled}
        itemToStringLabel={(item) => item.label}
        isItemEqualToValue={(a, b) => a.id === b.id}
      >
        <ComboboxChips ref={anchor}>
          <ComboboxValue>
            {(selected: SourceOption[]) =>
              selected.map((item) => (
                <ComboboxChip
                  key={item.id}
                  removeLabel={t("hostEditor.removeParameter", {
                    name: item.label,
                  })}
                >
                  {item.label}
                </ComboboxChip>
              ))
            }
          </ComboboxValue>
          <ComboboxChipsInput id={id} />
        </ComboboxChips>
        <ComboboxContent anchor={anchor}>
          <ComboboxEmpty>{t("subscriptionTemplates.empty")}</ComboboxEmpty>
          <ComboboxList>
            {(item: SourceOption) => (
              <ComboboxItem key={item.id} value={item}>
                {item.label}
              </ComboboxItem>
            )}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
    </Field>
  );
}
