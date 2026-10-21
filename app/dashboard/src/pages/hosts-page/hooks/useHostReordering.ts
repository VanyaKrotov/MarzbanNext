import { useState, type DragEvent } from "react";
import { reorderHost, type HostRow } from "../lib/model";
import type { HostsSchema } from "../types";

export type HostsDropTarget = {
  rowId: number;
  position: "before" | "after";
} | null;

export function useHostReordering(
  rows: HostsSchema,
  reorderDisabled: boolean,
  onReorder: (hosts: HostsSchema) => void,
) {
  const [draggedRow, setDraggedRow] = useState<HostRow | null>(null);
  const [dropTarget, setDropTarget] = useState<HostsDropTarget>(null);
  const dragStart = (row: HostRow) => {
    if (!reorderDisabled) setDraggedRow(row);
  };

  const dragEnd = () => {
    setDraggedRow(null);
    setDropTarget(null);
  };

  const dragOver = (row: HostRow, event: DragEvent<HTMLTableRowElement>) => {
    event.preventDefault();
    if (reorderDisabled || !draggedRow) {
      return;
    }

    const bounds = event.currentTarget.getBoundingClientRect();
    const position =
      event.clientY < bounds.top + bounds.height / 2 ? "before" : "after";
    setDropTarget((current) =>
      current?.rowId === row.id && current.position === position
        ? current
        : { rowId: row.id, position },
    );
  };

  const drop = (target: HostRow) => {
    if (reorderDisabled || !draggedRow || !dropTarget) {
      dragEnd();
      return;
    }

    const sourceIndex = rows.findIndex((row) => row.id === draggedRow.id);
    const targetRowIndex = rows.findIndex((row) => row.id === target.id);
    if (sourceIndex < 0 || targetRowIndex < 0) {
      dragEnd();
      return;
    }

    let targetIndex =
      targetRowIndex + (dropTarget.position === "after" ? 1 : 0);
    if (sourceIndex < targetIndex) targetIndex -= 1;

    if (sourceIndex !== targetIndex) {
      onReorder(reorderHost(rows, sourceIndex, targetIndex));
    }
    dragEnd();
  };

  return { dropTarget, dragStart, dragEnd, dragOver, drop };
}
