import { FieldGroup } from "@/components/ui/field";
import type { InboundType } from "@/types/Inbound";
import type { HostGroupType } from "../../../types";
import {
  AddressField,
  InboundField,
  PortField,
  RemarkField,
} from "./BasicHostFields";
import { GroupsField } from "./GroupsField";

export function CoreFields({
  inbounds,
  groups,
  pending,
}: {
  inbounds: InboundType[];
  groups: HostGroupType[];
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
    </FieldGroup>
  );
}
