import { Plus, RefreshCw, Star, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import Page from "@/components/page";
import { TablePagination } from "@/components/table-pagination";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { TemplateDialog } from "./components/TemplateDialog";
import {
  TemplateActionDialog,
  type TemplateAction,
} from "./components/TemplateActionDialog";
import {
  formatLabelKeys,
  subscriptionFormats,
  useTemplatesQuery,
  type SubscriptionTemplate,
} from "./lib/query";

export default function SubscriptionTemplatesPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [format, setFormat] = useState("");
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(10);
  const [editor, setEditor] = useState<{
    template: SubscriptionTemplate | null;
  } | null>(null);
  const [action, setAction] = useState<TemplateAction | null>(null);
  const query = useTemplatesQuery(format, search, offset, limit);
  const total = query.data?.total;

  useEffect(() => {
    if (total === undefined) return;
    const lastOffset = Math.max(0, Math.ceil(total / limit) - 1) * limit;
    setOffset((current) => Math.min(current, lastOffset));
  }, [total, limit]);
  return (
    <Page>
      <Page.Header
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="icon"
              aria-label={t("subscriptionTemplates.refresh")}
              onClick={() => void query.refetch()}
            >
              <RefreshCw className={query.isFetching ? "animate-spin" : ""} />
            </Button>
            <Button
              onClick={() => setEditor({ template: null })}
            >
              <Plus />
              {t("create")}
            </Button>
          </div>
        }
      >
        <h1 className="font-semibold">{t("subscriptionTemplates.title")}</h1>
      </Page.Header>
      <div className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <Input
            className="sm:max-w-sm"
            value={search}
            placeholder={t("subscriptionTemplates.search")}
            aria-label={t("subscriptionTemplates.search")}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
          <Select
            value={format || "all"}
            onValueChange={(value) => {
              setFormat(value === "all" ? "" : value);
              setOffset(0);
            }}
          >
            <SelectTrigger className="md:ms-auto">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">
                  {t("subscriptionTemplates.allFormats")}
                </SelectItem>
                {subscriptionFormats.map((value) => (
                  <SelectItem key={value} value={value}>
                    {t(formatLabelKeys[value])}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
        {query.isLoading ? (
          <Skeleton className="h-64" />
        ) : query.isError ? (
          <p role="alert">{t("subscriptionTemplates.loadError")}</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border">
            <Table>
              <TableHeader className="bg-muted/40">
                <TableRow className="hover:bg-transparent">
                  <TableHead>{t("subscriptionTemplates.name")}</TableHead>
                  <TableHead>{t("subscriptionTemplates.format")}</TableHead>
                  <TableHead className="w-24">
                    <span className="sr-only">
                      {t("subscriptionTemplates.actions")}
                    </span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data?.items.map((template) => (
                  <TableRow
                    key={template.id}
                    className="cursor-pointer"
                    onClick={() => setEditor({ template })}
                  >
                    <TableCell>
                      <button type="button" className="text-start font-medium">
                        {template.name}
                      </button>
                    </TableCell>
                    <TableCell>{t(formatLabelKeys[template.format])}</TableCell>
                    <TableCell onClick={(event) => event.stopPropagation()}>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          disabled={template.is_default}
                          aria-label={t(
                            template.is_default
                              ? "subscriptionTemplates.default"
                              : "subscriptionTemplates.setDefault",
                          )}
                          aria-pressed={template.is_default}
                          onClick={(event) => {
                            event.stopPropagation();
                            if (!template.is_default) {
                              setAction({ template, type: "default" });
                            }
                          }}
                        >
                          <Star
                            fill={template.is_default ? "currentColor" : "none"}
                          />
                        </Button>
                        <Button
                          variant="destructive"
                          size="icon-sm"
                          disabled={template.is_default}
                          aria-label={t("subscriptionTemplates.delete")}
                          onClick={(event) => {
                            event.stopPropagation();
                            setAction({ template, type: "delete" });
                          }}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!query.data?.items.length && (
                  <TableRow>
                    <TableCell
                      colSpan={3}
                      className="py-10 text-center text-muted-foreground"
                    >
                      {t("subscriptionTemplates.empty")}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        )}
        {!query.isError && (
          <TablePagination
            limit={limit}
            offset={offset}
            total={total ?? 0}
            onChange={(pagination) => {
              setLimit(pagination.limit);
              setOffset(pagination.offset);
            }}
          />
        )}
      </div>
      <TemplateDialog
        template={editor?.template ?? null}
        open={editor !== null}
        onOpenChange={(open) => {
          if (!open) setEditor(null);
        }}
      />
      <TemplateActionDialog action={action} onClose={() => setAction(null)} />
    </Page>
  );
}
