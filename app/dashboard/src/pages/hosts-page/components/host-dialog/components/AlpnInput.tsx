import { useMemo, useState, type Ref } from "react";
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
import { alpnOptions, getAlpnSelection } from "../lib/alpn";

type AlpnInputProps = {
  id: string;
  value: string;
  onChange: (value: string) => void;
  onBlur: () => void;
  inputRef: Ref<HTMLInputElement>;
  disabled: boolean;
  invalid: boolean;
};

export function AlpnInput({
  id,
  value,
  onChange,
  onBlur,
  inputRef,
  disabled,
  invalid,
}: AlpnInputProps) {
  const { t } = useTranslation();
  const anchor = useComboboxAnchor();
  const [search, setSearch] = useState("");
  const [storedOptions] = useState(() => getAlpnSelection(value));
  const selected = useMemo(() => getAlpnSelection(value), [value]);
  // Existing custom identifiers remain selectable when editing an older host.
  const options = useMemo(
    () => [...new Set([...alpnOptions, ...storedOptions, ...selected])],
    [storedOptions, selected],
  );

  return (
    <Combobox<string, true>
      multiple
      items={options}
      value={selected}
      disabled={disabled}
      inputValue={search}
      onInputValueChange={setSearch}
      onOpenChange={(open, details) => {
        if (!open && details.reason === "item-press") details.cancel();
      }}
      onValueChange={(values) => {
        onChange(JSON.stringify(values));
        setSearch("");
      }}
    >
      <ComboboxChips ref={anchor}>
        <ComboboxValue>
          {(values: string[]) =>
            values.map((protocol) => (
              <ComboboxChip
                key={protocol}
                className="min-w-0 max-w-full"
                removeLabel={t("hostEditor.removeParameter", {
                  name: protocol,
                })}
              >
                <span className="min-w-0 truncate">{protocol}</span>
              </ComboboxChip>
            ))
          }
        </ComboboxValue>
        <ComboboxChipsInput
          id={id}
          ref={inputRef}
          onBlur={onBlur}
          disabled={disabled}
          aria-invalid={invalid}
          placeholder={t("actions.select")}
        />
      </ComboboxChips>
      <ComboboxContent anchor={anchor}>
        <ComboboxEmpty>{t("hostEditor.noAlpnResults")}</ComboboxEmpty>
        <ComboboxList>
          {(protocol: string) => (
            <ComboboxItem key={protocol} value={protocol}>
              {protocol}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
