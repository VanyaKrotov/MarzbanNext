import { Copy, Plus, RefreshCw, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import Page from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
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
  const [editor, setEditor] = useState<{
    template: SubscriptionTemplate | null;
    duplicate: boolean;
  } | null>(null);
  const [action, setAction] = useState<TemplateAction | null>(null);
  const query = useTemplatesQuery(format, search, offset);
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
              onClick={() => setEditor({ template: null, duplicate: false })}
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
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                {t("subscriptionTemplates.allFormats")}
              </SelectItem>
              {subscriptionFormats.map((value) => (
                <SelectItem key={value} value={value}>
                  {t(formatLabelKeys[value])}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {query.isLoading ? (
          <Skeleton className="h-64" />
        ) : query.isError ? (
          <p role="alert">{t("subscriptionTemplates.loadError")}</p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("subscriptionTemplates.name")}</TableHead>
                  <TableHead>{t("subscriptionTemplates.format")}</TableHead>
                  <TableHead className="text-end">
                    {t("subscriptionTemplates.actions")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data?.items.map((template) => (
                  <TableRow
                    key={template.id}
                    className="cursor-pointer"
                    onClick={() => setEditor({ template, duplicate: false })}
                  >
                    <TableCell>
                      <button type="button" className="text-start font-medium">
                        {template.name}
                      </button>
                      {template.is_default && (
                        <Badge variant="secondary" className="ms-2">
                          {t("subscriptionTemplates.default")}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>{t(formatLabelKeys[template.format])}</TableCell>
                    <TableCell onClick={(event) => event.stopPropagation()}>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={t("subscriptionTemplates.duplicate")}
                          onClick={() =>
                            setEditor({ template, duplicate: true })
                          }
                        >
                          <Copy />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={template.is_default}
                          aria-label={t("subscriptionTemplates.setDefault")}
                          onClick={() =>
                            setAction({ template, type: "default" })
                          }
                        >
                          <Star />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={template.is_default}
                          aria-label={t("subscriptionTemplates.delete")}
                          onClick={() =>
                            setAction({ template, type: "delete" })
                          }
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
        <div className="flex items-center justify-end gap-3 text-sm">
          <span>{query.data?.total ?? 0}</span>
          <Button
            variant="outline"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            {t("subscriptionTemplates.previous")}
          </Button>
          <Button
            variant="outline"
            disabled={offset + 50 >= (query.data?.total ?? 0)}
            onClick={() => setOffset(offset + 50)}
          >
            {t("subscriptionTemplates.next")}
          </Button>
        </div>
      </div>
      <TemplateDialog
        template={editor?.template ?? null}
        duplicate={editor?.duplicate ?? false}
        open={editor !== null}
        onOpenChange={(open) => {
          if (!open) setEditor(null);
        }}
      />
      <TemplateActionDialog action={action} onClose={() => setAction(null)} />
    </Page>
  );
}
