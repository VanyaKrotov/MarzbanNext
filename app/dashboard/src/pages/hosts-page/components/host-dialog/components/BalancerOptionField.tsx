import { Controller, type FieldPath, useFormContext } from "react-hook-form";
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
import { Textarea } from "@/components/ui/textarea";
import type { HostFormValues } from "../lib/form";

type BalancerOptionFieldProps = {
  name: FieldPath<HostFormValues>;
  label: string;
  kind: "text" | "number" | "boolean" | "json";
  pending: boolean;
  min?: number;
  max?: number;
  step?: number | "any";
  placeholder?: string;
  shouldUnregister?: boolean;
};

export function BalancerOptionField({
  name,
  label,
  kind,
  pending,
  min,
  max,
  step,
  placeholder,
  shouldUnregister = false,
}: BalancerOptionFieldProps) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  const id = `host-${name.replaceAll(".", "-")}`;

  return (
    <Controller
      control={control}
      name={name}
      shouldUnregister={shouldUnregister}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel htmlFor={id}>{label}</FieldLabel>
          {kind === "boolean" ? (
            <Select
              disabled={pending}
              value={
                field.value === undefined ? "inherit" : String(field.value)
              }
              onValueChange={(value) =>
                field.onChange(
                  value === "inherit" ? undefined : value === "true",
                )
              }
            >
              <SelectTrigger
                ref={field.ref}
                id={id}
                aria-invalid={fieldState.invalid}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="inherit">
                    {t("hostEditor.defaultValue")}
                  </SelectItem>
                  <SelectItem value="true">
                    {t("hostsDialog.enabled")}
                  </SelectItem>
                  <SelectItem value="false">
                    {t("hostsDialog.disabled")}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          ) : kind === "json" ? (
            <Textarea
              ref={field.ref}
              name={field.name}
              id={id}
              dir="ltr"
              disabled={pending}
              value={String(field.value ?? "")}
              onChange={field.onChange}
              onBlur={field.onBlur}
              placeholder={placeholder}
              aria-invalid={fieldState.invalid}
              className="font-mono text-xs"
            />
          ) : (
            <Input
              ref={field.ref}
              name={field.name}
              id={id}
              disabled={pending}
              type={kind}
              min={min}
              max={max}
              step={step}
              value={String(field.value ?? "")}
              onBlur={field.onBlur}
              aria-invalid={fieldState.invalid}
              placeholder={placeholder ?? t("hostEditor.defaultValue")}
              onChange={(event) =>
                field.onChange(
                  event.target.value === ""
                    ? undefined
                    : kind === "number"
                      ? event.target.valueAsNumber
                      : event.target.value,
                )
              }
            />
          )}
          <FieldError errors={[fieldState.error]} />
        </Field>
      )}
    />
  );
}
