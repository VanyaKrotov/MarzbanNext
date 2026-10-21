import { Copy, GripVertical } from "lucide-react";
import type { DragEvent } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { DeleteHostButton } from "./DeleteHostButton";
import { HostCompositionSummary } from "./HostCompositionSummary";
import type { HostType } from "../types";
import { HostGroupBadges } from "./HostGroupBadges";

import type { HostRow } from "../lib/model";

type DropTarget = {
  rowId: number;
  position: "before" | "after";
} | null;

type HostsTableProps = {
  rows: HostRow[];
  hostsById: ReadonlyMap<number, HostType>;
  pending: boolean;
  reorderDisabled: boolean;
  dropTarget: DropTarget;
  onDragStart: (row: HostRow) => void;
  onDragEnd: () => void;
  onDragOver: (row: HostRow, event: DragEvent<HTMLTableRowElement>) => void;
  onDrop: (row: HostRow) => void;
  onEdit: (row: HostRow) => void;
  onDuplicate: (row: HostRow) => void;
  onToggle: (row: HostRow, checked: boolean) => void;
  onDelete: (row: HostRow) => void;
};

export function HostsTable({
  rows,
  hostsById,
  pending,
  reorderDisabled,
  dropTarget,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
  onEdit,
  onDuplicate,
  onToggle,
  onDelete,
}: HostsTableProps) {
  const { t } = useTranslation();

  return (
    <div className="hidden overflow-hidden rounded-xl border md:block">
      <Table>
        <TableHeader className="bg-muted/40">
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-10" />
            <TableHead>{t("hostsPage.name")}</TableHead>
            <TableHead>{t("hostsPage.addressPort")}</TableHead>
            <TableHead>{t("hostsPage.enabled")}</TableHead>
            <TableHead>{t("hostsPage.inbound")}</TableHead>
            <TableHead>{t("hostsPage.groups")}</TableHead>
            <TableHead>{t("hostEditor.singleVisibility")}</TableHead>
            <TableHead className="w-28" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={row.id}
              draggable={!reorderDisabled}
              className={`cursor-pointer ${
                dropTarget?.rowId === row.id
                  ? dropTarget.position === "before"
                    ? "border-t-2 border-t-primary"
                    : "border-b-2 border-b-primary"
                  : ""
              }`}
              onDragStart={() => onDragStart(row)}
              onDragEnd={onDragEnd}
              onDragOver={(event) => onDragOver(row, event)}
              onDrop={() => onDrop(row)}
              onClick={() => onEdit(row)}
            >
              <TableCell>
                <GripVertical
                  className={`size-4 text-muted-foreground ${
                    reorderDisabled ? "opacity-30" : "cursor-grab"
                  }`}
                />
              </TableCell>
              <TableCell className="font-medium">
                <Button
                  type="button"
                  variant="link"
                  className="h-auto whitespace-normal p-0 text-start text-foreground"
                  onClick={(event) => {
                    event.stopPropagation();
                    onEdit(row);
                  }}
                >
                  {row.remark}
                </Button>
                <HostCompositionSummary
                  host={row}
                  hostsById={hostsById}
                  onEdit={onEdit}
                />
              </TableCell>
              <TableCell className="font-mono text-xs">
                {row.address}:{row.port ?? row.inbound_port}
              </TableCell>
              <TableCell>
                <div
                  className="w-fit"
                  onClick={(event) => event.stopPropagation()}
                >
                  <Switch
                    checked={row.enabled}
                    disabled={pending}
                    onCheckedChange={(checked) => onToggle(row, checked)}
                  />
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{row.inbound_tag}</Badge>
              </TableCell>
              <TableCell>
                <HostGroupBadges groups={row.groups} />
              </TableCell>
              <TableCell>
                {t(
                  row.show_when_composed
                    ? "hostsDialog.enabled"
                    : "hostsDialog.disabled",
                )}
              </TableCell>
              <TableCell onClick={(event) => event.stopPropagation()}>
                <div className="flex justify-end gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    disabled={pending}
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
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
