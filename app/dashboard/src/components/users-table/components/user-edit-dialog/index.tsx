import { LoaderCircle, Pencil, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { FormProvider } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { NodeUsageChart } from "@/components/node-usage-chart";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useInboundsByProtocolQuery,
  useXrayCapabilitiesQuery,
} from "hooks/useInboundsQuery";
import type { InboundsMap } from "types/Inbound";
import type { User } from "types/User";

import { InboundAccordionsSection } from "./components/InboundAccordionsSection";
import { UserDialogActions } from "./components/UserDialogActions";
import { UserFormSection } from "./components/UserFormSection";
import {
  applyUserFormServerErrors,
  getDefaultUserFormValues,
  toUserPayload,
  UserFormValues,
} from "./lib/form";
import { useUserEditForm, useUserUsage } from "./lib/hooks";
import {
  useDeleteUserMutation,
  useResetUserUsageMutation,
  useRevokeSubscriptionMutation,
  useSaveUserMutation,
} from "./lib/query";
const emptyInbounds: InboundsMap = new Map();

type UserEditDialogProps = {
  editingUser: User | null;
  creatingUser: boolean;
  onEditingUserChange: (user: User | null) => void;
  onCreatingUserChange: (open: boolean) => void;
};

export function UserEditDialog({
  editingUser,
  creatingUser,
  onEditingUserChange,
  onCreatingUserChange,
}: UserEditDialogProps) {
  const isOpen = creatingUser || Boolean(editingUser);
  const [closeDisabled, setCloseDisabled] = useState(false);

  const close = () => {
    onCreatingUserChange(false);
    onEditingUserChange(null);
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => !open && !closeDisabled && close()}
    >
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-4xl">
        <UserEditDialogContent
          editingUser={editingUser}
          onClose={close}
          onEditingUserChange={onEditingUserChange}
          onPendingChange={setCloseDisabled}
        />
      </DialogContent>
    </Dialog>
  );
}

interface ContentProps {
  editingUser: User | null;
  onClose: () => void;
  onEditingUserChange: (user: User | null) => void;
  onPendingChange: (pending: boolean) => void;
}

function UserEditDialogContent({
  editingUser,
  onClose,
  onEditingUserChange,
  onPendingChange,
}: ContentProps) {
  const { t } = useTranslation();
  const isEditing = Boolean(editingUser);
  const inboundsQuery = useInboundsByProtocolQuery(true);
  const capabilitiesQuery = useXrayCapabilitiesQuery(true);
  const availableInbounds = inboundsQuery.data ?? emptyInbounds;
  const accountProtocols = capabilitiesQuery.data?.account_protocols;
  const form = useUserEditForm(editingUser, availableInbounds);
  const usage = useUserUsage(editingUser);
  const saveMutation = useSaveUserMutation(isEditing);
  const deleteMutation = useDeleteUserMutation();
  const resetUsageMutation = useResetUserUsageMutation();
  const revokeSubscriptionMutation = useRevokeSubscriptionMutation();
  const [serverError, setServerError] = useState<string | null>(null);
  const actionPending =
    deleteMutation.isPending ||
    resetUsageMutation.isPending ||
    revokeSubscriptionMutation.isPending;
  const disabled = saveMutation.isPending || actionPending;

  const close = () => {
    form.reset(getDefaultUserFormValues(availableInbounds));
    setServerError(null);
    usage.reset();
    onClose();
  };

  useEffect(() => {
    onPendingChange(disabled);
    return () => onPendingChange(false);
  }, [disabled, onPendingChange]);

  const submit = (values: UserFormValues) => {
    setServerError(null);
    saveMutation.mutate(toUserPayload(values), {
      onSuccess: () => {
        toast.success(
          t(isEditing ? "userDialog.userEdited" : "userDialog.userCreated", {
            username: values.username,
          }),
          { duration: 3000 },
        );
        close();
      },
      onError: (error) => {
        setServerError(applyUserFormServerErrors(error, form));
      },
    });
  };

  return (
    <FormProvider {...form}>
      <form onSubmit={form.handleSubmit(submit)} className="space-y-6">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            {isEditing ? (
              <Pencil className="size-4" />
            ) : (
              <UserPlus className="size-4" />
            )}
            {isEditing ? t("userDialog.editUserTitle") : t("createNewUser")}
          </DialogTitle>
          <DialogDescription>
            {isEditing ? editingUser?.username : t("createNewUser")}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 md:grid-cols-2">
          <UserFormSection
            disabled={disabled}
            isEditing={isEditing}
            serverError={serverError}
          />
          <InboundAccordionsSection
            disabled={disabled}
            availableInbounds={availableInbounds}
            accountProtocols={accountProtocols}
          />
        </div>

        {isEditing && usage.visible && (
          <div className="border-t pt-5">
            <NodeUsageChart
              username={editingUser?.username}
              title={t("userDialog.usage")}
              description={t("userDialog.usageDescription")}
            />
          </div>
        )}

        <DialogFooter className="border-t pt-4 sm:justify-between">
          {editingUser ? (
            <UserDialogActions
              user={editingUser}
              disabled={disabled}
              deleteMutation={deleteMutation}
              resetUsageMutation={resetUsageMutation}
              revokeSubscriptionMutation={revokeSubscriptionMutation}
              usageVisible={usage.visible}
              onClose={close}
              onUserChange={onEditingUserChange}
              onUsageToggle={() => usage.setVisible(!usage.visible)}
            />
          ) : (
            <div />
          )}
          <Button type="submit" disabled={disabled}>
            {saveMutation.isPending && (
              <LoaderCircle className="animate-spin" />
            )}
            {t(isEditing ? "core.save" : "create")}
          </Button>
        </DialogFooter>
      </form>
    </FormProvider>
  );
}
