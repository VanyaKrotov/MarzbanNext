import { X } from "lucide-react";
import { useMemo, useRef } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { HostFormValues } from "../lib/form";
import { hostParameters, specialHostParameters } from "../lib/parameters";
import type { HostFormProps } from "../lib/types";
import { GroupsField } from "./GroupsField";
import { ParameterField, StandaloneField } from "./ParameterFields";
import { CompositionFields } from "./CompositionFields";
import { SubscriptionTemplatesPopover } from "./SubscriptionTemplatesPopover";

const parametersById = new Map(
  hostParameters.map((definition) => [definition.id, definition]),
);

export function HostParameterSections(props: HostFormProps) {
  const { pending, inbounds } = props;
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const selected = useWatch({ control: form.control, name: "selected" });
  const inboundId = useWatch({ control: form.control, name: "inbound_id" });
  const addParameterRef = useRef<HTMLButtonElement>(null);
  const inbound = inbounds.find((item) => item.id === inboundId);
  const supportsXhttp =
    inbound?.network === "xhttp" || inbound?.network === "splithttp";
  const candidates = [
    ...hostParameters.filter((item) => !item.xhttpOnly || supportsXhttp),
    ...specialHostParameters,
  ];

  const removeParameter = (id: string) => {
    form.setValue(
      "selected",
      selected.filter((value) => value !== id),
      { shouldDirty: true },
    );
    form.clearErrors(`parameters.${id}`);
    if (id === "show_when_composed") form.setValue("show_when_composed", true);
    if (id === "composition") form.setValue("linked_host_ids", []);
    if (id === "groups") form.setValue("group_ids", []);
    requestAnimationFrame(() => addParameterRef.current?.focus());
  };

  const addParameter = (id: string) => {
    form.setValue("selected", [...selected, id], { shouldDirty: true });
    if (parametersById.has(id))
      requestAnimationFrame(() => form.setFocus(`parameters.${id}`));
  };

  return (
    <>
      {selected.map((id) => {
        const definition = parametersById.get(id);
        const labelKey =
          definition?.labelKey ??
          specialHostParameters.find((item) => item.id === id)?.labelKey;
        if (!labelKey) return null;
        const label = t(labelKey);

        return (
          <section
            key={id}
            className="flex flex-col gap-3 rounded-lg border p-4"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{label}</span>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                disabled={pending}
                onClick={() => removeParameter(id)}
                aria-label={t("hostEditor.removeParameter", { name: label })}
              >
                <X />
              </Button>
            </div>
            {definition ? (
              <ParameterField
                definition={definition}
                pending={pending}
                incompatible={Boolean(definition.xhttpOnly && !supportsXhttp)}
              />
            ) : (
              <SpecialParameter id={id} {...props} />
            )}
          </section>
        );
      })}
      <Select value="" disabled={pending} onValueChange={addParameter}>
        <SelectTrigger
          ref={addParameterRef}
          aria-label={t("hostEditor.addParameter")}
        >
          <SelectValue placeholder={t("hostEditor.addParameter")} />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {candidates
              .filter((item) => !selected.includes(item.id))
              .map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {t(item.labelKey)}
                </SelectItem>
              ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </>
  );
}

function SpecialParameter({
  id,
  host,
  hosts,
  hostGroups,
  templates,
  capabilities,
  pending,
}: HostFormProps & { id: string }) {
  const members = useMemo(
    () => hosts.filter((item) => item.id !== host?.id),
    [hosts, host?.id],
  );
  switch (id) {
    case "groups":
      return <GroupsField groups={hostGroups} pending={pending} />;
    case "templates":
      return (
        <SubscriptionTemplatesPopover templates={templates} pending={pending} />
      );
    case "composition":
      return (
        <CompositionFields
          hosts={members}
          capabilities={capabilities}
          pending={pending}
        />
      );
    case "show_when_composed":
      return <StandaloneField pending={pending} />;
    default:
      return null;
  }
}
