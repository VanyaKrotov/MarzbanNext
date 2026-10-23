import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { FieldDescription } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { useAllTemplatesQuery } from "@/pages/subscription-templates-page/lib/query";
import { useInboundsQuery } from "../../lib/query";
import { HostForm } from "./components/HostForm";
import type { HostDialogProps } from "./lib/types";

export function HostDialog(props: HostDialogProps) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent
        aria-describedby={undefined}
        className="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-2xl"
        onEscapeKeyDown={(event) => {
          // Radix observes Escape before the nested Base UI combobox closes its popup.
          const target = event.target;
          if (
            target instanceof Element &&
            target.closest(
              '[role="combobox"][aria-expanded="true"], [data-slot="combobox-content"]',
            )
          ) {
            event.preventDefault();
          }
        }}
      >
        <HostDialogContent {...props} />
      </DialogContent>
    </Dialog>
  );
}

function HostDialogContent(props: HostDialogProps) {
  const { t } = useTranslation();
  return (
    <>
      <DialogTitle className="flex flex-wrap items-center gap-2 pe-8">
        {t(props.host ? "hostEditor.editTitle" : "hostEditor.createTitle")}
        {props.host && (
          <Badge variant="secondary" className="font-mono tabular-nums">
            {t("hostsPage.id")}: {props.host.id}
          </Badge>
        )}
      </DialogTitle>
      <HostFormLoader {...props} />
    </>
  );
}

function HostFormLoader(props: HostDialogProps) {
  const { t } = useTranslation();
  const inbounds = useInboundsQuery(props.inboundTag ?? undefined);
  const templates = useAllTemplatesQuery();
  const queries = [inbounds, templates];

  if (queries.some((query) => query.isLoading))
    return <Skeleton className="h-48" />;
  if (queries.some((query) => query.isError)) {
    return (
      <FieldDescription>{t("hostsPage.loadErrorDescription")}</FieldDescription>
    );
  }
  if (!inbounds.data?.length) {
    return (
      <FieldDescription>
        {t("hostsPage.noInboundsDescription")}
      </FieldDescription>
    );
  }
  return (
    <HostForm
      {...props}
      inbounds={inbounds.data}
      templates={templates.data ?? []}
    />
  );
}
