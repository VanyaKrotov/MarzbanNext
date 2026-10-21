import type { InboundType } from "@/types/Inbound";
import type { SubscriptionTemplate } from "@/pages/subscription-templates-page/lib/query";
import type {
  HostCapabilities,
  HostGroupType,
  HostPayload,
  HostType,
} from "../../../types";

export type HostDialogProps = {
  open: boolean;
  host: HostType | null;
  inboundTag: string | null;
  hostGroups: HostGroupType[];
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: HostPayload) => void;
};

export type HostFormProps = HostDialogProps & {
  inbounds: InboundType[];
  templates: SubscriptionTemplate[];
  hosts: HostType[];
  capabilities: HostCapabilities;
};
