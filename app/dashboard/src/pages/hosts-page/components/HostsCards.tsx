import { Copy } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

import { DeleteHostButton } from "./DeleteHostButton";
import { HostGroupBadges } from "./HostGroupBadges";
import { HostVisibilityIndicator } from "./HostVisibilityIndicator";

import type { HostRow } from "../lib/model";

type HostsCardsProps = {
  rows: HostRow[];
  pending: boolean;
  onEdit: (row: HostRow) => void;
  onDuplicate: (row: HostRow) => void;
  onToggle: (row: HostRow, checked: boolean) => void;
  onDelete: (row: HostRow) => void;
};

export function HostsCards({
  rows,
  pending,
  onEdit,
  onDuplicate,
  onToggle,
  onDelete,
}: HostsCardsProps) {
  const { t } = useTranslation();

  return (
    <div className="grid gap-3 md:hidden">
      {rows.map((row) => (
        <article
          key={row.id}
          className="rounded-xl border bg-card p-4 shadow-xs"
          onClick={() => onEdit(row)}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="link"
                  className="h-auto whitespace-normal p-0 text-start font-medium text-foreground"
                  onClick={(event) => {
                    event.stopPropagation();
                    onEdit(row);
                  }}
                >
                  <span>{row.remark}</span>
                  <HostVisibilityIndicator isHidden={row.is_hidden} />
                </Button>
                <Badge variant="secondary" className="font-mono tabular-nums">
                  {t("hostsPage.id")}: {row.id}
                </Badge>
              </div>
              <p className="font-mono text-xs text-muted-foreground">
                {row.address}:{row.port ?? row.inbound_port}
              </p>
            </div>
            <Badge variant="outline">{row.inbound_tag}</Badge>
          </div>
          <div className="mt-3">
            <HostGroupBadges groups={row.groups} />
          </div>
          <div
            className="mt-4 flex items-center justify-between"
            onClick={(event) => event.stopPropagation()}
          >
            <Switch
              checked={row.enabled}
              disabled={pending}
              onCheckedChange={(checked) => onToggle(row, checked)}
            />
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => onDuplicate(row)}
                aria-label={t("hostsPage.copy")}
              >
                <Copy />
              </Button>
              <DeleteHostButton
                pending={pending}
                name={row.remark}
                onDelete={() => onDelete(row)}
              />
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
