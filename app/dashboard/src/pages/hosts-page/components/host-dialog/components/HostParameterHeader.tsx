import type { ReactNode } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { HostParameterHelp } from "./HostParameterHelp";

export function HostParameterHeader({
  id,
  label,
  pending,
  onRemove,
  labelControl,
  hintKey,
  hintListKeys,
  example,
  children,
}: {
  id: string;
  label: string;
  pending: boolean;
  onRemove: (id: string) => void;
  labelControl?: ReactNode;
  hintKey?: string;
  hintListKeys?: readonly string[];
  example?: string;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="flex min-w-0 items-center gap-1">
        {labelControl ?? (
          <h3 id={`host-option-${id}`} className="text-sm font-medium">
            {label}
          </h3>
        )}
        {hintKey && (
          <HostParameterHelp
            label={label}
            hint={t(hintKey)}
            hintListKeys={hintListKeys}
            example={example}
          />
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {children}
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
    </div>
  );
}
