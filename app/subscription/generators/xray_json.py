import json

from app.models.subscription_template import SubscriptionFormat
from app.subscription.generators.base import (
    apply_resolved_options, apply_xray_options, builder_arguments, finish, map_node,
)
from app.subscription.v2ray import V2rayJsonConfig
from app.subscription.template_directives import XrayDirectives, parse_directive, selected_sources, validate_directives
from app.subscription.validation import OutputValidator
from app.utils.helpers import UUIDEncoder
from app.utils.subscription_templates import parse_subscription_document, render_subscription_template


class XrayJsonSubscriptionGenerator:
    def generate(self, data):
        documents, diagnostics = [], []
        profiles = reversed(data.profiles) if data.reverse else data.profiles
        for profile in profiles:
            first = profile.connections[0]
            content = render_subscription_template(profile.template.content, {
                **first.context, "host": first.template_record(), "remarks": profile.remark,
            })
            document = parse_subscription_document(SubscriptionFormat.v2ray_json, content)
            validate_directives(document, "v2ray-json")
            builder = V2rayJsonConfig(template='{"outbounds": []}', defaults=data.defaults)
            options = parse_directive(XrayDirectives, document.pop("marzban", {}))
            selected = [(first, "proxy")] if options.addVirtualHostAsOutbound else []
            empty_pool = False
            for injection in options.injectHosts:
                sources = selected_sources(profile, injection, recipient=profile.owner, diagnostics=diagnostics)
                if not sources:
                    empty_pool = True
                selected.extend((connection, injection.tagPrefix if index == 0
                                 else f"{injection.tagPrefix}-{index + 1}")
                                for index, connection in enumerate(sources))
            if empty_pool:
                continue
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
                if "server_description" in connection.client_options:
                    generated[0].setdefault("meta", {})[
                        "serverDescription"] = connection.client_options["server_description"]
                generated[0] = map_node(generated[0], connection, "xrayJson")
                outbounds.extend(generated)
            if not outbounds:
                continue
            document["remarks"] = profile.remark
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
