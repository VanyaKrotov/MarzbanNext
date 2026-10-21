import { useTranslation } from "react-i18next";
import { FieldGroup } from "@/components/ui/field";
import { BalancerOptionField } from "./BalancerOptionField";

const PREFIX = "balancer_clients.v2ray-json.strategy_settings" as const;

export function LeastLoadFields({ pending }: { pending: boolean }) {
  const { t } = useTranslation();
  return (
    <FieldGroup>
      <span className="text-sm font-medium">
        {t("hostEditor.leastLoadOptions")}
      </span>
      <BalancerOptionField
        name={`${PREFIX}.expected`}
        shouldUnregister
        label={t("hostEditor.expected")}
        kind="number"
        min={1}
        pending={pending}
      />
      <BalancerOptionField
        name={`${PREFIX}.max_rtt_ms`}
        shouldUnregister
        label={t("hostEditor.max_rtt_ms")}
        kind="number"
        min={1}
        pending={pending}
      />
      <BalancerOptionField
        name={`${PREFIX}.failure_tolerance`}
        shouldUnregister
        label={t("hostEditor.failure_tolerance")}
        kind="number"
        min={0}
        max={1}
        step="any"
        pending={pending}
      />
      <BalancerOptionField
        name={`${PREFIX}.baselines_ms`}
        shouldUnregister
        label={t("hostEditor.baselines_ms")}
        kind="json"
        placeholder="[100,200]"
        pending={pending}
      />
      <BalancerOptionField
        name={`${PREFIX}.costs`}
        shouldUnregister
        label={t("hostEditor.costs")}
        kind="json"
        placeholder={'[{"host_id":1,"value":1}]'}
        pending={pending}
      />
    </FieldGroup>
  );
}
