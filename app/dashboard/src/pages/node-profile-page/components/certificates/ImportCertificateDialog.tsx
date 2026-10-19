import { FileKey2, LoaderCircle } from "lucide-react";
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
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useImportCertificateMutation } from "@/pages/nodes-page/lib/query";

type ImportCertificateFormValues = {
  domain: string;
  certificate_file: string;
  key_file: string;
};

interface Props {
  nodeId: number;
  nodeName: string;
}

export function ImportCertificateDialog(props: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" size="sm" variant="outline">
          <FileKey2 />
          {t("actions.import")}
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
  const form = useForm<ImportCertificateFormValues>({
    defaultValues: {
      domain: "",
      certificate_file: "",
      key_file: "",
    },
  });
  const importCertificate = useImportCertificateMutation(nodeId);
  const domain = form.watch("domain");
  const certificateFile = form.watch("certificate_file");
  const keyFile = form.watch("key_file");

  const submit = (values: ImportCertificateFormValues) => {
    importCertificate.mutate(
      {
        domain: values.domain.trim(),
        certificate_file: values.certificate_file.trim(),
        key_file: values.key_file.trim(),
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
        <DialogTitle>{t("nodes.certificates.importTitle")}</DialogTitle>
        <DialogDescription>{nodeName}</DialogDescription>
      </DialogHeader>
      <form className="space-y-4" onSubmit={form.handleSubmit(submit)}>
        <Field>
          <FieldLabel htmlFor="profile-import-certificate-domain">
            {t("nodes.certificates.domain")}
          </FieldLabel>
          <Controller
            control={form.control}
            name="domain"
            render={({ field }) => (
              <Input
                id="profile-import-certificate-domain"
                placeholder="node.example.com"
                {...field}
              />
            )}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="profile-import-certificate-file">
            {t("nodes.certificates.certificateFile")}
          </FieldLabel>
          <Controller
            control={form.control}
            name="certificate_file"
            render={({ field }) => (
              <Input
                id="profile-import-certificate-file"
                placeholder="/etc/letsencrypt/live/node.example.com/fullchain.pem"
                {...field}
              />
            )}
          />
          <FieldDescription>
            {t("nodes.certificates.importPathHint")}
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel htmlFor="profile-import-key-file">
            {t("nodes.certificates.keyFile")}
          </FieldLabel>
          <Controller
            control={form.control}
            name="key_file"
            render={({ field }) => (
              <Input
                id="profile-import-key-file"
                placeholder="/etc/letsencrypt/live/node.example.com/privkey.pem"
                {...field}
              />
            )}
          />
        </Field>
        <Button
          type="submit"
          className="w-full"
          disabled={
            !domain.trim() ||
            !certificateFile.trim() ||
            !keyFile.trim() ||
            importCertificate.isPending
          }
        >
          {importCertificate.isPending && (
            <LoaderCircle className="animate-spin" />
          )}
          {t("actions.import")}
        </Button>
      </form>
    </>
  );
}
