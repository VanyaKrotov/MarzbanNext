import {
  Controller,
  type ControllerRenderProps,
  useFormContext,
} from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { HostFormValues } from "../lib/form";
import {
  getParameterSelectOptions,
  type HostParameterDefinition,
} from "../lib/parameters";
import { AlpnInput } from "./AlpnInput";

type ParameterFieldProps = {
  definition: HostParameterDefinition;
  pending: boolean;
};
type ParameterValueField = ControllerRenderProps<
  HostFormValues,
  `parameters.${string}`
>;

export function ParameterField({ definition, pending }: ParameterFieldProps) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  return (
    <Controller
      control={control}
      name={`parameters.${definition.id}`}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel
            htmlFor={`host-parameter-${definition.id}`}
            className="sr-only"
          >
            {t(definition.labelKey)}
          </FieldLabel>
          <ParameterInput
            definition={definition}
            pending={pending}
            invalid={fieldState.invalid}
            field={field}
          />
          <FieldError errors={[fieldState.error]} />
        </Field>
      )}
    />
  );
}

function ParameterInput({
  definition,
  pending,
  invalid,
  field,
}: {
  definition: HostParameterDefinition;
  pending: boolean;
  invalid: boolean;
  field: ParameterValueField;
}) {
  const { t } = useTranslation();
  const id = `host-parameter-${definition.id}`;

  if (definition.id === "alpn") {
    return (
      <AlpnInput
        id={id}
        value={field.value ?? ""}
        onChange={field.onChange}
        onBlur={field.onBlur}
        inputRef={field.ref}
        disabled={pending}
        invalid={invalid}
      />
    );
  }

  if (definition.kind === "select") {
    const options = getParameterSelectOptions(definition, field.value ?? "");
    return (
      <Select
        disabled={pending}
        value={field.value || "inherit"}
        onOpenChange={(open) => {
          if (!open) field.onBlur();
        }}
        onValueChange={(value) =>
          field.onChange(value === "inherit" ? "" : value)
        }
      >
        <SelectTrigger ref={field.ref} id={id} aria-invalid={invalid}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="inherit">
              {t(definition.emptyLabelKey ?? "hostEditor.defaultValue")}
            </SelectItem>
            {options.map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {t(label)}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    );
  }

  return (
    <Input
      {...field}
      id={id}
      value={field.value ?? ""}
      placeholder={
        definition.kind === "text" ? definition.placeholder : undefined
      }
      disabled={pending}
      aria-invalid={invalid}
    />
  );
}

export function VisibilityField({ pending }: { pending: boolean }) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  return (
    <Controller
      control={control}
      name="is_hidden"
      render={({ field }) => (
        <Field orientation="horizontal" className="min-w-0 flex-1">
          <Switch
            id="host-is-hidden"
            checked={field.value}
            onCheckedChange={field.onChange}
            disabled={pending}
          />
          <FieldLabel id="host-option-is_hidden" htmlFor="host-is-hidden">
            {t("hostEditor.isHidden")}
          </FieldLabel>
        </Field>
      )}
    />
  );
}
