import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

export function HostParameterHelp({
  label,
  hint,
  hintListKeys,
  example,
}: {
  label: string;
  hint: string;
  hintListKeys?: readonly string[];
  example?: string;
}) {
  const { t } = useTranslation();
  const accessibleLabel = t("hostEditor.parameterHelp", { name: label });
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label={accessibleLabel}
        >
          <Info />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        aria-label={accessibleLabel}
        className="max-h-[var(--radix-popover-content-available-height)] w-80 max-w-[calc(100vw-2rem)] gap-3 overflow-y-auto"
      >
        <p className="whitespace-pre-line">{hint}</p>
        {hintListKeys && (
          <ul className="grid list-disc gap-2 ps-4">
            {hintListKeys.map((key) => (
              <li key={key}>{t(key)}</li>
            ))}
          </ul>
        )}
        {example && (
          <div className="flex min-w-0 flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              {t("hostEditor.example")}
            </span>
            <code dir="ltr" className="break-all text-start">
              {example}
            </code>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
