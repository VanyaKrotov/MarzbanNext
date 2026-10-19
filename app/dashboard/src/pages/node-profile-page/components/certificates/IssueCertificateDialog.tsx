import { LoaderCircle, Plus } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { generateErrorMessage } from "utils/toastHandler";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

import { useIssueCertificateMutation } from "@/pages/nodes-page/lib/query";

type IssueCertificateFormValues = {
  domain: string;
  email: string;
};

interface Props {
  nodeId: number;
  nodeName: string;
}

export function IssueCertificateDialog(props: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" size="sm">
          <Plus />
          {t("actions.issue")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <FormContent {...props} onClose={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}

function FormContent({
  nodeId,
  nodeName,
  onClose,
}: Props & { onClose(): void }) {
  const { t } = useTranslation();
  const form = useForm<IssueCertificateFormValues>({
    defaultValues: {
      domain: "",
      email: "",
    },
  });

  const issue = useIssueCertificateMutation(nodeId);
  const domain = form.watch("domain");

  const submit = (values: IssueCertificateFormValues) => {
    issue.mutate(
      {
        domain: values.domain.trim(),
        email: values.email.trim(),
      },
      {
        onSuccess: onClose,
        onError: (error) => generateErrorMessage(error),
      },
    );
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle>{t("nodes.certificates.issue")}</DialogTitle>
        <DialogDescription>{nodeName}</DialogDescription>
      </DialogHeader>
      <form className="space-y-4" onSubmit={form.handleSubmit(submit)}>
        <Field>
          <FieldLabel htmlFor="profile-certificate-domain">
            {t("nodes.certificates.domain")}
          </FieldLabel>
          <Controller
            control={form.control}
            name="domain"
            render={({ field }) => (
              <Input
                id="profile-certificate-domain"
                placeholder="node.example.com"
                {...field}
              />
            )}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="profile-certificate-email">
            {t("nodes.certificates.email")}
          </FieldLabel>
          <Controller
            control={form.control}
            name="email"
            render={({ field }) => (
              <Input
                id="profile-certificate-email"
                type="email"
                placeholder="admin@example.com"
                {...field}
              />
            )}
          />
        </Field>
        <Button
          type="submit"
          className="w-full"
          disabled={!domain.trim() || issue.isPending}
        >
          {issue.isPending && <LoaderCircle className="animate-spin" />}
          {t("actions.issue")}
        </Button>
      </form>
    </>
  );
}
