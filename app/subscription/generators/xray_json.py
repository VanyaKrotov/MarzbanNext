import json

from app.models.subscription_template import SubscriptionFormat
from app.subscription.generators.base import apply_resolved_options, apply_xray_options, builder_arguments, finish, map_node
from app.subscription.v2ray import V2rayJsonConfig
from app.subscription.validation import OutputValidator
from app.utils.helpers import UUIDEncoder
from app.utils.subscription_templates import parse_subscription_document, render_subscription_template


class XrayBalancerBuilder:
    def apply(self, document, profile, tags):
        options = profile.balancer
        prefix = f"mb-auto-{profile.owner.id}-"
        routing = document.setdefault("routing", {})
        balancer_tag = f"mb-auto-{profile.owner.id}"
        strategy = {"type": {"least_ping": "leastPing", "least_load": "leastLoad",
                             "round_robin": "roundRobin", "random": "random"}[options["strategy"]]}
        settings = options.get("strategy_settings")
        if settings:
            mapped = {}
            for key, value in settings.items():
                if key == "max_rtt_ms":
                    mapped["maxRTT"] = f"{value}ms"
                elif key == "failure_tolerance":
                    mapped["tolerance"] = value
                elif key == "baselines_ms":
                    mapped["baselines"] = [f"{item}ms" for item in value]
                elif key == "costs":
                    mapped["costs"] = [{"regexp": False, "match": tags[item["host_id"]], "value": item["value"]}
                                       for item in value if item["host_id"] in tags]
                else:
                    mapped[key] = value
            strategy["settings"] = mapped
        routing.setdefault("balancers", []).append({"tag": balancer_tag, "selector": [prefix], "strategy": strategy})
        # Existing rules keep their order. References to the single-profile proxy become the balancer.
        for rule in routing.setdefault("rules", []):
            if rule.get("outboundTag") == "proxy":
                rule.pop("outboundTag")
                rule["balancerTag"] = balancer_tag
        routing["rules"].append({"type": "field", "network": "tcp,udp", "balancerTag": balancer_tag})
        if options["strategy"] in {"least_ping", "least_load"}:
            generated = {"subjectSelector": [prefix], "probeUrl": options["probe_url"],
                         "probeInterval": f"{options['probe_interval']}s",
                         "enableConcurrency": options.get("enable_concurrency", True)}
            observer = document.setdefault("observatory", {})
            if observer and any(observer.get(key, value) != value for key, value in generated.items()
                                if key != "subjectSelector"):
                from app.subscription.contracts import SubscriptionError

                raise SubscriptionError("Template observatory conflicts with automatic profile settings")
            generated["subjectSelector"] = list(dict.fromkeys(observer.get("subjectSelector", []) + [prefix]))
            observer.update(generated)


class XrayJsonSubscriptionGenerator:
    def generate(self, data):
        documents = []
        profiles = reversed(data.profiles) if data.reverse else data.profiles
        for profile in profiles:
            first = profile.connections[0]
            content = render_subscription_template(profile.template.content, {
                **first.context, "host": first.template_record(), "remarks": profile.remark,
            })
            document = parse_subscription_document(SubscriptionFormat.v2ray_json, content)
            builder = V2rayJsonConfig(template='{"outbounds": []}', defaults=data.defaults)
            outbounds, tags = [], {}
            for connection in profile.connections:
                tag = f"mb-auto-{profile.owner.id}-host-{connection.host_id}" if profile.automatic else "proxy"
                generated = builder.add(**builder_arguments(connection), outbound_tag=tag, return_outbounds=True)
                if not generated:
                    continue
                if len(generated) > 1:
                    # Observatory selectors must never include fragment/noise dialer outbounds.
                    dialer_tag = f"mb-dialer-{profile.owner.id}-host-{connection.host_id}"
                    generated[1]["tag"] = dialer_tag
                    generated[0].setdefault("streamSettings", {}).setdefault("sockopt", {})["dialerProxy"] = dialer_tag
                apply_resolved_options(generated[0], connection, "v2ray-json")
                apply_xray_options(generated[0], connection)
                if "server_description" in connection.client_options:
                    generated[0].setdefault("meta", {})[
                        "serverDescription"] = connection.client_options["server_description"]
                generated[0] = map_node(generated[0], connection, "xrayJson")
                tags[connection.host_id] = generated[0]["tag"]
                outbounds.extend(generated)
            if not outbounds:
                continue
            document["remarks"] = profile.remark
            document["outbounds"] = outbounds + document["outbounds"]
            if profile.automatic:
                XrayBalancerBuilder().apply(document, profile, tags)
            # Historical default templates reference these conventional names without defining them.
            referenced = {rule.get("outboundTag") for rule in document.get("routing", {}).get("rules", [])}
            existing = {item.get("tag") for item in document["outbounds"]}
            for name, protocol in (("direct", "freedom"), ("block", "blackhole")):
                if name in referenced and name not in existing:
                    document["outbounds"].append({"tag": name, "protocol": protocol})
            OutputValidator().validate(document, "v2ray-json")
            documents.append(document)
        return finish(json.dumps(documents, cls=UUIDEncoder, ensure_ascii=False, indent=2) if documents else "",
                      data, "application/json")
