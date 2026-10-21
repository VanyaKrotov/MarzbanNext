import { isAxiosError } from "axios";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
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
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { useHostsQuery } from "@/pages/hosts-page/lib/query";
import { api } from "@/service/http";
import type { SubscriptionFormat } from "../lib/formats";

type PreviewUser = { id: number; username: string };
type Values = { user: PreviewUser | null; recipient: number | null };
type PreviewResult = {
  body: string;
  media_type: string;
  diagnostics: { host_id: number; reason: string }[];
};

export function TemplatePreview({
  format,
  getContent,
  disabled,
}: {
  format: SubscriptionFormat;
  getContent: () => string;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const form = useForm<Values>({
    defaultValues: { user: null, recipient: null },
  });
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const users = useQuery({
    queryKey: ["subscription-template-preview-users", deferredSearch],
    queryFn: ({ signal }) =>
      api.get<PreviewUser[]>("/subscription-templates/preview-users", {
        signal,
        params: { search: deferredSearch },
      }),
  });
  const hosts = useHostsQuery();
  const hostNames = useMemo(
    () => new Map(hosts.data?.map((host) => [host.id, host.remark])),
    [hosts.data],
  );
  const hostIds = useMemo(() => Array.from(hostNames.keys()), [hostNames]);
  const preview = useMutation({
    mutationFn: (values: Values) =>
      api.post<PreviewResult>("/subscription-templates/preview", {
        format,
        content: getContent(),
        user_id: values.user!.id,
        recipient_host_id: values.recipient,
      }),
  });
  const detail = isAxiosError(preview.error)
    ? preview.error.response?.data?.detail
    : undefined;
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Controller
          control={form.control}
          name="user"
          rules={{ required: true }}
          render={({ field, fieldState }) => (
            <Field>
              <FieldLabel htmlFor="template-preview-user">
                {t("templateComposition.user")}
              </FieldLabel>
              <Combobox<PreviewUser>
                items={users.data ?? []}
                value={field.value}
                onValueChange={field.onChange}
                inputValue={search}
                onInputValueChange={setSearch}
                itemToStringLabel={(user) => user.username}
                isItemEqualToValue={(a, b) => a.id === b.id}
              >
                <ComboboxInput
                  id="template-preview-user"
                  aria-invalid={fieldState.invalid}
                />
                <ComboboxContent>
                  <ComboboxEmpty>
                    {t("subscriptionTemplates.empty")}
                  </ComboboxEmpty>
                  <ComboboxList>
                    {(user: PreviewUser) => (
                      <ComboboxItem key={user.id} value={user}>
                        {user.username}
                      </ComboboxItem>
                    )}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>
              <FieldError
                errors={
                  fieldState.invalid
                    ? [{ message: t("templateComposition.chooseUser") }]
                    : []
                }
              />
            </Field>
          )}
        />
        <Controller
          control={form.control}
          name="recipient"
          render={({ field }) => (
            <Field>
              <FieldLabel htmlFor="template-preview-recipient">
                {t("templateComposition.recipient")}
              </FieldLabel>
              <Combobox<number>
                items={hostIds}
                value={field.value}
                onValueChange={field.onChange}
                itemToStringLabel={(id) => `${id}: ${hostNames.get(id) ?? id}`}
              >
                <ComboboxInput id="template-preview-recipient" showClear />
                <ComboboxContent>
                  <ComboboxEmpty>
                    {t("subscriptionTemplates.empty")}
                  </ComboboxEmpty>
                  <ComboboxList>
                    {(id: number) => (
                      <ComboboxItem key={id} value={id}>
                        {id}: {hostNames.get(id)}
                      </ComboboxItem>
                    )}
                  </ComboboxList>
                </ComboboxContent>
              </Combobox>
            </Field>
          )}
        />
      </div>
      {(users.isError || hosts.isError) && (
        <p role="alert">{t("templateComposition.loadError")}</p>
      )}
      <Button
        type="button"
        variant="outline"
        className="self-start"
        disabled={disabled || preview.isPending}
        onClick={() =>
          void form.handleSubmit((values) => preview.mutate(values))()
        }
      >
        {t(preview.isPending ? "loading" : "templateComposition.preview")}
      </Button>
      {preview.isError && (
        <p role="alert" className="text-sm text-destructive">
          {typeof detail === "string"
            ? detail
            : t("subscriptionTemplates.saveError")}
        </p>
      )}
      {preview.data && (
        <>
          <Field>
            <FieldLabel htmlFor="template-preview-result">
              {t("templateComposition.result")}
            </FieldLabel>
            <Textarea
              id="template-preview-result"
              value={preview.data.body || t("templateComposition.empty")}
              readOnly
              rows={12}
              dir="ltr"
              className="font-mono text-xs"
            />
          </Field>
          {preview.data.diagnostics.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-medium">
                {t("templateComposition.diagnostics")}
              </h3>
              <ul className="max-h-48 overflow-auto text-sm">
                {preview.data.diagnostics.map((item, index) => (
                  <li key={`${item.host_id}-${index}`}>
                    {item.host_id}:{" "}
                    {t(`templateComposition.${item.reason}`, {
                      defaultValue: item.reason,
                    })}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
