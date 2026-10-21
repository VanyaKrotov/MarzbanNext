"""The persistence boundary of client configuration generation."""

from copy import deepcopy

from app.subscription.contracts import HostSnapshot, SubscriptionSnapshot, TemplateSnapshot


def snapshot_host(host) -> HostSnapshot:
    return HostSnapshot(
        id=host.id, inbound_id=host.inbound_id, inbound_tag=host.inbound_tag,
        remark=host.remark, address=host.address, port=host.port, enabled=host.enabled,
        position=host.position, is_hidden=host.is_hidden,
        overrides=deepcopy(host.overrides),
        group_ids=tuple(group.id for group in host.groups),
        subscription_template_ids=dict(host.subscription_template_ids),
    )


class SubscriptionSnapshotLoader:
    def load(self, db, runtime_settings=None) -> SubscriptionSnapshot:
        from app.db.crud.proxy_hosts import list_hosts
        from app.db.models.proxies import ProxyInbound
        from app.db.models.subscription_templates import SubscriptionTemplate
        from app.utils.runtime_settings import get_runtime_settings
        from app.utils.subscription_template_defaults import GENERATOR_TEMPLATE_SOURCES
        from app.utils.xray_config_registry import get_enabled_inbound_registry

        registry = get_enabled_inbound_registry(db)
        rows = db.query(ProxyInbound).filter(ProxyInbound.enabled.is_(True)).all()
        settings = runtime_settings or get_runtime_settings()
        return SubscriptionSnapshot(
            hosts=tuple(snapshot_host(host) for host in list_hosts(db).all()),
            inbounds={row.id: deepcopy(registry.inbounds_by_tag[row.tag])
                      for row in rows if row.tag in registry.inbounds_by_tag},
            raw_inbounds={row.id: deepcopy(row.content) for row in rows},
            templates={row.id: TemplateSnapshot(row.id, row.format, row.content)
                       for row in db.query(SubscriptionTemplate).all()},
            defaults={key: getattr(settings, key) for key in GENERATOR_TEMPLATE_SOURCES},
            external_config=settings.external_config,
        )
