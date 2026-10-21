import { isAxiosError } from "axios";
import { zodResolver } from "@hookform/resolvers/zod";
import { useCallback, useEffect, useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { MonacoJsonEditor } from "@/components/MonacoJsonEditor";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/service/http";
import {
  generateErrorMessage,
  generateSuccessMessage,
} from "@/utils/toastHandler";

import { initialTemplateContent } from "../lib/content";
import {
  formatLabelKeys,
  subscriptionFormats,
  useTemplateMutation,
  useTemplateQuery,
  type SubscriptionTemplate,
  type TemplateDocument,
  type SubscriptionFormat,
} from "../lib/query";

const schema = z.object({
  name: z.string().trim().min(1).max(128),
  format: z.enum(subscriptionFormats),
  content: z.string().min(1),
});
type Values = z.infer<typeof schema>;

export function TemplateDialog({
  template,
  open,
  onOpenChange,
}: {
  template: SubscriptionTemplate | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [confirmClose, setConfirmClose] = useState(false);
  const status = useRef({ dirty: false, pending: false });
  const onStatus = useCallback((dirty: boolean, pending: boolean) => {
    status.current = { dirty, pending };
  }, []);
  useEffect(() => {
    if (!open) {
      status.current = { dirty: false, pending: false };
      setConfirmClose(false);
    }
  }, [open]);
  const requestClose = () => {
    if (status.current.pending) return;
    if (status.current.dirty) setConfirmClose(true);
    else onOpenChange(false);
  };
  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(next) => (next ? onOpenChange(true) : requestClose())}
      >
        <DialogContent
          aria-describedby={undefined}
          className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-4xl"
        >
          <TemplateLoader
            template={template}
            onSaved={() => onOpenChange(false)}
            onDiscard={requestClose}
            onStatus={onStatus}
          />
        </DialogContent>
      </Dialog>
      <DiscardDialog
        open={confirmClose}
        onOpenChange={setConfirmClose}
        onDiscard={() => onOpenChange(false)}
      />
    </>
  );
}

function DiscardDialog({
  open,
  onOpenChange,
  onDiscard,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDiscard: () => void;
}) {
  const { t } = useTranslation();
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {t("subscriptionTemplates.discardTitle")}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {t("subscriptionTemplates.discardDescription")}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
          <AlertDialogAction onClick={onDiscard}>
            {t("actions.discard")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function TemplateLoader({
  template,
  onSaved,
  onDiscard,
  onStatus,
}: {
  template: SubscriptionTemplate | null;
  onSaved: () => void;
  onDiscard: () => void;
  onStatus: (dirty: boolean, pending: boolean) => void;
}) {
  const { t } = useTranslation();
  const query = useTemplateQuery(template?.id);
  if (template && !query.isFetchedAfterMount)
    return (
      <>
        <DialogTitle className="sr-only">
          {t("subscriptionTemplates.editTitle")}
        </DialogTitle>
        <Skeleton className="h-96" />
      </>
    );
  if (template && !query.data)
    return (
      <>
        <DialogTitle>{t("subscriptionTemplates.editTitle")}</DialogTitle>
        <DialogDescription role="alert">
          {t("subscriptionTemplates.loadError")}
        </DialogDescription>
      </>
    );
  return (
    <TemplateForm
      key={template?.id ?? "new"}
      template={query.data}
      onSaved={onSaved}
      onDiscard={onDiscard}
      onStatus={onStatus}
    />
  );
}

function TemplateForm({
  template,
  onSaved,
  onDiscard,
  onStatus,
}: {
  template?: TemplateDocument;
  onSaved: () => void;
  onDiscard: () => void;
  onStatus: (dirty: boolean, pending: boolean) => void;
}) {
  const { t } = useTranslation();
  const editing = Boolean(template);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: template?.name ?? "",
      format: template?.format ?? "v2ray-json",
      content: template?.content ?? initialTemplateContent["v2ray-json"],
    },
  });
  const mutation = useTemplateMutation((values: Values) =>
    editing
      ? api.patch(`/subscription-templates/${template!.id}`, values)
      : api.post("/subscription-templates", values),
  );
  useEffect(() => {
    onStatus(form.formState.isDirty, mutation.isPending);
  }, [form.formState.isDirty, mutation.isPending, onStatus]);
  const format = form.watch("format");
  const submit = form.handleSubmit((values) =>
    mutation.mutate(values, {
      onSuccess: () => {
        generateSuccessMessage(t("subscriptionTemplates.saved"));
        onSaved();
      },
      onError: (error) => {
        const detail = isAxiosError(error)
          ? error.response?.data?.detail
          : undefined;
        form.setError("root", {
          message:
            typeof detail === "string"
              ? detail
              : t("subscriptionTemplates.saveError"),
        });
        generateErrorMessage(error, form);
      },
    }),
  );
  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {t(
            editing
              ? "subscriptionTemplates.editTitle"
              : "subscriptionTemplates.createTitle",
          )}
        </DialogTitle>
      </DialogHeader>
      <form className="space-y-4" onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Field>
            <FieldLabel htmlFor="template-name">
              {t("subscriptionTemplates.name")}
            </FieldLabel>
            <Input id="template-name" {...form.register("name")} />
            <FieldError errors={[form.formState.errors.name]} />
          </Field>
          <Field>
            <FieldLabel htmlFor="template-format">
              {t("subscriptionTemplates.format")}
            </FieldLabel>
            <Controller
              control={form.control}
              name="format"
              render={({ field }) => (
                <Select
                  value={field.value}
                  onValueChange={(value) => {
                    if (value === field.value) return;
                    field.onChange(value);
                    if (!editing) {
                      form.setValue(
                        "content",
                        initialTemplateContent[value as SubscriptionFormat],
                        { shouldDirty: true, shouldValidate: true },
                      );
                      form.clearErrors("root");
                    }
                  }}
                  disabled={editing && template?.is_default}
                >
                  <SelectTrigger id="template-format" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {subscriptionFormats.map((value) => (
                        <SelectItem key={value} value={value}>
                          {t(formatLabelKeys[value])}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              )}
            />
          </Field>
        </div>
        <Field>
          <FieldLabel htmlFor="template-content">
            {t("subscriptionTemplates.content")}
          </FieldLabel>
          <Controller
            control={form.control}
            name="content"
            render={({ field }) => (
              <MonacoJsonEditor
                id="template-content"
                value={field.value}
                onChange={field.onChange}
                language={
                  format === "clash-meta"
                    ? "yaml"
                    : format === "v2ray"
                      ? "text"
                      : "json"
                }
                disabled={mutation.isPending}
                className="h-[50svh] min-h-64"
              />
            )}
          />
          <FieldError errors={[form.formState.errors.content]} />
        </Field>
        <p className="text-sm text-muted-foreground">
          {t("subscriptionTemplates.variables")}
        </p>
        {form.formState.errors.root && (
          <p role="alert" className="text-sm text-destructive">
            {form.formState.errors.root.message}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={mutation.isPending}
            onClick={onDiscard}
          >
            {t("cancel")}
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {t(editing ? "core.save" : "create")}
          </Button>
        </div>
      </form>
    </>
  );
}
