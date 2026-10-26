import { FieldGroup } from "@/components/ui/field";
import type { InboundType } from "@/types/Inbound";
import type { SubscriptionTemplate } from "@/pages/subscription-templates-page/lib/query";
import type { HostGroupType } from "../../../types";
import {
  AddressField,
  InboundField,
  PortField,
  RemarkField,
} from "./BasicHostFields";
import { GroupsField } from "./GroupsField";
import { SubscriptionTemplateFields } from "./SubscriptionTemplateFields";

export function CoreFields({
  inbounds,
  groups,
  templates,
  pending,
}: {
  inbounds: InboundType[];
  groups: HostGroupType[];
  templates: SubscriptionTemplate[];
  pending: boolean;
}) {
  return (
    <FieldGroup>
      <RemarkField pending={pending} />
      <InboundField inbounds={inbounds} pending={pending} />
      <GroupsField groups={groups} pending={pending} />
      <FieldGroup className="grid grid-cols-[minmax(0,1fr)_7rem] items-start gap-3">
        <AddressField pending={pending} />
        <PortField inbounds={inbounds} pending={pending} />
      </FieldGroup>
      <SubscriptionTemplateFields templates={templates} pending={pending} />
    </FieldGroup>
  );
}
