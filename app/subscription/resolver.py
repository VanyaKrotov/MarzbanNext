"""Resolve one host independently of its role in single or automatic profiles."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import random
import secrets

from app.subscription.contracts import ConnectionInput, ResolvedConnection, SubscriptionError


@dataclass
class ResolveContext:
    variables: dict
    random: random.Random = field(default_factory=random.SystemRandom)
    salt: object = secrets.token_hex

    def choose(self, value):
        if isinstance(value, str):
            value = value.split(",")
        if not value:
            return ""
        return str(self.random.choice(value)).strip().replace("*", self.salt(8)).format_map(self.variables)


class ProtocolResolver:
    def resolve(self, protocol: str, credentials: dict) -> dict:
        from app.models.proxy import ProxySettings

        identity = {"vmess": "id", "vless": "id", "trojan": "password",
                    "shadowsocks": "password", "hysteria": "auth"}.get(protocol)
        if identity is None or not credentials.get(identity):
            raise SubscriptionError(f"Missing account credentials for {protocol}")
        # Validate existing credentials without ever generating replacement identities.
        return ProxySettings.from_dict(protocol, credentials).model_dump(mode="json")


class SecurityResolver:
    def resolve(self, inbound, overrides, address, context):
        security = overrides.get("security", {})
        inbound["tls"] = security.get("mode", inbound.get("tls", "none"))
        inbound["sni"] = context.choose(security.get("sni", inbound.get("sni", [])))
        if security.get("keep_sni_blank"):
            inbound["sni"] = ""
        elif security.get("sni_from_address"):
            inbound["sni"] = address
        for source, target in (("fingerprint", "fp"), ("allow_insecure", "ais")):
            if source in security:
                inbound[target] = security[source]
        if "alpn" in security:
            inbound["alpn"] = ",".join(security["alpn"])
        if inbound.get("sids"):
            inbound["sid"] = context.random.choice(inbound["sids"])
        return deepcopy(security)


class TransportResolver:
    def resolve(self, inbound, raw, overrides, context):
        transport = overrides.get("transport", {})
        inbound["host"] = context.choose(transport.get("host", inbound.get("host", [])))
        inbound["path"] = transport.get("path", inbound.get("path", "")).format_map(context.variables)
        inbound["random_user_agent"] = transport.get("random_user_agent", False)
        if transport.get("use_sni_as_host"):
            inbound["host"] = inbound["sni"]
        stream = raw.get("streamSettings", {})
        network = inbound["network"]
        source = stream.get(network + "Settings", {})
        resolved = {}
        if "headers" in source:
            resolved["headers"] = deepcopy(source["headers"])
        if "path" in transport or "path" in source or "serviceName" in source:
            resolved["path"] = inbound["path"]
        if "host" in transport or "host" in source or "Host" in source.get("headers", {}) or transport.get("use_sni_as_host"):
            resolved["host"] = inbound["host"]
        if "heartbeatPeriod" in source:
            resolved["heartbeatPeriod"] = source["heartbeatPeriod"]
        if inbound["network"] not in {"xhttp", "splithttp"}:
            return resolved
        source = stream.get("xhttpSettings") or stream.get("splithttpSettings") or {}
        xhttp = transport.get("xhttp", {})
        if "extra" in xhttp:
            extra = deepcopy(xhttp["extra"])
            # Old normalized fields must not bypass an explicit replacement, including {}.
            for key in source.get("extra", {}):
                inbound.pop(key, None)
            for key in ("scMaxBufferedPosts", "xPaddingObfsMode", "uplinkHTTPMethod",
                        "scMaxEachPostBytes", "scMinPostsIntervalMs", "xPaddingBytes", "xmux", "noGRPCHeader"):
                inbound.pop(key, None)
        else:
            extra = deepcopy(source.get("extra") or {})
            for key in ("scMaxBufferedPosts", "xPaddingObfsMode", "uplinkHTTPMethod"):
                if key in inbound:
                    extra[key] = inbound[key]
        inbound["_xhttp_extra"] = extra
        return resolved


class ConnectionResolver:
    def resolve(self, data: ConnectionInput, context: ResolveContext) -> ResolvedConnection:
        inbound = deepcopy(data.inbound)
        variables = dict(context.variables, PROTOCOL=inbound["protocol"], TRANSPORT=inbound["network"])
        context = ResolveContext(variables, context.random, context.salt)
        address = context.choose(data.host.address)
        inbound["port"] = data.host.port if data.host.port is not None else inbound["port"]
        if isinstance(inbound["port"], str):
            inbound["port"] = int(context.choose(inbound["port"]))
        if not 1 <= inbound["port"] <= 65535:
            raise SubscriptionError(f"Invalid port for host {data.host.id}")
        overrides = data.host.overrides
        security = SecurityResolver().resolve(inbound, overrides, address, context)
        transport = TransportResolver().resolve(inbound, data.raw_inbound, overrides, context)
        inbound.update({
            "mux_enable": overrides.get("mux", {}).get("enabled", False),
            "fragment_setting": overrides.get("fragment"), "noise_setting": overrides.get("noise"),
        })
        return ResolvedConnection(
            host_id=data.host.id, remark=data.host.remark.format_map(variables), address=address,
            port=inbound["port"], inbound=inbound,
            credentials=ProtocolResolver().resolve(inbound["protocol"], data.credentials), context=variables,
            client_options=deepcopy(overrides.get("clients", {})), mapper=deepcopy(overrides.get("mapper", {})),
            stream=deepcopy(overrides.get("stream", {})), mux=deepcopy(overrides.get("mux", {})),
            raw_inbound=deepcopy(data.raw_inbound),
            security=security, transport=transport,
        )
