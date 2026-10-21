import { useCallback, useRef } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { FieldGroup } from "@/components/ui/field";
import type { HostFormValues } from "../lib/form";
import type { HostFormProps } from "../lib/types";
import { AddHostParameter } from "./AddHostParameter";
import { HostParameterSection } from "./HostParameterSection";

export function HostParameterSections({
  pending,
  inbounds,
  templates,
}: HostFormProps) {
  const { control, getValues, setValue, clearErrors } =
    useFormContext<HostFormValues>();
  const selected = useWatch({ control, name: "selected", exact: true });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const removeParameter = useCallback(
    (id: string) => {
      setValue(
        "selected",
        getValues("selected").filter((value) => value !== id),
        { shouldDirty: true },
      );
      clearErrors(`parameters.${id}`);
      if (id === "is_hidden") setValue("is_hidden", false);
      requestAnimationFrame(() => triggerRef.current?.focus());
    },
    [getValues, setValue, clearErrors],
  );
  return (
    <FieldGroup className="gap-5">
      <AddHostParameter
        inbounds={inbounds}
        pending={pending}
        triggerRef={triggerRef}
      />
      {selected.map((id) => (
        <HostParameterSection
          key={id}
          id={id}
          pending={pending}
          inbounds={inbounds}
          templates={templates}
          onRemove={removeParameter}
        />
      ))}
    </FieldGroup>
  );
}
