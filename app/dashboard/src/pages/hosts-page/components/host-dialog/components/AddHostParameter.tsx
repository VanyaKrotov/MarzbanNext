import { Plus } from "lucide-react";
import { Fragment, useRef, type RefObject } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { InboundType } from "@/types/Inbound";
import type { HostFormValues } from "../lib/form";
import { getAvailableParameterGroups, hostParameters } from "../lib/parameters";
import { useSupportsXhttp } from "../lib/useSupportsXhttp";

export function AddHostParameter({
  inbounds,
  pending,
  triggerRef,
}: {
  inbounds: InboundType[];
  pending: boolean;
  triggerRef: RefObject<HTMLButtonElement>;
}) {
  const { t } = useTranslation();
  const form = useFormContext<HostFormValues>();
  const selected = useWatch({
    control: form.control,
    name: "selected",
    exact: true,
  });
  const supportsXhttp = useSupportsXhttp(inbounds);
  const groups = getAvailableParameterGroups(selected, supportsXhttp);
  const addedParameterRef = useRef<string | null>(null);
  return (
    <div className="flex items-center justify-between gap-2">
      <h3 className="text-sm font-medium">{t("hostEditor.additional")}</h3>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            ref={triggerRef}
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
            if (id && hostParameters.some((parameter) => parameter.id === id)) {
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
  );
}
