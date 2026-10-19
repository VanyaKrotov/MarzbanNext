import { useEffect } from "react";
import { Controller, useFormContext } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLabel } from "@/components/ui/field";
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
import {
  proxyALPN,
  proxyFingerprint,
  proxyHostSecurity,
} from "constants/Proxies";
import type { InboundType } from "types/Inbound";

import { HOST_BOOLEAN_FIELDS } from "../lib/constants";
import type { HostFormValues } from "../lib/form";
import { HostSelectField, HostTextField } from "./FormFields";

const UPLINK_HTTP_METHODS = [
  "POST",
  "GET",
  "PUT",
  "PATCH",
  "DELETE",
  "HEAD",
  "OPTIONS",
  "CONNECT",
  "TRACE",
];

export function AdvancedFields({
  pending,
  inbounds,
}: {
  pending: boolean;
  inbounds: InboundType[];
}) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const inboundTag = form.watch("inboundTag");
  const inbound = inbounds.find((item) => item.tag === inboundTag);
  const isXhttp =
    inbound?.network === "xhttp" || inbound?.network === "splithttp";

  useEffect(() => {
    if (!isXhttp) {
      form.setValue("sc_max_buffered_posts", null);
      form.setValue("x_padding_obfs_mode", null);
      form.setValue("uplink_http_method", null);
    }
  }, [form, isXhttp]);

  return (
    <section className="space-y-4 border-t pt-5">
      <h3 className="font-medium">{t("hostsDialog.advancedOptions")}</h3>
      <HostTextField
        id="host-sni"
        label={t("hostsDialog.sni")}
        placeholder="example.com"
        description={t("hostsDialog.sni.info")}
        disabled={pending}
        {...form.register("sni")}
      />
      <HostTextField
        id="host-request-host"
        label={t("hostsDialog.host")}
        placeholder="example.com"
        description={t("hostsDialog.host.info")}
        disabled={pending}
        {...form.register("host")}
      />
      <HostTextField
        id="host-path"
        label={t("hostsDialog.path")}
        placeholder="/vless"
        description={t("hostsDialog.path.info")}
        disabled={pending}
        {...form.register("path")}
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <HostSelectField
          name="security"
          label={t("hostsDialog.security")}
          description={t("hostsDialog.security.info")}
          options={proxyHostSecurity.map((option) => ({
            ...option,
            title:
              option.value === "inbound_default"
                ? t("hostsDialog.inboundDefault")
                : option.value === "none"
                  ? t("hostsDialog.noSecurity")
                  : option.title,
          }))}
          control={form.control}
          disabled={pending}
        />
        <HostSelectField
          name="alpn"
          label={t("hostsDialog.alpn")}
          options={proxyALPN}
          control={form.control}
          disabled={pending}
        />
        <HostSelectField
          name="fingerprint"
          label={t("hostsDialog.fingerprint")}
          options={proxyFingerprint}
          control={form.control}
          disabled={pending}
        />
      </div>
      <HostTextField
        id="host-fragment"
        label={t("hostsDialog.fragment")}
        placeholder="100-200,10-20,tlshello"
        description={t("hostsDialog.fragment.info")}
        disabled={pending}
        {...form.register("fragment_setting")}
      />
      <HostTextField
        id="host-noise"
        label={t("hostsDialog.noise")}
        placeholder="rand:10-20,10-20"
        description={t("hostsDialog.noise.info")}
        disabled={pending}
        {...form.register("noise_setting")}
      />

      {isXhttp ? (
        <div className="space-y-4 rounded-lg border p-4">
          <h4 className="font-medium">{t("hostsDialog.xhttpOptions")}</h4>
          <div className="grid gap-4 sm:grid-cols-2">
            <Controller
              name="sc_max_buffered_posts"
              control={form.control}
              render={({ field }) => (
                <Field>
                  <FieldLabel htmlFor="host-sc-max-buffered-posts">
                  {t("hostsDialog.scMaxBufferedPosts")}
                  </FieldLabel>
                  <Input
                    id="host-sc-max-buffered-posts"
                    type="number"
                    min="0"
                    placeholder="30"
                    disabled={pending}
                    value={field.value ?? ""}
                    onChange={(event) =>
                      field.onChange(
                        event.target.value ? event.target.valueAsNumber : null,
                      )
                    }
                  />
                </Field>
              )}
            />
            <Controller
              name="uplink_http_method"
              control={form.control}
              render={({ field }) => (
                <Field>
                  <FieldLabel htmlFor="host-uplink-http-method">
                    {t("hostsDialog.uplinkHttpMethod")}
                  </FieldLabel>
                  <Select
                    disabled={pending}
                    value={field.value ?? "__unset__"}
                    onValueChange={(value) =>
                      field.onChange(value === "__unset__" ? null : value)
                    }
                  >
                    <SelectTrigger id="host-uplink-http-method">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="__unset__">—</SelectItem>
                        {UPLINK_HTTP_METHODS.map((method) => (
                          <SelectItem key={method} value={method}>
                            {method}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
              )}
            />
          </div>
          <Controller
            name="x_padding_obfs_mode"
            control={form.control}
            render={({ field }) => (
              <Field orientation="horizontal" className="justify-between">
                <FieldLabel htmlFor="host-x-padding-obfs-mode">
                  {t("hostsDialog.xPaddingObfsMode")}
                </FieldLabel>
                <Switch
                  id="host-x-padding-obfs-mode"
                  checked={field.value === true}
                  disabled={pending}
                  onCheckedChange={(checked) =>
                    field.onChange(checked ? true : null)
                  }
                />
              </Field>
            )}
          />
          <p className="text-sm text-muted-foreground">
            {t("hostsDialog.uplinkHttpMethod.info")}
          </p>
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        {HOST_BOOLEAN_FIELDS.map(([name, label]) => (
          <Controller
            key={name}
            name={name}
            control={form.control}
            render={({ field }) => (
              <Field orientation="horizontal">
                <Checkbox
                  id={`host-${name}`}
                  checked={Boolean(field.value)}
                  disabled={pending}
                  onCheckedChange={(checked) =>
                    field.onChange(checked === true)
                  }
                />
                <FieldLabel htmlFor={`host-${name}`}>{t(label)}</FieldLabel>
              </Field>
            )}
          />
        ))}
      </div>
    </section>
  );
}
