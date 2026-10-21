import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { FormProvider, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { defaultBindings } from "@/pages/subscription-templates-page/lib/query";
import {
  getHostFormValues,
  hostFormSchema,
  type HostFormValues,
} from "../lib/form";
import { ParameterError, toHostPayload } from "../lib/payload";
import type { HostFormProps } from "../lib/types";
import { CoreFields } from "./CoreFields";
import { HostParameterSections } from "./HostParameterSections";

export function HostForm(props: HostFormProps) {
  const { host, pending, onSubmit, onOpenChange, inbounds, templates } = props;
  const { t } = useTranslation();
  const [defaultValues] = useState(() =>
    getHostFormValues(inbounds[0].id, host, defaultBindings(templates)),
  );
  const form = useForm<HostFormValues>({
    resolver: zodResolver(hostFormSchema),
    defaultValues,
  });

  const submit = (values: HostFormValues) => {
    try {
      onSubmit(toHostPayload(values));
    } catch (error) {
      if (!(error instanceof ParameterError)) throw error;
      form.setError(
        `parameters.${error.parameter}`,
        { message: t(error.message) },
        { shouldFocus: true },
      );
    }
  };

  return (
    <FormProvider {...form}>
      <form
        onSubmit={form.handleSubmit(submit)}
        className="flex flex-col gap-5"
      >
        <CoreFields
          inbounds={inbounds}
          groups={props.hostGroups}
          pending={pending}
        />
        <HostParameterSections {...props} />
        <div className="flex justify-end gap-2 border-t pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={pending}
          >
            {t("cancel")}
          </Button>
          <Button type="submit" disabled={pending}>
            {pending && <LoaderCircle className="animate-spin" />}
            {t(host ? "core.save" : "create")}
          </Button>
        </div>
      </form>
    </FormProvider>
  );
}
