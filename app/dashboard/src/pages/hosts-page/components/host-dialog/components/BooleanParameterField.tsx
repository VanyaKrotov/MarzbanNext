import { Controller, useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Field, FieldLabel } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import type { HostFormValues } from "../lib/form";
import type { HostParameterDefinition } from "../lib/parameters";

export function BooleanParameterField({
  definition,
  pending,
}: {
  definition: HostParameterDefinition;
  pending: boolean;
}) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  const id = `host-parameter-${definition.id}`;
  return (
    <Controller
      control={control}
      name={`parameters.${definition.id}`}
      defaultValue="false"
      render={({ field }) => (
        <Field
          orientation="horizontal"
          className="min-w-0 flex-1"
          data-disabled={pending}
        >
          <Switch
            ref={field.ref}
            id={id}
            name={field.name}
            checked={field.value === "true"}
            onCheckedChange={(checked) => field.onChange(String(checked))}
            onBlur={field.onBlur}
            disabled={pending}
          />
          <FieldLabel id={`host-option-${definition.id}`} htmlFor={id}>
            {t(definition.labelKey)}
          </FieldLabel>
        </Field>
      )}
    />
  );
}
