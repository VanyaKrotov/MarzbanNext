import { zodResolver } from "@hookform/resolvers/zod";
import { Braces, LoaderCircle } from "lucide-react";
import { useMemo } from "react";
import {
  Controller,
  FormProvider,
  useForm,
  useFormContext,
  useWatch,
} from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import i18n from "@/locales/i18n";
import set from "lodash/set";

import { Button } from "@/components/ui/button";
import { MonacoJsonEditor } from "@/components/MonacoJsonEditor";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";

import { createXrayInboundSchema } from "@/lib/xray-schemas/inbound";
import { useNodeCertificatesQuery } from "@/pages/nodes-page/lib/query";
import type { InboundConfig, InboundPayload } from "../../lib/inbounds-query";
import { tryParseInbound } from "./selectors";
import CertificateHelper from "./CertificateHelper";
import ShortIdsHelper from "./ShortIdsHelper";
import TlsCertificateHelper from "./TlsCertificateHelper";
import X25519Helpers from "./X25519Helpers";

const inboundFormSchema = z.object({
  enabled: z.boolean(),
  auto_assign_users: z.boolean(),
  content: z.string().superRefine((value, context) => {
    try {
      const parsed = JSON.parse(value);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        context.addIssue({
          code: "custom",
          message: "JSON must contain an object",
        });
      }

      if (
        typeof parsed === "object" &&
        parsed !== null &&
        !Array.isArray(parsed) &&
        (typeof parsed.tag !== "string" || !parsed.tag.trim())
      ) {
        context.addIssue({
          code: "custom",
          message: "JSON must contain a non-empty tag",
        });
      }
    } catch {
      context.addIssue({ code: "custom", message: i18n.t("validation.json") });
    }
  }),
});

type InboundFormValues = z.infer<typeof inboundFormSchema>;

type InboundDialogProps = {
  inbound: InboundConfig | null;
  nodeId: number;
  open: boolean;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: InboundPayload) => void;
};

const defaultContent = {
  tag: "",
  listen: "0.0.0.0",
  port: 443,
  protocol: "vless",
  settings: {
    clients: [],
    decryption: "none",
  },
  streamSettings: {
    network: "tcp",
    security: "none",
  },
};

export function InboundDialog({
  inbound,
  nodeId,
  open,
  pending,
  onOpenChange,
  onSubmit,
}: InboundDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-3xl">
        <InboundDialogContent
          inbound={inbound}
          nodeId={nodeId}
          pending={pending}
          onSubmit={onSubmit}
        />
      </DialogContent>
    </Dialog>
  );
}

function InboundDialogContent({
  inbound,
  nodeId,
  pending,
  onSubmit,
}: Pick<InboundDialogProps, "inbound" | "nodeId" | "pending" | "onSubmit">) {
  const { t } = useTranslation();
  const readonly = inbound?.readonly ?? false;
  const certificatesQuery = useNodeCertificatesQuery(nodeId);
  const inboundSchema = useMemo(
    () =>
      createXrayInboundSchema({
        certificateFiles: certificatesQuery.data?.map(
          ({ certificate_file }) => certificate_file,
        ),
        keyFiles: certificatesQuery.data?.map(({ key_file }) => key_file),
      }),
    [certificatesQuery.data],
  );
  const form = useForm<InboundFormValues>({
    resolver: zodResolver(inboundFormSchema),
    defaultValues: {
      enabled: inbound?.enabled ?? true,
      auto_assign_users: true,
      content: JSON.stringify(inbound?.content ?? defaultContent, null, 2),
    },
  });

  const submit = (values: InboundFormValues) => {
    const content = JSON.parse(values.content) as Record<string, unknown>;

    onSubmit({
      enabled: values.enabled,
      auto_assign_users: inbound ? undefined : values.auto_assign_users,
      node_ids: inbound?.node_ids ?? [nodeId],
      content,
    });
  };

  return (
    <FormProvider {...form}>
      <>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Braces className="size-5 text-primary" />
            {t(inbound ? "inboundsPage.editTitle" : "inboundsPage.createTitle")}
          </DialogTitle>
          <DialogDescription>
            {t(
              readonly
                ? "inboundsPage.readonlyDescription"
                : "inboundsPage.dialogDescription",
            )}
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-5" onSubmit={form.handleSubmit(submit)}>
          <Controller
            control={form.control}
            name="content"
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="inbound-content">
                  {t("inboundsPage.content")}
                </FieldLabel>
                <MonacoJsonEditor
                  id="inbound-content"
                  value={field.value}
                  onChange={field.onChange}
                  schema={inboundSchema}
                  schemaUri="https://marzban.local/schemas/xray-inbound.json"
                  className="min-h-96"
                  disabled={pending || readonly}
                  invalid={fieldState.invalid}
                />
                <FieldError errors={[fieldState.error]} />
                <InboundHelpers nodeId={nodeId} />
              </Field>
            )}
          />

          {!inbound && (
            <Controller
              control={form.control}
              name="auto_assign_users"
              render={({ field }) => (
                <Field orientation="horizontal" className="min-h-9">
                  <Switch
                    id="inbound-auto-assign-users"
                    checked={field.value}
                    disabled={pending}
                    onCheckedChange={field.onChange}
                  />
                  <FieldLabel
                    htmlFor="inbound-auto-assign-users"
                    className="min-w-0"
                  >
                    {t("inboundsPage.autoAssignUsers")}
                  </FieldLabel>
                </Field>
              )}
            />
          )}

          <div className="flex items-center justify-between gap-4">
            <Controller
              control={form.control}
              name="enabled"
              render={({ field }) => (
                <Field orientation="horizontal" className="min-h-9">
                  <Switch
                    id="inbound-enabled"
                    checked={field.value}
                    disabled={pending}
                    onCheckedChange={field.onChange}
                  />
                  <FieldLabel htmlFor="inbound-enabled" className="min-w-0">
                    {t(
                      field.value
                        ? "inboundsPage.enabledState"
                        : "inboundsPage.disabledState",
                    )}
                  </FieldLabel>
                </Field>
              )}
            />
            <Button type="submit" disabled={pending}>
              {pending && <LoaderCircle className="animate-spin" />}
              {t(inbound ? "core.save" : "create")}
            </Button>
          </div>
        </form>
      </>
    </FormProvider>
  );
}

function InboundHelpers({ nodeId }: { nodeId: number }) {
  const { control, setValue } = useFormContext<InboundFormValues>();

  const value = useWatch({
    control,
    name: "content",
  });

  const { inbound, helpers } = useMemo(() => {
    const inbound = tryParseInbound(value);
    if (!inbound) {
      return { inbound, helpers: [] };
    }

    const helpers = [];
    switch (inbound.streamSettings?.security) {
      case "tls":
        helpers.push("certificate", "tlsCertificate");
        break;
      case "reality":
        helpers.push("shortIds", "x25519");
        break;
    }

    return { inbound, helpers };
  }, [value]);

  if (!helpers.length) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {helpers.map((type) => {
        if (type === "shortIds") {
          return (
            <ShortIdsHelper
              key={type}
              onSet={(ids) => {
                const res = set(
                  inbound!,
                  "streamSettings.realitySettings.shortIds",
                  ids,
                );

                setValue("content", JSON.stringify(res, null, 2));
              }}
            />
          );
        }

        if (type === "x25519") {
          return (
            <X25519Helpers
              key={type}
              onSet={(publicKey, privateKey) => {
                let res = set(
                  inbound!,
                  "streamSettings.realitySettings.publicKey",
                  publicKey,
                );
                res = set(
                  inbound!,
                  "streamSettings.realitySettings.privateKey",
                  privateKey,
                );

                setValue("content", JSON.stringify(res, null, 2));
              }}
            />
          );
        }

        if (type === "certificate") {
          const certificates =
            inbound?.streamSettings?.tlsSettings?.certificates ?? [];

          return (
            <CertificateHelper
              key={type}
              nodeId={nodeId}
              checkSelected={(cert) =>
                certificates!.some(
                  (x) =>
                    x.certificateFile === cert.certificate_file &&
                    x.keyFile === cert.key_file,
                )
              }
              onSet={(certificateFile, keyFile) => {
                const res = set(
                  inbound!,
                  "streamSettings.tlsSettings.certificates",
                  [{ certificateFile, keyFile }],
                );

                setValue("content", JSON.stringify(res, null, 2));
              }}
            />
          );
        }

        if (type === "tlsCertificate") {
          const serverName = inbound?.streamSettings?.tlsSettings?.serverName;

          return (
            <TlsCertificateHelper
              key={type}
              serverName={typeof serverName === "string" ? serverName : undefined}
              onSet={(certificate, key) => {
                const res = set(
                  inbound!,
                  "streamSettings.tlsSettings.certificates",
                  [{ certificate, key }],
                );

                setValue("content", JSON.stringify(res, null, 2));
              }}
            />
          );
        }
      })}
    </div>
  );
}
