import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { HostType } from "../types";

export function HostCompositionSummary({
  host,
  hostsById: byId,
  onEdit,
}: {
  host: HostType;
  hostsById: ReadonlyMap<number, HostType>;
  onEdit: (host: HostType) => void;
}) {
  const { t } = useTranslation();
  if (!host.balancer_settings && !host.member_of.length) return null;
  return (
    <details
      onClick={(event) => event.stopPropagation()}
      className="mt-1 text-xs"
    >
      <summary className="cursor-pointer text-muted-foreground">
        {host.balancer_settings && (
          <Badge variant="outline">
            {t("hostEditor.composition")}: {host.linked_host_ids.length + 1}
          </Badge>
        )}
        {host.member_of.length > 0 && (
          <span className="ms-1">
            {t("hostEditor.memberOf", { count: host.member_of.length })}
          </span>
        )}
      </summary>
      <div className="mt-2 flex flex-col gap-2">
        {host.balancer_settings && (
          <>
            {[host.id, ...host.linked_host_ids].map((id) => {
              const member = byId.get(id);
              return (
                <Button
                  key={id}
                  variant="link"
                  size="sm"
                  type="button"
                  disabled={!member}
                  onClick={() => member && onEdit(member)}
                  className="h-auto justify-start whitespace-normal p-0 text-xs"
                >
                  {member
                    ? `${member.remark} — ${member.address}:${member.port ?? t("hostEditor.portFromInbound")} (${member.inbound_tag})`
                    : String(id)}
                </Button>
              );
            })}
            <span>
              {t("hostEditor.strategy")}:{" "}
              {t(`hostEditor.strategies.${host.balancer_settings.strategy}`)}
            </span>
            {Object.entries(host.balancer_settings.clients).map(
              ([target, options]) =>
                options.strategy && (
                  <span key={target}>
                    {t(`subscriptionTemplates.formats.${target}`)}:{" "}
                    {t(`hostEditor.strategies.${options.strategy}`)}
                  </span>
                ),
            )}
          </>
        )}
        {host.member_of.map((owner) => (
          <Button
            key={owner.id}
            variant="link"
            size="sm"
            type="button"
            className="h-auto justify-start p-0 text-xs"
            disabled={!byId.has(owner.id)}
            onClick={() => {
              const item = byId.get(owner.id);
              if (item) onEdit(item);
            }}
          >
            {owner.remark}
          </Button>
        ))}
      </div>
    </details>
  );
}
