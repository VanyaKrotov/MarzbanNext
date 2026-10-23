import { useCallback, useMemo, useState } from "react";
import {
  Controller,
  useController,
  useForm,
  useFormContext,
} from "react-hook-form";
import { useTranslation } from "react-i18next";
import {
  MonacoJsonEditor,
  type MonacoJsonMarker,
} from "@/components/MonacoJsonEditor";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { useHostCapabilitiesQuery } from "../../../lib/query";
import type { HostFormValues } from "../lib/form";
import { jsonParameterSchema, parseJsonObject } from "../lib/json-parameters";
import type { HostParameterDefinition } from "../lib/parameters";
import type { HostFormProps } from "../lib/types";
import { useSupportsXhttp } from "../lib/useSupportsXhttp";
import { HostParameterHeader } from "./HostParameterHeader";

export function JsonParameterField({
  definition,
  pending,
  inbounds,
  onRemove,
}: Pick<HostFormProps, "pending" | "inbounds"> & {
  definition: HostParameterDefinition;
  onRemove: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const { control, clearErrors } = useFormContext<HostFormValues>();
  const name = `parameters.${definition.id}` as const;
  const { field, fieldState } = useController({ control, name });
  const supportsXhttp = useSupportsXhttp(inbounds);
  const incompatible = Boolean(definition.xhttpOnly && !supportsXhttp);
  const label = t(definition.labelKey);
  return (
    <FieldGroup
      className="gap-3"
      aria-labelledby={`host-option-${definition.id}`}
    >
      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (!next) field.onBlur();
        }}
      >
        <HostParameterHeader
          id={definition.id}
          label={label}
          pending={pending}
          onRemove={onRemove}
          hintKey={definition.hintKey}
        >
          <DialogTrigger asChild>
            <Button
              ref={field.ref}
              id={`host-parameter-${definition.id}`}
              type="button"
              variant="outline"
              size="sm"
              disabled={pending}
              aria-invalid={fieldState.invalid || incompatible}
              aria-label={t("hostEditor.configureParameter", { name: label })}
              onBlur={field.onBlur}
            >
              {t("actions.configure")}
            </Button>
          </DialogTrigger>
        </HostParameterHeader>
        <DialogContent
          aria-describedby={undefined}
          className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-4xl"
        >
          <JsonParameterEditor
            definition={definition}
            value={field.value ?? ""}
            pending={pending}
            onSave={(value) => {
              field.onChange(value);
              field.onBlur();
              clearErrors(name);
              setOpen(false);
            }}
          />
        </DialogContent>
      </Dialog>
      {incompatible && (
        <FieldError>{t("hostEditor.incompatibleInbound")}</FieldError>
      )}
      <FieldError errors={[fieldState.error]} />
    </FieldGroup>
  );
}

function JsonParameterEditor({
  definition,
  value,
  pending,
  onSave,
}: {
  definition: HostParameterDefinition;
  value: string;
  pending: boolean;
  onSave: (value: string) => void;
}) {
  const { t } = useTranslation();
  const form = useForm({ defaultValues: { json: value || "{}" } });
  const [schemaErrors, setSchemaErrors] = useState(false);
  const capabilities = useHostCapabilitiesQuery();
  const schema = useMemo(
    () =>
      jsonParameterSchema(definition.path, capabilities.data?.overrides_schema),
    [definition.path, capabilities.data],
  );
  const onValidate = useCallback((markers: MonacoJsonMarker[]) => {
    setSchemaErrors(markers.some((marker) => marker.severity >= 8));
  }, []);
  const label = t(definition.labelKey);
  const id = `host-json-editor-${definition.id}`;
  return (
    <>
      <DialogHeader>
        <DialogTitle>{label}</DialogTitle>
      </DialogHeader>
      <form
        className="flex min-w-0 flex-col gap-5"
        onSubmit={(event) => {
          // Portal events still bubble through the host form in React.
          event.stopPropagation();
          void form.handleSubmit(({ json }) => {
            if (!schemaErrors)
              onSave(JSON.stringify(parseJsonObject(json), null, 2));
          })(event);
        }}
      >
        <FieldGroup>
          <Controller
            control={form.control}
            name="json"
            rules={{
              validate: (text) => {
                try {
                  parseJsonObject(text);
                  return true;
                } catch {
                  return t("hostEditor.invalidJsonObject");
                }
              },
            }}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid || schemaErrors}>
                <FieldLabel htmlFor={id} className="sr-only">
                  {label}
                </FieldLabel>
                <MonacoJsonEditor
                  ref={field.ref}
                  id={id}
                  value={field.value}
                  onChange={field.onChange}
                  schema={schema}
                  onValidate={onValidate}
                  disabled={pending}
                  invalid={fieldState.invalid || schemaErrors}
                  className="h-[min(55svh,32rem)] rounded-md"
                />
                <FieldError errors={[fieldState.error]} />
                {schemaErrors && !fieldState.error && (
                  <FieldError>{t("hostEditor.jsonSchemaError")}</FieldError>
                )}
              </Field>
            )}
          />
        </FieldGroup>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              {t("cancel")}
            </Button>
          </DialogClose>
          <Button type="submit" disabled={pending}>
            {t("core.save")}
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}
