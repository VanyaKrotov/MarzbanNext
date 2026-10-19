import { zodResolver } from "@hookform/resolvers/zod";
import { type ReactNode, useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  getNodeDefaultValues,
  NodeSchema,
  type NodeType,
} from "types/Node";

type NodeFormProps = {
  node?: NodeType | null;
  pending: boolean;
  actions?: ReactNode;
  onSubmit: (node: NodeType) => void;
};

export function NodeForm({
  node,
  pending,
  actions,
  onSubmit,
}: NodeFormProps) {
  const { t } = useTranslation();
  const isEditing = Boolean(node);
  const form = useForm<NodeType>({
    resolver: zodResolver(NodeSchema),
    defaultValues: node ?? {
      ...getNodeDefaultValues(),
      add_as_new_host: false,
    },
  });

  useEffect(() => {
    if (node && !form.formState.isDirty) {
      form.reset(node);
    }
  }, [form, node]);

  return (
    <form
      className="space-y-4"
      onSubmit={form.handleSubmit(onSubmit)}
      id={isEditing ? "edit-node-form" : "create-node-form"}
    >
      <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
        <Field data-invalid={Boolean(form.formState.errors.name)}>
          <FieldLabel htmlFor="node-name">{t("nodes.nodeName")}</FieldLabel>
          <Input
            id="node-name"
            placeholder="MarzbanNext-S2"
            disabled={pending}
            {...form.register("name")}
          />
          <FieldError errors={[form.formState.errors.name]} />
        </Field>

        {isEditing && (
          <Controller
            name="status"
            control={form.control}
            render={({ field }) => (
              <Field
                className="w-[140px] shrink-0 sm:pt-6 [&>[data-slot=field-label]]:flex-none"
                orientation="horizontal"
              >
                <Switch
                  id="node-enabled"
                  checked={field.value !== "disabled"}
                  disabled={pending}
                  onCheckedChange={(checked) =>
                    field.onChange(checked ? "connecting" : "disabled")
                  }
                />
                <FieldLabel htmlFor="node-enabled">
                  {field.value === "disabled"
                    ? t("nodes.disabledState")
                    : t("nodes.enabledState")}
                </FieldLabel>
              </Field>
            )}
          />
        )}
      </div>

      <Field data-invalid={Boolean(form.formState.errors.address)}>
        <FieldLabel htmlFor="node-address">{t("nodes.nodeAddress")}</FieldLabel>
        <Input
          id="node-address"
          placeholder="51.20.12.13"
          disabled={pending}
          {...form.register("address")}
        />
        <FieldError errors={[form.formState.errors.address]} />
      </Field>

      <div className="grid gap-4 sm:grid-cols-3 items-end">
        <NumberField
          id="node-port"
          label={t("nodes.nodePort")}
          disabled={pending}
          error={form.formState.errors.port?.message}
          value={form.watch("port")}
          onChange={(value) =>
            form.setValue("port", value, { shouldValidate: true })
          }
        />
        <NumberField
          id="node-api-port"
          label={t("nodes.nodeAPIPort")}
          disabled={pending}
          error={form.formState.errors.api_port?.message}
          value={form.watch("api_port")}
          onChange={(value) =>
            form.setValue("api_port", value, { shouldValidate: true })
          }
        />
        <NumberField
          id="node-usage-coefficient"
          label={t("nodes.usageCoefficient")}
          disabled={pending}
          step="any"
          error={form.formState.errors.usage_coefficient?.message}
          value={form.watch("usage_coefficient")}
          onChange={(value) =>
            form.setValue("usage_coefficient", value, { shouldValidate: true })
          }
        />
      </div>

      {!isEditing && (
        <Controller
          name="add_as_new_host"
          control={form.control}
          render={({ field }) => (
            <Field orientation="horizontal">
              <Checkbox
                id="node-add-as-host"
                checked={field.value}
                disabled={pending}
                onCheckedChange={(checked) => field.onChange(checked === true)}
              />
              <FieldLabel htmlFor="node-add-as-host">
                {t("nodes.addHostForEveryInbound")}
              </FieldLabel>
            </Field>
          )}
        />
      )}

      <div className="flex items-center gap-2 pt-6">
        {actions}
        <Button className="flex-1" type="submit" disabled={pending}>
          {isEditing ? t("core.save") : t("actions.connect")}
        </Button>
      </div>
    </form>
  );
}

function NumberField({
  id,
  label,
  value,
  error,
  disabled,
  step = "1",
  onChange,
}: {
  id: string;
  label: string;
  value: number | string;
  error?: string;
  disabled: boolean;
  step?: string;
  onChange: (value: number) => void;
}) {
  return (
    <Field data-invalid={Boolean(error)}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        type="number"
        min="1"
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.valueAsNumber)}
      />
      <FieldError errors={error ? [{ message: error }] : []} />
    </Field>
  );
}
