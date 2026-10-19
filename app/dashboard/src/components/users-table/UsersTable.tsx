import { ArrowDown, ArrowUp, Users } from "lucide-react";
import { useState } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { User } from "types/User";

import { UserCard, UserRow } from "./components/UserRow";
import { UsersDialogs } from "./components/UsersDialogs";
import { UsersPagination } from "./components/UsersPagination";
import { UsersToolbar } from "./components/UsersToolbar";

import { useUsersTable } from "./lib/hooks";

const statuses = [
  "active",
  "on_hold",
  "disabled",
  "limited",
  "expired",
] as const;

function SortIndicator({ sort, column }: { sort: string; column: string }) {
  if (sort.replace("-", "") !== column) {
    return null;
  }

  const classes = "size-3.5";

  return sort.startsWith("-") ? (
    <ArrowDown className={classes} />
  ) : (
    <ArrowUp className={classes} />
  );
}

const UsersTable = () => {
  const { t } = useTranslation();
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [creatingUser, setCreatingUser] = useState(false);
  const [qrUser, setQrUser] = useState<User | null>(null);
  const {
    filters,
    users,
    total,
    isLoading,
    isFetching,
    error,
    refetch,
    updateFilters,
    resetFilters,
  } = useUsersTable();

  const changeSort = (column: string) => {
    const currentColumn = filters.sort.replace("-", "");
    const sort =
      currentColumn === column && !filters.sort.startsWith("-")
        ? `-${column}`
        : column;

    updateFilters({ sort, offset: 0 });
  };

  const isFiltered = Boolean(
    filters.search || filters.status || filters.sort !== "-created_at",
  );

  return (
    <section className="w-full min-w-0 max-w-full space-y-4" id="users-table">
      <UsersToolbar
        filters={filters}
        isFetching={isFetching}
        onFiltersChange={updateFilters}
        onRefresh={() => void refetch()}
        onResetFilters={resetFilters}
        showResetFilters={isFiltered}
        onCreate={() => setCreatingUser(true)}
      />

      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-muted-foreground">
          {total} {t("users").toLowerCase()}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">
            {t("usersTable.status")}
          </span>
          <Select
            value={filters.status ?? "all"}
            onValueChange={(value) =>
              updateFilters({
                status:
                  value !== "all"
                    ? (value as typeof filters.status)
                    : undefined,
                offset: 0,
              })
            }
          >
            <SelectTrigger size="sm" className="min-w-32 capitalize">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">{t("usersTable.all")}</SelectItem>
                {statuses.map((status) => (
                  <SelectItem
                    value={status}
                    key={status}
                    className="capitalize"
                  >
                    {t(`status.${status}`)}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-6 text-center">
          <p className="text-sm text-destructive">
            {t("usersTable.loadError")}
          </p>
          <Button
            className="mt-3"
            variant="outline"
            onClick={() => void refetch()}
          >
            {t("usersTable.retry")}
          </Button>
        </div>
      ) : (
        <>
          <div className="hidden w-full max-w-full overflow-x-auto rounded-xl border md:block">
            <Table className="min-w-[960px] table-fixed">
              <colgroup>
                <col className="w-56" />
                <col className="w-64" />
                <col className="w-52" />
                <col className="w-80" />
                <col className="w-44" />
              </colgroup>
              <TableHeader className="bg-muted/40">
                <TableRow className="hover:bg-transparent">
                  <TableHead>
                    <button
                      className="flex items-center gap-1.5 relative"
                      onClick={() => changeSort("username")}
                    >
                      {t("username")}
                      <SortIndicator sort={filters.sort} column="username" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button
                      className="flex items-center gap-1.5 relative"
                      onClick={() => changeSort("expire")}
                    >
                      {t("usersTable.status")}
                      <SortIndicator sort={filters.sort} column="expire" />
                    </button>
                  </TableHead>
                  <TableHead className="w-52">
                    {t("usersTable.protocols")}
                  </TableHead>
                  <TableHead className="w-80 max-w-80">
                    <button
                      className="flex items-center gap-1.5 relative"
                      onClick={() => changeSort("used_traffic")}
                    >
                      {t("usersTable.dataUsage")}
                      <SortIndicator
                        sort={filters.sort}
                        column="used_traffic"
                      />
                    </button>
                  </TableHead>
                  <TableHead className="w-44" />
                </TableRow>
              </TableHeader>
              <TableBody
                className={cn(isFetching && !isLoading && "opacity-60")}
              >
                {isLoading
                  ? Array.from({ length: filters.limit ?? 10 }).map(
                      (_, index) => (
                        <TableRow key={index}>
                          <TableCell>
                            <Skeleton className="h-5 w-32" />
                          </TableCell>
                          <TableCell>
                            <Skeleton className="h-6 w-40" />
                          </TableCell>
                          <TableCell>
                            <Skeleton className="h-6 w-32" />
                          </TableCell>
                          <TableCell className="w-80 max-w-80">
                            <Skeleton className="h-8 w-full" />
                          </TableCell>
                          <TableCell>
                            <Skeleton className="ms-auto h-8 w-36" />
                          </TableCell>
                        </TableRow>
                      ),
                    )
                  : users.map((user) => (
                      <UserRow
                        user={user}
                        key={user.username}
                        onEdit={setEditingUser}
                        onShowQr={setQrUser}
                      />
                    ))}
              </TableBody>
            </Table>
          </div>

          <div
            className={cn(
              "grid gap-3 md:hidden",
              isFetching && !isLoading && "opacity-60",
            )}
          >
            {isLoading
              ? Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton className="h-40 rounded-xl" key={index} />
                ))
              : users.map((user) => (
                  <UserCard
                    user={user}
                    key={user.username}
                    onEdit={setEditingUser}
                    onShowQr={setQrUser}
                  />
                ))}
          </div>

          {!isLoading && users.length === 0 && (
            <div className="flex flex-col items-center gap-3 rounded-xl border px-6 py-12 text-center">
              <div className="rounded-full bg-muted p-3 text-muted-foreground">
                <Users className="size-6" />
              </div>
              <p className="text-sm text-muted-foreground">
                {isFiltered
                  ? t("usersTable.noUserMatched")
                  : t("usersTable.noUser")}
              </p>
              {!isFiltered && (
                <Button
                  onClick={() => setCreatingUser(true)}
                >
                  {t("create")}
                </Button>
              )}
            </div>
          )}
        </>
      )}

      {!error && (
        <UsersPagination
          filters={filters}
          total={total}
          onFiltersChange={updateFilters}
        />
      )}
      <UsersDialogs
        editingUser={editingUser}
        creatingUser={creatingUser}
        qrUser={qrUser}
        onEditingUserChange={setEditingUser}
        onCreatingUserChange={setCreatingUser}
        onQrUserChange={setQrUser}
      />
    </section>
  );
};

export default UsersTable;
