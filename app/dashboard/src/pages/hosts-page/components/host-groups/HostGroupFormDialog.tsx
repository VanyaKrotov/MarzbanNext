import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateHostGroupMutation,
  useUpdateHostGroupMutation,
} from "../../lib/query";
import type { HostGroupType } from "../../types";

const hostGroupFormSchema = z.object({
  id: z
    .string()
    .trim()
    .min(1, "hostsPage.groupIdRequired")
    .max(64, "hostsPage.groupIdTooLong")
    .regex(/^[a-zA-Z0-9_-]+$/, "hostsPage.groupIdInvalid"),
  name: z.string().trim().min(1, "hostsPage.groupNameRequired").max(256),
  description: z.string().trim().optional(),
  tags: z.string().trim().optional(),
});

type HostGroupFormValues = z.infer<typeof hostGroupFormSchema>;

type HostGroupFormDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pending?: boolean;
  group?: HostGroupType | null;
  trigger?: ReactNode;
  onSaved?: (group: HostGroupType) => void;
};

export function HostGroupFormDialog({
  open,
  onOpenChange,
  pending = false,
  group = null,
  trigger,
  onSaved,
}: HostGroupFormDialogProps) {
  const { t } = useTranslation();
  const createHostGroup = useCreateHostGroupMutation();
  const updateHostGroup = useUpdateHostGroupMutation();
  const isEditing = Boolean(group);
  const form = useForm<HostGroupFormValues>({
    resolver: zodResolver(hostGroupFormSchema),
    defaultValues: getHostGroupFormValues(group),
  });
  const submitting =
    pending || createHostGroup.isPending || updateHostGroup.isPending;

  useEffect(() => {
    if (open) {
      form.reset(getHostGroupFormValues(group));
    }
  }, [form, group, open]);

  const close = (nextOpen: boolean) => {
    if (submitting) return;
    onOpenChange(nextOpen);
    if (!nextOpen) {
      form.clearErrors();
    }
  };

  const submit = form.handleSubmit((values) => {
    const payload = {
      name: values.name,
      description: values.description || null,
      tags: parseTags(values.tags),
    };

    if (group) {
      updateHostGroup.mutate(
        {
          id: group.id,
          group: payload,
        },
        {
          onSuccess: (savedGroup) => {
            onSaved?.(savedGroup);
            onOpenChange(false);
          },
          onError: (error) => setRootError(form, error, t("hostsPage.groupUpdateError")),
        },
      );
      return;
    }

    createHostGroup.mutate(
      {
        id: values.id,
        ...payload,
      },
      {
        onSuccess: (savedGroup) => {
          onSaved?.(savedGroup);
          form.reset(getHostGroupFormValues(null));
          onOpenChange(false);
        },
        onError: (error) => setRootError(form, error, t("hostsPage.groupCreateError")),
      },
    );
  });

  return (
    <Dialog open={open} onOpenChange={close}>
      {trigger ? <DialogTrigger asChild>{trigger}</DialogTrigger> : null}
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isEditing
              ? t("hostsPage.editGroupTitle")
              : t("hostsPage.addGroupTitle")}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Field>
            <FieldLabel htmlFor="host-group-id">
              {t("hostsPage.groupId")}
            </FieldLabel>
            <Input
              id="host-group-id"
              disabled={submitting || isEditing}
              aria-invalid={Boolean(form.formState.errors.id)}
              placeholder={t("hostsPage.groupIdPlaceholder")}
              {...form.register("id")}
            />
            <FieldError
              errors={[normalizeFieldError(form.formState.errors.id, t)]}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="host-group-name">
              {t("hostsPage.groupName")}
            </FieldLabel>
            <Input
              id="host-group-name"
              disabled={submitting}
              aria-invalid={Boolean(form.formState.errors.name)}
              placeholder={t("hostsPage.groupNamePlaceholder")}
              {...form.register("name", {
                onChange: (event) => {
                  if (!isEditing && !form.formState.dirtyFields.id) {
                    form.setValue("id", slugifyGroupId(event.target.value), {
                      shouldValidate: true,
                    });
                  }
                },
              })}
            />
            <FieldError
              errors={[normalizeFieldError(form.formState.errors.name, t)]}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="host-group-tags">
              {t("hostsPage.groupTags")}
            </FieldLabel>
            <Input
              id="host-group-tags"
              disabled={submitting}
              placeholder={t("hostsPage.groupTagsPlaceholder")}
              {...form.register("tags")}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="host-group-description">
              {t("hostsPage.groupDescription")}
            </FieldLabel>
            <Textarea
              id="host-group-description"
              disabled={submitting}
              placeholder={t("hostsPage.groupDescriptionPlaceholder")}
              rows={3}
              {...form.register("description")}
            />
          </Field>
          <FieldError errors={[form.formState.errors.root]} />
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={submitting}
            onClick={() => close(false)}
          >
            {t("cancel")}
          </Button>
          <Button type="button" disabled={submitting} onClick={submit}>
            {isEditing ? t("core.save") : t("create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function parseTags(value?: string) {
  if (!value) return [];
  return Array.from(
    new Set(
      value
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    ),
  );
}

function getHostGroupFormValues(
  group: HostGroupType | null | undefined,
): HostGroupFormValues {
  return {
    id: group?.id ?? "",
    name: group?.name ?? "",
    description: group?.description ?? "",
    tags: group?.tags.join(", ") ?? "",
  };
}

function slugifyGroupId(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

function normalizeFieldError(
  error: { message?: string } | undefined,
  t: (key: string) => string,
) {
  if (!error?.message) {
    return undefined;
  }
  return {
    ...error,
    message: error.message.startsWith("hostsPage.")
      ? t(error.message)
      : error.message,
  };
}

function setRootError(
  form: ReturnType<typeof useForm<HostGroupFormValues>>,
  error: unknown,
  fallback: string,
) {
  form.setError("root", {
    message: getHostGroupErrorMessage(error, fallback),
  });
}

function getHostGroupErrorMessage(error: unknown, fallback: string) {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof error.response === "object" &&
    error.response !== null &&
    "data" in error.response &&
    typeof error.response.data === "object" &&
    error.response.data !== null &&
    "detail" in error.response.data
  ) {
    const detail = error.response.data.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return fallback;
}
