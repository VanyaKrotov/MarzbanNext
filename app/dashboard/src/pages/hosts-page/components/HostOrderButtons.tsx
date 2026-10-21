import { ArrowDown, ArrowUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";

export function HostOrderButtons({ disabled, first, last, onMove }: {
  disabled: boolean; first: boolean; last: boolean; onMove: (direction: -1 | 1) => void;
}) {
  const { t } = useTranslation();
  return <div className="flex" onClick={(event) => event.stopPropagation()}>
    <Button type="button" variant="ghost" size="icon-sm" disabled={disabled || first}
      aria-label={t("hostEditor.moveUp")} onClick={() => onMove(-1)}><ArrowUp /></Button>
    <Button type="button" variant="ghost" size="icon-sm" disabled={disabled || last}
      aria-label={t("hostEditor.moveDown")} onClick={() => onMove(1)}><ArrowDown /></Button>
  </div>;
}
