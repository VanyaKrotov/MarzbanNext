import { ArrowDown, ArrowUp, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useController, useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import type { HostType } from "../../../types";
import type { HostFormValues } from "../lib/form";

function describeHost(host: HostType) {
  return `${host.remark} (${host.inbound_tag}, ${host.address}:${host.port ?? host.inbound_port ?? ""})`;
}

export function LinkedHostsField({
  hosts,
  pending,
}: {
  hosts: HostType[];
  pending: boolean;
}) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  const { field, fieldState } = useController({
    control,
    name: "linked_host_ids",
  });
  const [search, setSearch] = useState("");
  const hostsById = useMemo(
    () => new Map(hosts.map((host) => [host.id, host])),
    [hosts],
  );

  const availableHosts = useMemo(() => {
    const selectedIds = new Set(field.value);
    return hosts.filter((host) => !selectedIds.has(host.id));
  }, [hosts, field.value]);
  const move = (index: number, delta: number) => {
    const next = [...field.value];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    field.onChange(next);
  };

  return (
    <Field data-invalid={fieldState.invalid}>
      <FieldLabel htmlFor="host-linked-hosts">
        {t("hostEditor.linkedHosts")}
      </FieldLabel>
      <Combobox
        items={availableHosts}
        value={null}
        inputValue={search}
        onInputValueChange={setSearch}
        itemToStringLabel={describeHost}
        disabled={pending}
        onValueChange={(host: HostType | null) => {
          if (host && !field.value.includes(host.id))
            field.onChange([...field.value, host.id]);
          setSearch("");
        }}
      >
        <ComboboxInput
          id="host-linked-hosts"
          disabled={pending}
          onBlur={field.onBlur}
          aria-invalid={fieldState.invalid}
          placeholder={t("hostEditor.searchLinkedHosts")}
        />
        <ComboboxContent>
          <ComboboxEmpty>{t("hostEditor.noLinkedHosts")}</ComboboxEmpty>
          <ComboboxList>
            {(host: HostType) => (
              <ComboboxItem key={host.id} value={host}>
                {describeHost(host)}
              </ComboboxItem>
            )}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
      {field.value.length > 0 && (
        <FieldGroup className="gap-2">
          {field.value.map((id, index) => {
            const host = hostsById.get(id);
            return (
              <div key={id} className="flex items-center gap-1">
                <span className="min-w-0 flex-1 break-words text-sm">
                  {host ? describeHost(host) : String(id)}
                </span>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  aria-label={t("hostEditor.moveUp")}
                  disabled={pending || index === 0}
                  onClick={() => move(index, -1)}
                >
                  <ArrowUp />
                </Button>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  aria-label={t("hostEditor.moveDown")}
                  disabled={pending || index === field.value.length - 1}
                  onClick={() => move(index, 1)}
                >
                  <ArrowDown />
                </Button>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  disabled={pending}
                  aria-label={t("hostEditor.removeParameter", {
                    name: host?.remark ?? String(id),
                  })}
                  onClick={() =>
                    field.onChange(field.value.filter((value) => value !== id))
                  }
                >
                  <X />
                </Button>
              </div>
            );
          })}
        </FieldGroup>
      )}
      <FieldError errors={[fieldState.error]} />
    </Field>
  );
}
