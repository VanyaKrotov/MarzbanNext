export type ProtocolType =
  | "vmess"
  | "vless"
  | "trojan"
  | "shadowsocks"
  | "socks"
  | "hysteria";

export type InboundType = {
  id: number;
  tag: string;
  protocol: ProtocolType;
  network: string;
  tls: string;
  port?: number;
  nodes: InboundNodeRef[];
};

export type InboundNodeRef = {
  id: number;
  name: string;
};

export type InboundsResponse = Record<ProtocolType, InboundType[]>;
export type InboundsMap = Map<ProtocolType, InboundType[]>;

export type XrayCapabilities = {
  inbound_protocols: string[];
  outbound_protocols: string[];
  account_protocols: ProtocolType[];
  runtime_api_protocols: ProtocolType[];
  transports: string[];
  securities: string[];
  legacy_transport_aliases: Record<string, string>;
};
