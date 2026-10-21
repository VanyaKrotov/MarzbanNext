import { memo } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { FieldDescription, FieldGroup } from "@/components/ui/field";
import {
  hostParameters,
  specialHostParameters,
  type HostParameterDefinition,
} from "../lib/parameters";
import type { HostFormProps } from "../lib/types";
import { useSupportsXhttp } from "../lib/useSupportsXhttp";
import { ParameterField, VisibilityField } from "./ParameterFields";
import { SubscriptionTemplateFields } from "./SubscriptionTemplateFields";

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
  return (
    <FieldGroup className="gap-3" aria-labelledby={`host-option-${id}`}>
      <div className="flex items-center justify-between gap-2">
        {id === "is_hidden" ? (
          <VisibilityField pending={pending} />
        ) : (
          <h3 id={`host-option-${id}`} className="text-sm font-medium">
            {label}
          </h3>
        )}
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          disabled={pending}
          onClick={() => onRemove(id)}
          aria-label={t("hostEditor.removeParameter", { name: label })}
        >
          <X />
        </Button>
      </div>
      {id === "is_hidden" && (
        <FieldDescription>{t("hostEditor.hiddenHint")}</FieldDescription>
      )}
      {definition ? (
        <OptionalParameterField
          definition={definition}
          pending={pending}
          inbounds={props.inbounds}
        />
      ) : (
        <SpecialParameter {...props} />
      )}
    </FieldGroup>
  );
});

function OptionalParameterField(
  props: Pick<SectionProps, "inbounds" | "pending"> & {
    definition: HostParameterDefinition;
  },
) {
  if (props.definition.xhttpOnly) return <XhttpParameterField {...props} />;
  return (
    <ParameterField
      definition={props.definition}
      pending={props.pending}
      incompatible={false}
    />
  );
}

function XhttpParameterField({
  definition,
  inbounds,
  pending,
}: Pick<SectionProps, "inbounds" | "pending"> & {
  definition: HostParameterDefinition;
}) {
  const supportsXhttp = useSupportsXhttp(inbounds);
  return (
    <ParameterField
      definition={definition}
      pending={pending}
      incompatible={!supportsXhttp}
    />
  );
}

function SpecialParameter({ id, templates, pending }: SectionProps) {
  return id === "templates" ? (
    <SubscriptionTemplateFields templates={templates} pending={pending} />
  ) : null;
}
