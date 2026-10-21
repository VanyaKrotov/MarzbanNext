import {
  Controller,
  useFormContext,
  useFormState,
  useWatch,
} from "react-hook-form";
import { useTranslation } from "react-i18next";
import {
  Field,
  FieldError,
  FieldGroup,
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
import type { InboundType } from "@/types/Inbound";
import type { HostFormValues } from "../lib/form";
import { VariablesPopover } from "./VariablesPopover";

type PendingProps = { pending: boolean };

export function RemarkField({ pending }: PendingProps) {
  const { t } = useTranslation();
  const { register, control } = useFormContext<HostFormValues>();
  const { errors } = useFormState({ control, name: "remark", exact: true });
  return (
    <Field data-invalid={Boolean(errors.remark)}>
      <div className="flex items-center gap-2">
        <FieldLabel htmlFor="host-remark">{t("hostEditor.remark")}</FieldLabel>
        <VariablesPopover />
      </div>
      <FieldGroup className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
        <Input
          id="host-remark"
          disabled={pending}
          aria-invalid={Boolean(errors.remark)}
          {...register("remark")}
        />
        <Controller
          control={control}
          name="enabled"
          render={({ field }) => (
            <Switch
              id="host-enabled"
              aria-label={t("hostsPage.enabled")}
              checked={field.value}
              onCheckedChange={field.onChange}
              disabled={pending}
            />
          )}
        />
      </FieldGroup>
      <FieldError errors={[errors.remark]} />
    </Field>
  );
}

export function InboundField({
  inbounds,
  pending,
}: PendingProps & { inbounds: InboundType[] }) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  return (
    <Controller
      control={control}
      name="inbound_id"
      render={({ field }) => (
        <Field>
          <FieldLabel htmlFor="host-inbound">
            {t("hostsPage.inbound")}
          </FieldLabel>
          <Select
            value={String(field.value)}
            onValueChange={(value) => field.onChange(Number(value))}
            disabled={pending}
          >
            <SelectTrigger id="host-inbound" ref={field.ref}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {inbounds.map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.tag} ({item.protocol}/{item.network}) —{" "}
                    {item.nodes.map((node) => node.name).join(", ") ||
                      t("hostsPage.unassignedNodes")}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
      )}
    />
  );
}

export function AddressField({ pending }: PendingProps) {
  const { t } = useTranslation();
  const { register, control } = useFormContext<HostFormValues>();
  const { errors } = useFormState({ control, name: "address", exact: true });
  return (
    <Field data-invalid={Boolean(errors.address)}>
      <FieldLabel htmlFor="host-address">{t("nodes.nodeAddress")}</FieldLabel>
      <Input
        id="host-address"
        disabled={pending}
        aria-invalid={Boolean(errors.address)}
        {...register("address")}
      />
      <FieldError errors={[errors.address]} />
    </Field>
  );
}

export function PortField({
  inbounds,
  pending,
}: PendingProps & { inbounds: InboundType[] }) {
  const { t } = useTranslation();
  const { control } = useFormContext<HostFormValues>();
  const inboundId = useWatch({ control, name: "inbound_id", exact: true });
  const inbound = inbounds.find((item) => item.id === inboundId);
  return (
    <Controller
      control={control}
      name="port"
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel htmlFor="host-port">{t("hostsDialog.port")}</FieldLabel>
          <Input
            id="host-port"
            type="number"
            min={1}
            max={65535}
            disabled={pending}
            ref={field.ref}
            name={field.name}
            onBlur={field.onBlur}
            aria-invalid={fieldState.invalid}
            placeholder={String(inbound?.port ?? "")}
            value={field.value ?? ""}
            onChange={(event) =>
              field.onChange(
                event.target.value === "" ? null : event.target.valueAsNumber,
              )
            }
          />
          <FieldError errors={[fieldState.error]} />
        </Field>
      )}
    />
  );
}
