import { useFormContext, useWatch } from "react-hook-form";
import type { InboundType } from "@/types/Inbound";
import type { HostFormValues } from "./form";

export function useSupportsXhttp(inbounds: InboundType[]) {
  const { control } = useFormContext<HostFormValues>();
  const inboundId = useWatch({
    control,
    name: "inbound_id",
    exact: true,
  });
  const network = inbounds.find((inbound) => inbound.id === inboundId)?.network;
  return network === "xhttp" || network === "splithttp";
}
