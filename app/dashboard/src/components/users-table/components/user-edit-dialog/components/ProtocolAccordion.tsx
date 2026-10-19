import { Dices } from "lucide-react";
import { forwardRef, useId, useState } from "react";
import { Controller, useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldLabel,
  FieldLegend,
  FieldSet,
  FieldTitle,
} from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { shadowsocksMethods, XTLSFlows } from "constants/Proxies";
import {
  InboundType,
  InboundsMap,
  ProtocolType,
} from "types/Inbound";

import type { UserFormValues } from "../lib/form";
import {
  generateProxyId,
  generateProxyPassword,
} from "../lib/generators";

type ProtocolOption = {
  title: ProtocolType;
  description: string;
};

type ProtocolAccordionProps = {
  disabled?: boolean;
  options: ProtocolOption[];
  availableInbounds: InboundsMap;
};

export function ProtocolAccordion({
  disabled = false,
  options,
  availableInbounds,
}: ProtocolAccordionProps) {
  const { t } = useTranslation();
  const form = useFormContext<UserFormValues>();
  const selectedInbounds =
    useWatch({
      control: form.control,
      name: "inbounds",
    }) ?? {};
  const [expandedProtocols, setExpandedProtocols] = useState<string[]>([]);

  return (
    <Accordion
      type="multiple"
      value={expandedProtocols}
      onValueChange={setExpandedProtocols}
      className="gap-2"
    >
      {options.map(({ title, description }) => {
        const protocolInbounds = availableInbounds.get(title) ?? [];
        const canEnable = protocolInbounds.length > 0;
        const protocolEnabled = Array.isArray(selectedInbounds[title]);
        const selectedCount = selectedInbounds[title]?.length ?? 0;

        return (
          <AccordionItem
            value={title}
            key={title}
            className={cn(
              "overflow-hidden rounded-lg border bg-card transition-colors not-last:border-b",
              {
                ["border-primary/40 bg-primary/3"]: protocolEnabled,
                ["opacity-55"]: !canEnable,
              },
            )}
          >
            <div className="px-3">
              <AccordionTrigger
                disabled={!canEnable}
                className="min-w-0 py-3 hover:no-underline"
              >
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 capitalize">
                    {title}
                    {protocolEnabled && (
                      <Badge variant="secondary" className="font-normal">
                        {selectedCount}/{protocolInbounds.length}
                      </Badge>
                    )}
                  </span>
                  <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                    {description}
                  </span>
                </span>
              </AccordionTrigger>
            </div>

            <AccordionContent className="border-t bg-muted/20 px-3 pt-3">
              <div className="space-y-4">
                <ProtocolSwitch
                  protocol={title}
                  disabled={disabled}
                  checked={protocolEnabled}
                  inboundTags={protocolInbounds.map((inbound) => inbound.tag)}
                />

                <FieldSet className="gap-3">
                  <FieldLegend variant="label">
                    {t("userDialog.inbounds")}
                  </FieldLegend>
                  <Controller
                    name={`inbounds.${title}`}
                    control={form.control}
                    render={({ field }) => (
                      <div className="grid gap-2">
                        {protocolInbounds.map((inbound) => {
                          const checked = (field.value ?? []).includes(
                            inbound.tag,
                          );

                          return (
                            <InboundOption
                              key={inbound.tag}
                              inbound={inbound}
                              checked={checked}
                              disabled={disabled || !protocolEnabled}
                              onBlur={field.onBlur}
                              onCheckedChange={(enabled) => {
                                const current = field.value ?? [];
                                field.onChange(
                                  enabled
                                    ? Array.from(
                                        new Set([...current, inbound.tag]),
                                      )
                                    : current.filter(
                                        (value) => value !== inbound.tag,
                                      ),
                                );
                              }}
                            />
                          );
                        })}
                      </div>
                    )}
                  />
                </FieldSet>

                {protocolEnabled && (
                  <ProtocolFields protocol={title} disabled={disabled} />
                )}
              </div>
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}

function ProtocolSwitch({
  protocol,
  checked,
  disabled,
  inboundTags,
}: {
  protocol: ProtocolType;
  checked: boolean;
  disabled: boolean;
  inboundTags: string[];
}) {
  const { t } = useTranslation();
  const form = useFormContext<UserFormValues>();
  const id = `protocol-${protocol}-enabled`;

  return (
    <Field orientation="horizontal" className="justify-between gap-4">
      <FieldLabel htmlFor={id} className="min-w-0">
        {t(
          checked
            ? "userDialog.protocolEnabled"
            : "userDialog.protocolDisabled",
        )}
      </FieldLabel>
      <Switch
        id={id}
        checked={checked}
        disabled={disabled}
        onCheckedChange={(enabled) => {
          const current = form.getValues("inbounds") ?? {};

          if (enabled) {
            form.setValue(
              "inbounds",
              {
                ...current,
                [protocol]: inboundTags,
              },
              { shouldDirty: true, shouldValidate: true },
            );
            return;
          }

          const { [protocol]: _removed, ...next } = current;
          form.setValue("inbounds", next, {
            shouldDirty: true,
            shouldValidate: true,
          });
        }}
      />
    </Field>
  );
}

function InboundOption({
  inbound,
  checked,
  disabled,
  onBlur,
  onCheckedChange,
}: {
  inbound: InboundType;
  checked: boolean;
  disabled: boolean;
  onBlur: () => void;
  onCheckedChange: (checked: boolean) => void;
}) {
  const id = `inbound-${useId().replaceAll(":", "")}`;

  return (
    <FieldLabel>
      <Field orientation="horizontal">
        <Checkbox
          id={id}
          checked={checked}
          disabled={disabled}
          onBlur={onBlur}
          onCheckedChange={(value) => onCheckedChange(value === true)}
        />
        <FieldTitle>
          <span className="min-w-0 flex-1 truncate">
            {inbound.tag}{" "}
            <span className="text-muted-foreground">({inbound.network})</span>
          </span>
          {inbound.tls && inbound.tls !== "none" && (
            <Badge variant="outline" className="uppercase">
              {inbound.tls}
            </Badge>
          )}
        </FieldTitle>
      </Field>
    </FieldLabel>
  );
}

interface ProtocolFieldsProps {
  protocol: ProtocolType;
  disabled: boolean;
}

function ProtocolFields({ protocol, disabled }: ProtocolFieldsProps) {
  const { t } = useTranslation();
  const form = useFormContext<UserFormValues>();
  const fieldPrefix = `proxy-${protocol}`;

  if (protocol === "vmess") {
    return (
      <Field>
        <FieldLabel htmlFor={`${fieldPrefix}-id`}>ID</FieldLabel>
        <Controller
          control={form.control}
          name="proxies.vmess.id"
          render={({ field }) => (
            <GeneratedInput
              id={`${fieldPrefix}-id`}
              disabled={disabled}
              onGenerate={() => field.onChange(generateProxyId())}
              {...field}
            />
          )}
        />
      </Field>
    );
  }

  if (protocol === "vless") {
    return (
      <div className="grid gap-4">
        <Field>
          <FieldLabel htmlFor={`${fieldPrefix}-id`}>ID</FieldLabel>
          <Controller
            control={form.control}
            name="proxies.vless.id"
            render={({ field }) => (
              <GeneratedInput
                id={`${fieldPrefix}-id`}
                disabled={disabled}
                onGenerate={() => field.onChange(generateProxyId())}
                {...field}
              />
            )}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor={`${fieldPrefix}-flow`}>
            {t("userDialog.flow")}
          </FieldLabel>
          <Controller
            control={form.control}
            name="proxies.vless.flow"
            render={({ field }) => (
              <Select
                disabled={disabled}
                value={field.value || "none"}
                onValueChange={(value) =>
                  field.onChange(value === "none" ? "" : value)
                }
              >
                <SelectTrigger id={`${fieldPrefix}-flow`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {XTLSFlows.map((flow) => (
                      <SelectItem
                        key={flow.value || "none"}
                        value={flow.value || "none"}
                      >
                        {flow.value ? flow.title : t("common.none")}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            )}
          />
        </Field>
      </div>
    );
  }

  if (protocol === "trojan") {
    return (
      <Field>
        <FieldLabel htmlFor={`${fieldPrefix}-password`}>
          {t("password")}
        </FieldLabel>
        <Controller
          control={form.control}
          name="proxies.trojan.password"
          render={({ field }) => (
            <GeneratedInput
              id={`${fieldPrefix}-password`}
              disabled={disabled}
              onGenerate={() => field.onChange(generateProxyPassword())}
              {...field}
            />
          )}
        />
      </Field>
    );
  }

  if (protocol === "hysteria") {
    return (
      <Field>
        <FieldLabel htmlFor={`${fieldPrefix}-auth`}>
          {t("userDialog.auth")}
        </FieldLabel>
        <Controller
          control={form.control}
          name="proxies.hysteria.auth"
          render={({ field }) => (
            <GeneratedInput
              id={`${fieldPrefix}-auth`}
              disabled={disabled}
              onGenerate={() => field.onChange(generateProxyPassword())}
              {...field}
            />
          )}
        />
      </Field>
    );
  }

  return (
    <div className="grid gap-4">
      <Field>
        <FieldLabel htmlFor={`${fieldPrefix}-password`}>
          {t("password")}
        </FieldLabel>
        <Controller
          control={form.control}
          name="proxies.shadowsocks.password"
          render={({ field }) => (
            <GeneratedInput
              id={`${fieldPrefix}-password`}
              disabled={disabled}
              onGenerate={() => {
                field.onChange(generateProxyPassword());
              }}
              {...field}
            />
          )}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor={`${fieldPrefix}-method`}>
          {t("userDialog.method")}
        </FieldLabel>
        <Controller
          control={form.control}
          name="proxies.shadowsocks.method"
          render={({ field }) => (
            <Select
              disabled={disabled}
              value={field.value}
              onValueChange={(value) => field.onChange(value)}
            >
              <SelectTrigger id={`${fieldPrefix}-method`} className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {shadowsocksMethods.map((method) => (
                    <SelectItem key={method} value={method}>
                      {method}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          )}
        />
      </Field>
    </div>
  );
}

const GeneratedInput = forwardRef<
  HTMLInputElement,
  React.ComponentProps<"input"> & { onGenerate: () => void }
>(({ onGenerate, ...props }, ref) => {
  const { t } = useTranslation();

  return (
    <InputGroup>
      <InputGroupInput
        ref={ref}
        placeholder={t("userDialog.generatedByDefault")}
        {...props}
      />
      <InputGroupAddon align="inline-end">
        <InputGroupButton
          size="icon-xs"
          type="button"
          aria-label={t("userDialog.generateValue")}
          title={t("userDialog.generateValue")}
          onClick={onGenerate}
          disabled={props.disabled}
        >
          <Dices />
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  );
});
