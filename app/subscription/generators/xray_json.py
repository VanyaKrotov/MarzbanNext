import json

from app.models.subscription_template import SubscriptionFormat
from app.subscription.client_metadata import get_server_description
from app.subscription.contracts import SubscriptionError
from app.subscription.generators.base import (
    apply_resolved_options, apply_xray_options, builder_arguments, finish, map_node,
)
from app.subscription.v2ray import V2rayJsonConfig
from app.subscription.template_directives import XrayDirectives, parse_directive, selected_sources, validate_directives
from app.subscription.validation import OutputValidator
from app.utils.helpers import UUIDEncoder
from app.utils.subscription_templates import render_template_document


class XrayJsonSubscriptionGenerator:
    def generate(self, data):
        documents, diagnostics = [], []
        host_ids_by_catalog = {}
        profiles = reversed(data.profiles) if data.reverse else data.profiles
        for profile in profiles:
            first = profile.connections[0]
            catalog_key = id(profile.sources)
            if catalog_key not in host_ids_by_catalog:
                host_ids_by_catalog[catalog_key] = tuple(connection.host_id for connection in profile.sources)
            document = render_template_document(SubscriptionFormat.v2ray_json, profile.template.content, {
                **first.context, "host": first.template_record(), "remarks": profile.remark,
                "host_ids": host_ids_by_catalog[catalog_key],
            }, profile.template.migration_settings)
            validate_directives(document, "v2ray-json")
            options = parse_directive(XrayDirectives, document.pop("marzban", {}))
            selected = self._select_connections(profile, options, diagnostics)
            if selected is None:
                continue
            outbounds = self._build_outbounds(selected, data.defaults)
            if not outbounds:
                continue
            document["remarks"] = profile.remark
            description = get_server_description(first, data.include_server_description)
            if description:
                metadata = document.setdefault("meta", {})
                if not isinstance(metadata, dict):
                    raise SubscriptionError("Xray profile meta must be an object")
                metadata["serverDescription"] = description
            document["outbounds"] = outbounds + document["outbounds"]
            # Historical default templates reference these conventional names without defining them.
            referenced = {rule.get("outboundTag") for rule in document.get("routing", {}).get("rules", [])}
            existing = {item.get("tag") for item in document["outbounds"]}
            for name, protocol in (("direct", "freedom"), ("block", "blackhole")):
                if name in referenced and name not in existing:
                    document["outbounds"].append({"tag": name, "protocol": protocol})
            OutputValidator().validate(document, "v2ray-json")
            documents.append(document)
        return finish(json.dumps(documents, cls=UUIDEncoder, ensure_ascii=False, indent=2) if documents else "",
                      data, "application/json", diagnostics)

    @staticmethod
    def _select_connections(profile, options, diagnostics):
        selected = [(profile.connections[0], "proxy")] if options.addVirtualHostAsOutbound else []
        for injection in options.injectHosts:
            sources = selected_sources(profile, injection, recipient=profile.owner, diagnostics=diagnostics)
            if not sources:
                return None
            for index, connection in enumerate(sources):
                tag = injection.tagPrefix if index == 0 else f"{injection.tagPrefix}-{index + 1}"
                selected.append((connection, tag))
        return selected

    @staticmethod
    def _build_outbounds(selected, defaults):
        builder = V2rayJsonConfig(template='{"outbounds": []}', defaults=defaults)
        outbounds = []
        for connection, tag in selected:
            generated = builder.add(**builder_arguments(connection), outbound_tag=tag, return_outbounds=True)
            if not generated:
                continue
            if len(generated) > 1:
                # Observatory selectors must never include fragment/noise dialer outbounds.
                dialer_tag = f"mb-dialer-{tag}"
                generated[1]["tag"] = dialer_tag
                generated[0].setdefault("streamSettings", {}).setdefault("sockopt", {})["dialerProxy"] = dialer_tag
            apply_resolved_options(generated[0], connection, "v2ray-json")
            apply_xray_options(generated[0], connection)
            generated[0] = map_node(generated[0], connection, "xrayJson")
            outbounds.extend(generated)
        return outbounds
