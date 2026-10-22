import { Trash2 } from "lucide-react";
import { isAxiosError } from "axios";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { api } from "@/service/http";
import {
  generateErrorMessage,
  generateSuccessMessage,
} from "@/utils/toastHandler";

import { useTemplateMutation, type SubscriptionTemplate } from "../lib/query";

export type TemplateAction = {
  template: SubscriptionTemplate;
  type: "delete" | "default";
};

export function TemplateActionDialog({
  action,
  onClose,
}: {
  action: TemplateAction | null;
  onClose: () => void;
}) {
  return (
    <AlertDialog
      open={action !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      {action && <TemplateActionContent action={action} onClose={onClose} />}
    </AlertDialog>
  );
}

function TemplateActionContent({
  action,
  onClose,
}: {
  action: TemplateAction;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const mutation = useTemplateMutation((_: void) =>
    action.type === "delete"
      ? api.delete(`/subscription-templates/${action.template.id}`)
      : api.post(`/subscription-templates/${action.template.id}/set-default`),
  );
  const confirm = () =>
    mutation.mutate(undefined, {
      onSuccess: () => {
        generateSuccessMessage(
          t(
            action.type === "delete"
              ? "subscriptionTemplates.deleted"
              : "subscriptionTemplates.defaultChanged",
          ),
        );
        onClose();
      },
      onError: (error) => {
        if (action.type === "delete" && isAxiosError(error)) {
          const detail = error.response?.data?.detail;
          if (detail === "Default templates cannot be deleted") {
            toast.error(t("subscriptionTemplates.deleteDefaultError"));
            return;
          }
          if (detail === "Templates assigned to hosts cannot be deleted") {
            toast.error(t("subscriptionTemplates.deleteAssignedError"));
            return;
          }
        }
        generateErrorMessage(error);
      },
    });
  return (
    <AlertDialogContent
      onEscapeKeyDown={(event) => {
        if (mutation.isPending) event.preventDefault();
      }}
    >
      <AlertDialogHeader>
        {action.type === "delete" && (
          <AlertDialogMedia className="bg-destructive/10 text-destructive">
            <Trash2 />
          </AlertDialogMedia>
        )}
        <AlertDialogTitle>
          {t(
            action.type === "delete"
              ? "subscriptionTemplates.deleteTitle"
              : "subscriptionTemplates.defaultTitle",
            { name: action.template.name },
          )}
        </AlertDialogTitle>
        <AlertDialogDescription>
          {t(
            action.type === "delete"
              ? "subscriptionTemplates.deleteDescription"
              : "subscriptionTemplates.defaultDescription",
            { name: action.template.name },
          )}
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel disabled={mutation.isPending}>
          {t("cancel")}
        </AlertDialogCancel>
        <AlertDialogAction
          variant={action.type === "delete" ? "destructive" : "default"}
          disabled={mutation.isPending}
          onClick={(event) => {
            event.preventDefault();
            confirm();
          }}
        >
          {t(action.type === "delete" ? "delete" : "apply")}
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  );
}
