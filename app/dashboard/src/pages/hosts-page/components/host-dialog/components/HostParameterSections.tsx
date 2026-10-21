import { Plus, X } from "lucide-react";
import { Fragment, useRef } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { FieldGroup } from "@/components/ui/field";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { HostFormValues } from "../lib/form";
import {
  getAvailableParameterGroups,
  hostParameters,
  specialHostParameters,
} from "../lib/parameters";
import type { HostFormProps } from "../lib/types";
import { ParameterField, StandaloneField } from "./ParameterFields";
import { CompositionFields } from "./CompositionFields";
import { SubscriptionTemplateFields } from "./SubscriptionTemplateFields";

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
  const addedParameterRef = useRef<string | null>(null);
  const inbound = inbounds.find((item) => item.id === inboundId);
  const supportsXhttp =
    inbound?.network === "xhttp" || inbound?.network === "splithttp";
  const groups = getAvailableParameterGroups(selected, supportsXhttp);

  const removeParameter = (id: string) => {
    form.setValue(
      "selected",
      selected.filter((value) => value !== id),
      { shouldDirty: true },
    );
    form.clearErrors(`parameters.${id}`);
    if (id === "show_when_composed") form.setValue("show_when_composed", true);
    if (id === "composition") {
      form.setValue("linked_host_ids", []);
      form.setValue("balancer_clients", {});
      form.clearErrors("balancer_clients");
    }
    requestAnimationFrame(() => addParameterRef.current?.focus());
  };

  return (
    <FieldGroup className="gap-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">{t("hostEditor.additional")}</h3>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              ref={addParameterRef}
              type="button"
              variant="outline"
              size="icon-sm"
              disabled={pending || !groups.length}
              aria-label={t("hostEditor.addParameter")}
            >
              <Plus />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="w-72 max-w-[calc(100vw-2rem)]"
            onCloseAutoFocus={(event) => {
              const id = addedParameterRef.current;
              addedParameterRef.current = null;
              if (id && parametersById.has(id)) {
                event.preventDefault();
                requestAnimationFrame(() => form.setFocus(`parameters.${id}`));
              }
            }}
          >
            {groups.map((group, index) => (
              <Fragment key={group.id}>
                {index > 0 && <DropdownMenuSeparator />}
                <DropdownMenuGroup>
                  <DropdownMenuLabel>
                    {t(`hostEditor.parameterGroups.${group.id}`)}
                  </DropdownMenuLabel>
                  {group.options.map((item) => (
                    <DropdownMenuItem
                      key={item.id}
                      onSelect={() => {
                        addedParameterRef.current = item.id;
                        form.setValue("selected", [...selected, item.id], {
                          shouldDirty: true,
                        });
                      }}
                    >
                      {t(item.labelKey)}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuGroup>
              </Fragment>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {selected.map((id) => {
        const definition = parametersById.get(id);
        const labelKey =
          definition?.labelKey ??
          specialHostParameters.find((item) => item.id === id)?.labelKey;
        if (!labelKey) return null;
        const label = t(labelKey);
        return (
          <FieldGroup
            key={id}
            className="gap-3"
            aria-labelledby={`host-option-${id}`}
          >
            <div className="flex items-center justify-between gap-2">
              <h3 id={`host-option-${id}`} className="text-sm font-medium">
                {label}
              </h3>
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
          </FieldGroup>
        );
      })}
    </FieldGroup>
  );
}

function SpecialParameter({
  id,
  host,
  hosts,
  templates,
  capabilities,
  pending,
}: HostFormProps & { id: string }) {
  switch (id) {
    case "templates":
      return (
        <SubscriptionTemplateFields templates={templates} pending={pending} />
      );
    case "composition":
      return (
        <CompositionFields
          hosts={hosts.filter((item) => item.id !== host?.id)}
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
