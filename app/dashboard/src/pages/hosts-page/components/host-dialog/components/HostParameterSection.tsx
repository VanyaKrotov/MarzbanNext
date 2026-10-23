import { memo } from "react";
import { useTranslation } from "react-i18next";
import { FieldGroup } from "@/components/ui/field";
import { hostParameters, specialHostParameters } from "../lib/parameters";
import type { HostFormProps } from "../lib/types";
import { ParameterField, VisibilityField } from "./ParameterFields";
import { BooleanParameterField } from "./BooleanParameterField";
import { SubscriptionTemplateFields } from "./SubscriptionTemplateFields";
import { HostParameterHeader } from "./HostParameterHeader";
import { JsonParameterField } from "./JsonParameterField";

const parametersById = new Map(
  hostParameters.map((definition) => [definition.id, definition]),
);
type SectionProps = Pick<
  HostFormProps,
  "inbounds" | "templates" | "pending"
> & {
  id: string;
  onRemove: (id: string) => void;
};

export const HostParameterSection = memo(function HostParameterSection(
  props: SectionProps,
) {
  const { id, pending, onRemove } = props;
  const { t } = useTranslation();
  const definition = parametersById.get(id);
  const labelKey =
    definition?.labelKey ??
    specialHostParameters.find((item) => item.id === id)?.labelKey;
  if (!labelKey) return null;
  const label = t(labelKey);
  if (definition?.kind === "json" && definition.id !== "alpn") {
    return <JsonParameterField {...props} definition={definition} />;
  }
  const isBoolean = definition?.kind === "boolean";
  return (
    <FieldGroup className="gap-3" aria-labelledby={`host-option-${id}`}>
      <HostParameterHeader
        id={id}
        label={label}
        pending={pending}
        onRemove={onRemove}
        hintKey={definition?.hintKey}
        hintListKeys={definition?.hintListKeys}
        example={
          definition?.kind === "text" ? definition.placeholder : undefined
        }
        labelControl={
          isBoolean ? (
            <BooleanParameterField definition={definition} pending={pending} />
          ) : id === "is_hidden" ? (
            <VisibilityField pending={pending} />
          ) : undefined
        }
      />
      {definition && !isBoolean && (
        <ParameterField definition={definition} pending={pending} />
      )}
      {!definition && <SpecialParameter {...props} />}
    </FieldGroup>
  );
});

function SpecialParameter({ id, templates, pending }: SectionProps) {
  return id === "templates" ? (
    <SubscriptionTemplateFields templates={templates} pending={pending} />
  ) : null;
}
