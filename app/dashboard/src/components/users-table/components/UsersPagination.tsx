import { TablePagination } from "@/components/table-pagination";
import type { UsersFilter } from "../lib/types";
import { setUsersPerPageLimitSize } from "utils/userPreferenceStorage";

export function UsersPagination({
  filters,
  total,
  onFiltersChange,
}: {
  filters: UsersFilter;
  total: number;
  onFiltersChange: (filters: Partial<UsersFilter>) => void;
}) {
  return (
    <TablePagination
      limit={filters.limit ?? 10}
      offset={filters.offset ?? 0}
      total={total}
      onChange={(pagination) => {
        if (pagination.limit !== (filters.limit ?? 10)) {
          setUsersPerPageLimitSize(String(pagination.limit));
        }
        onFiltersChange(pagination);
      }}
    />
  );
}
