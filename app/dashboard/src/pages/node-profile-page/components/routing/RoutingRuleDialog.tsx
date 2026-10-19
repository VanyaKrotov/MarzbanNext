import { zodResolver } from "@hookform/resolvers/zod";
import { Braces, LoaderCircle } from "lucide-react";
import { useMemo } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import i18n from "@/locales/i18n";

import { MonacoJsonEditor } from "@/components/MonacoJsonEditor";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";

import { useNodeGeoResourcesQuery } from "../geo-resources/query";
import {
  type RoutingRule,
  type RoutingRulePayload,
  useRoutingInboundsQuery,
  useRoutingOutboundsQuery,
} from "../../lib/routing-query";
import { createXrayRoutingRuleSchema } from "./xray-routing-rule-schema";

const formSchema = z.object({
  enabled: z.boolean(),
  content: z.string().superRefine((value, context) => {
    try {
      const parsed = JSON.parse(value);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        context.addIssue({
          code: "custom",
          message: "JSON must contain an object",
        });
        return;
      }
      const ruleTag = (parsed as Record<string, unknown>).ruleTag;
      if (typeof ruleTag !== "string" || !ruleTag.trim()) {
        context.addIssue({
          code: "custom",
          message: "JSON must contain a non-empty ruleTag",
        });
      } else if (ruleTag.trim().length > 128) {
        context.addIssue({
          code: "custom",
          message: "ruleTag cannot be longer than 128 characters",
        });
      }
    } catch {
      context.addIssue({ code: "custom", message: i18n.t("validation.json") });
    }
  }),
});

type FormValues = z.infer<typeof formSchema>;

type RoutingRuleDialogProps = {
  rule: RoutingRule | null;
  nodeId: number;
  open: boolean;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: RoutingRulePayload) => void;
};

export function RoutingRuleDialog({
  rule,
  nodeId,
  open,
  pending,
  onOpenChange,
  onSubmit,
}: RoutingRuleDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-3xl">
        <RoutingRuleDialogContent
          rule={rule}
          nodeId={nodeId}
          pending={pending}
          onSubmit={onSubmit}
        />
      </DialogContent>
    </Dialog>
  );
}

function RoutingRuleDialogContent({
  rule,
  nodeId,
  pending,
  onSubmit,
}: Pick<
  RoutingRuleDialogProps,
  | "rule"
  | "nodeId"
  | "pending"
  | "onSubmit"
>) {
  const { t } = useTranslation();
  const inboundsQuery = useRoutingInboundsQuery(nodeId);
  const outboundsQuery = useRoutingOutboundsQuery(nodeId);
  const geoResourcesQuery = useNodeGeoResourcesQuery(nodeId);
  const inboundTags = useMemo(
    () =>
      (inboundsQuery.data ?? [])
        .filter((item) => item.node_ids.includes(nodeId) && item.enabled)
        .map((item) => item.tag),
    [inboundsQuery.data, nodeId],
  );
  const outboundTags = useMemo(
    () =>
      (outboundsQuery.data ?? [])
        .filter((item) => item.node_ids.includes(nodeId) && item.enabled)
        .map((item) => item.tag),
    [outboundsQuery.data, nodeId],
  );
  const geoResourceFilenames = (geoResourcesQuery.data ?? []).map(
    (item) => item.filename,
  );
  const readonly = rule?.readonly ?? false;
  const schema = useMemo(
    () =>
      createXrayRoutingRuleSchema(
        inboundTags,
        outboundTags,
        geoResourceFilenames,
      ),
    [geoResourceFilenames, inboundTags, outboundTags],
  );
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      enabled: rule?.enabled ?? true,
      content: JSON.stringify(
        rule?.content ?? {
          ruleTag: "",
          type: "field",
          inboundTag: [],
          outboundTag: outboundTags[0] ?? "DIRECT",
        },
        null,
        2,
      ),
    },
  });

  const submit = (values: FormValues) => {
    onSubmit({
      enabled: values.enabled,
      node_ids: rule?.node_ids ?? [nodeId],
      content: JSON.parse(values.content) as Record<string, unknown>,
    });
  };

  return (
    <>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Braces className="size-5 text-primary" />
            {t(
              rule
                ? "routingPage.editTitle"
                : "routingPage.createTitle",
            )}
          </DialogTitle>
          <DialogDescription>
            {t(
              readonly
                ? "routingPage.readonlyDescription"
                : "routingPage.dialogDescription",
            )}
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-5" onSubmit={form.handleSubmit(submit)}>
          <div className="flex justify-end">
            <Controller
              control={form.control}
              name="enabled"
              render={({ field }) => (
                <Field orientation="horizontal" className="h-9">
                  <Switch
                    id="routing-rule-enabled"
                    checked={field.value}
                    disabled={pending}
                    onCheckedChange={field.onChange}
                  />
                  <FieldLabel htmlFor="routing-rule-enabled">
                    {t(field.value ? "enabled" : "disabled")}
                  </FieldLabel>
                </Field>
              )}
            />
          </div>

          <Controller
            control={form.control}
            name="content"
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="routing-rule-content">
                  {t("routingPage.content")}
                </FieldLabel>
                <MonacoJsonEditor
                  id="routing-rule-content"
                  value={field.value}
                  onChange={field.onChange}
                  schema={schema}
                  schemaUri="https://marzban.local/schemas/xray-routing-rule.json"
                  className="min-h-96"
                  disabled={pending || readonly}
                  invalid={fieldState.invalid}
                />
                <FieldError errors={[fieldState.error]} />
              </Field>
            )}
          />

          <div className="flex justify-end">
            <Button type="submit" disabled={pending}>
              {pending && <LoaderCircle className="animate-spin" />}
              {t(rule ? "core.save" : "create")}
            </Button>
          </div>
        </form>
    </>
  );
}
