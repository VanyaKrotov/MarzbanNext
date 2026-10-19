import { ChevronLeft, ChevronRight } from "lucide-react";
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

type PaginationState = { limit: number; offset: number };

export function TablePagination({
  limit,
  offset,
  total,
  onChange,
}: PaginationState & {
  total: number;
  onChange: (pagination: PaginationState) => void;
}) {
  const { t } = useTranslation();
  const page = Math.floor(offset / limit);
  const pages = Math.ceil(total / limit);

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Select
          value={String(limit)}
          onValueChange={(value) =>
            onChange({ limit: Number(value), offset: 0 })
          }
        >
          <SelectTrigger
            size="sm"
            className="w-16 text-foreground"
            aria-label={t("itemsPerPage")}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {[10, 20, 30].map((value) => (
                <SelectItem value={String(value)} key={value}>
                  {value}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        {t("itemsPerPage")}
      </div>

      <div className="flex items-center justify-end gap-2">
        <span className="text-sm text-muted-foreground">
          {pages ? page + 1 : 0} / {pages}
        </span>
        <Button
          variant="outline"
          size="icon-sm"
          aria-label={t("previous")}
          disabled={page <= 0}
          onClick={() => onChange({ limit, offset: (page - 1) * limit })}
        >
          <ChevronLeft className="rtl:rotate-180" />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          aria-label={t("next")}
          disabled={page + 1 >= pages}
          onClick={() => onChange({ limit, offset: (page + 1) * limit })}
        >
          <ChevronRight className="rtl:rotate-180" />
        </Button>
      </div>
    </div>
  );
}
