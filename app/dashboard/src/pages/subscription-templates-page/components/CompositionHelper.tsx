import { useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  useHostGroupsQuery,
  useHostsQuery,
} from "@/pages/hosts-page/lib/query";
import type { SubscriptionFormat } from "../lib/formats";
import { compositionExample } from "../lib/composition";
import { SourcePicker, type SourceOption } from "./SourcePicker";

type Values = {
  type: "ids" | "groups";
  hosts: SourceOption[];
  groups: SourceOption[];
};

export function CompositionHelper({
  format,
  onInsert,
  disabled,
}: {
  format: SubscriptionFormat;
  onInsert: (content: string) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const hosts = useHostsQuery();
  const groups = useHostGroupsQuery();
  const form = useForm<Values>({
    defaultValues: { type: "ids", hosts: [], groups: [] },
  });
  const type = form.watch("type");
  const selection = form.watch(type === "ids" ? "hosts" : "groups");
  const hostOptions = useMemo(
    () =>
      hosts.data?.map((host) => ({
        id: String(host.id),
        label: `${host.id}: ${host.remark}`,
      })) ?? [],
    [hosts.data],
  );
  const groupOptions = useMemo(
    () =>
      groups.data?.map((group) => ({ id: group.id, label: group.name })) ?? [],
    [groups.data],
  );
  const [example, setExample] = useState<string | null>(null);
  const insert = form.handleSubmit((values) =>
    setExample(
      compositionExample(
        format,
        values.type === "ids"
          ? { type: "ids", values: values.hosts.map((host) => Number(host.id)) }
          : { type: "groups", values: values.groups.map((group) => group.id) },
      ),
    ),
  );
  return (
    <div className="flex flex-col gap-3">
      <Field>
        <FieldLabel htmlFor="composition-source-type">
          {t("templateComposition.sources")}
        </FieldLabel>
        <Controller
          control={form.control}
          name="type"
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger id="composition-source-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="ids">
                    {t("templateComposition.hosts")}
                  </SelectItem>
                  <SelectItem value="groups">
                    {t("templateComposition.groups")}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          )}
        />
      </Field>
      <Controller
        control={form.control}
        name={type === "ids" ? "hosts" : "groups"}
        render={({ field }) => (
          <SourcePicker
            label={t(
              type === "ids"
                ? "templateComposition.hosts"
                : "templateComposition.groups",
            )}
            value={field.value}
            onChange={field.onChange}
            options={type === "ids" ? hostOptions : groupOptions}
            disabled={disabled || hosts.isLoading || groups.isLoading}
          />
        )}
      />
      {(hosts.isError || groups.isError) && (
        <p role="alert">{t("templateComposition.loadError")}</p>
      )}
      <Button
        type="button"
        variant="outline"
        className="self-start"
        disabled={disabled || !selection.length}
        onClick={() => void insert()}
      >
        {t("templateComposition.insert")}
      </Button>
      <AlertDialog
        open={example !== null}
        onOpenChange={(open) => {
          if (!open) setExample(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("templateComposition.replaceTitle")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("templateComposition.replaceDescription")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (example !== null) onInsert(example);
                setExample(null);
              }}
            >
              {t("templateComposition.insert")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
