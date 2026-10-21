import {
  Controller,
  type ControllerRenderProps,
  useFormContext,
} from "react-hook-form";
import { useTranslation } from "react-i18next";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
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
import { Textarea } from "@/components/ui/textarea";
import type { HostFormValues } from "../lib/form";
import type { HostParameterDefinition } from "../lib/parameters";

type ParameterFieldProps = {
  definition: HostParameterDefinition;
  pending: boolean;
  incompatible: boolean;
};
type ParameterValueField = ControllerRenderProps<
  HostFormValues,
  `parameters.${string}`
>;
const BOOLEAN_OPTIONS = [
  ["true", "hostsDialog.enabled"],
  ["false", "hostsDialog.disabled"],
] as const;
const SECURITY_OPTIONS = [
  ["tls", "TLS"],
  ["none", "hostEditor.noSecurity"],
] as const;

export function ParameterField({
  definition,
  pending,
  incompatible,
}: ParameterFieldProps) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  return (
    <Controller
      control={control}
      name={`parameters.${definition.id}`}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid || incompatible}>
          <FieldLabel
            htmlFor={`host-parameter-${definition.id}`}
            className="sr-only"
          >
            {t(definition.labelKey)}
          </FieldLabel>
          <ParameterInput
            definition={definition}
            pending={pending}
            invalid={fieldState.invalid || incompatible}
            field={field}
          />
          {definition.id === "xhttp_extra" && (
            <FieldDescription>{t("hostEditor.extraHint")}</FieldDescription>
          )}
          {incompatible && (
            <FieldError>{t("hostEditor.incompatibleInbound")}</FieldError>
          )}
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

  if (definition.kind === "boolean" || definition.kind === "security") {
    const options =
      definition.kind === "boolean" ? BOOLEAN_OPTIONS : SECURITY_OPTIONS;
    return (
      <Select
        disabled={pending}
        value={field.value || "inherit"}
        onValueChange={(value) =>
          field.onChange(value === "inherit" ? "" : value)
        }
      >
        <SelectTrigger ref={field.ref} id={id} aria-invalid={invalid}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="inherit">{t("hostEditor.inherit")}</SelectItem>
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

  if (definition.kind === "json") {
    return (
      <Textarea
        {...field}
        id={id}
        value={field.value ?? ""}
        disabled={pending}
        aria-invalid={invalid}
        rows={6}
        className="font-mono text-xs"
        dir="ltr"
        placeholder={
          definition.id === "xhttp_extra"
            ? '{"scMaxBufferedPosts":0,"xPaddingObfsMode":false,"uplinkHTTPMethod":"PUT"}'
            : undefined
        }
      />
    );
  }

  return (
    <Input
      {...field}
      id={id}
      value={field.value ?? ""}
      disabled={pending}
      aria-invalid={invalid}
    />
  );
}

export function StandaloneField({ pending }: { pending: boolean }) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  return (
    <Controller
      control={control}
      name="show_when_composed"
      render={({ field }) => (
        <Field>
          <Switch
            aria-label={t("hostEditor.showWhenComposed")}
            checked={field.value}
            onCheckedChange={field.onChange}
            disabled={pending}
          />
          <FieldDescription>
            {t("hostEditor.showWhenComposedHint")}
          </FieldDescription>
        </Field>
      )}
    />
  );
}
