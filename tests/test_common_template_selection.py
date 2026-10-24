"""Common documents follow catalog defaults; host bindings only enable their format."""

from dataclasses import replace
import json
from unittest import TestCase

import yaml

from app.db.crud import proxy_hosts, subscription_templates
from app.db.models.subscription_templates import SubscriptionTemplate
from app.db.models.proxies import ProxyInbound
from app.models.host import HostCreate, HostPatch
from app.subscription.contracts import SubscriptionError
from app.subscription.planning import ProfilePlanner
from app.subscription.resolver import ResolveContext

import test_unified_hosts as fixtures


COMMON_FORMATS = ("sing-box", "clash", "outline")


def automatic_template(target, ids):
    selector = {"selectFrom": "ALL", "selector": {"type": "ids", "values": ids}}
    if target == "sing-box":
        return {"outbounds": [{"tag": "best", "type": "urltest", "outbounds": [],
                               "marzban": {"includeProxies": True, **selector}}], "route": {"final": "best"}}
    return {"proxies": [], "proxy-groups": [{"name": "best", "type": "url-test", "proxies": [],
                                             "url": "https://example.com", "interval": 60,
                                             "marzban": {"include-proxies": True, **selector}}]}


class CommonTemplateSelectionTests(TestCase):
    setUp = fixtures.UnifiedHostTests.setUp
    tearDown = fixtures.UnifiedHostTests.tearDown
    host = fixtures.UnifiedHostTests.host
    plan = fixtures.UnifiedHostTests.plan
    generate = fixtures.UnifiedHostTests.generate

    def template(self, target, marker, document=None, migration_settings=None):
        if target == "outline":
            content = '{% set _ = config.update({"template_marker": "' + marker + '"}) %}{{ config | tojson }}'
        elif target == "v2ray":
            content = "{{ links | map('replace', '#', '#" + marker + "-') | join('\\n') }}"
        else:
            content = json.dumps({**(document or ({"proxies": []} if target == "clash" else {"outbounds": []})),
                                  "template_marker": marker})
        template = SubscriptionTemplate(name=f"{target}-{marker}", format=target, content=content,
                                        migration_settings=migration_settings)
        self.db.add(template)
        self.db.commit()
        return template

    def set_default(self, template):
        for current in subscription_templates.get_defaults(self.db):
            if current.format == template.format:
                current.default_marker = None
        self.db.flush()
        template.default_marker = 1
        self.db.commit()

    def assign(self, host, target, template):
        proxy_hosts.update_host(self.db, host, HostPatch(subscription_template_ids={
            **host.subscription_template_ids, target: template.id}))

    def document(self, target, **options):
        output = self.generate(target, **options)
        return yaml.safe_load(output) if target == "clash" else json.loads(output)

    def test_defaults_ignore_host_order_visibility_and_conflicting_bindings(self):
        first, second = self.host("First"), self.host("Second")
        for target in COMMON_FORMATS:
            with self.subTest(target=target):
                default = self.template(target, "common")
                self.set_default(default)
                custom = self.template(target, "host")
                self.assign(first, target, custom)
                self.assertEqual(self.document(target)["template_marker"], "common")
                first.position = 100
                self.db.commit()
                self.assertEqual(self.document(target)["template_marker"], "common")
                proxy_hosts.update_host(self.db, first, HostPatch(is_hidden=True))
                self.assertEqual(self.document(target)["template_marker"], "common")
                self.assertEqual(self.document(target, root_ids={second.id})["template_marker"], "common")
                proxy_hosts.update_host(self.db, first, HostPatch(is_hidden=False))
                self.assertEqual(first.subscription_template_ids[target], custom.id)

    def test_changing_default_applies_to_existing_hosts_without_reassigning_bindings(self):
        host = self.host("First")
        saved = dict(host.subscription_template_ids)
        for target in COMMON_FORMATS:
            with self.subTest(target=target):
                for marker in ("first", "second"):
                    self.set_default(self.template(target, marker))
                    self.assertEqual(self.document(target)["template_marker"], marker)
                self.assertEqual(host.subscription_template_ids, saved)

    def test_explicit_override_is_optional_and_does_not_change_the_default(self):
        self.host("First")
        for target in COMMON_FORMATS:
            with self.subTest(target=target):
                self.set_default(self.template(target, "common"))
                custom = self.template(target, "explicit")
                self.assertEqual(self.document(target, template_id=custom.id)["template_marker"], "explicit")
                self.assertEqual(self.document(target)["template_marker"], "common")

    def test_personal_xray_and_uri_templates_remain_per_host(self):
        first, second = self.host("First"), self.host("Second")
        for target in ("v2ray-json", "v2ray"):
            with self.subTest(target=target):
                personal = self.template(target, "personal")
                self.assign(first, target, personal)
                self.set_default(self.template(target, "new-default"))
                output = self.generate(target)
                self.assertIn("personal", output)
                self.assertNotIn("new-default", output)
                if target == "v2ray-json":
                    self.assertEqual(json.loads(output)[0]["template_marker"], "personal")
                if target == "v2ray-json":
                    self.assertIn("second.example.com", output)
                else:
                    self.assertEqual(len(output.splitlines()), 2)
                self.assertNotEqual(second.subscription_template_ids[target], personal.id)
                self.assertNotIn("personal", self.generate(
                    target, template_id=second.subscription_template_ids[target]))

    def test_common_composition_injects_visible_and_hidden_sources_without_template_id(self):
        first, second = self.host("First"), self.host("Second", is_hidden=True)
        for target in ("sing-box", "clash"):
            with self.subTest(target=target):
                template = self.template(target, "automatic", automatic_template(target, [first.id, second.id]))
                self.set_default(template)
                for hidden in (False, True):
                    proxy_hosts.update_host(self.db, first, HostPatch(is_hidden=hidden))
                    document = self.document(target)
                    group = document["outbounds" if target == "sing-box" else "proxy-groups"][0]
                    self.assertEqual(group["outbounds" if target == "sing-box" else "proxies"], ["First", "Second"])
                    self.assertNotIn('"marzban":', json.dumps(document))
                proxy_hosts.update_host(self.db, first, HostPatch(is_hidden=False))

    def test_empty_required_pool_does_not_fall_back_to_another_template(self):
        self.host("First")
        for target in ("sing-box", "clash"):
            with self.subTest(target=target):
                self.set_default(self.template(target, "empty", automatic_template(target, [999999])))
                self.assertEqual(self.generate(target), "")

    def test_common_injection_respects_permissions_disabled_hosts_and_disabled_formats(self):
        allowed = self.host("Allowed")
        disabled = self.host("Disabled", enabled=False)
        excluded = self.host("Excluded", subscription_template_ids={})
        inbound = ProxyInbound(tag="Denied", content={**self.inbound.content, "tag": "Denied"})
        self.db.add(inbound)
        self.db.commit()
        denied = proxy_hosts.create_host(self.db, HostCreate(
            inbound_id=inbound.id, remark="Denied", address="denied.example.com"))
        ids = [host.id for host in (allowed, disabled, excluded, denied)]
        for target in ("sing-box", "clash"):
            with self.subTest(target=target):
                self.set_default(self.template(target, "restricted", automatic_template(target, ids)))
                document = self.document(target)
                group = document["outbounds" if target == "sing-box" else "proxy-groups"][0]
                self.assertEqual(group["outbounds" if target == "sing-box" else "proxies"], ["Allowed"])
                for host in (disabled, excluded, denied):
                    self.assertNotIn(host.address, json.dumps(document))

    def test_disabling_a_format_excludes_hosts_even_with_an_explicit_template(self):
        host = self.host("First")
        for target in COMMON_FORMATS:
            with self.subTest(target=target):
                bindings = dict(host.subscription_template_ids)
                template_id = bindings.pop(target)
                proxy_hosts.update_host(self.db, host, HostPatch(subscription_template_ids=bindings))
                self.assertEqual(self.generate(target), "")
                self.assertEqual(self.generate(target, template_id=template_id), "")

    def test_missing_default_is_an_error_without_a_host_template_fallback(self):
        self.host("First")
        for target in COMMON_FORMATS:
            snapshot, _, _ = self.plan(target)
            snapshot = replace(snapshot, default_template_ids={})
            with self.subTest(target=target), self.assertRaisesRegex(SubscriptionError, "Default.*missing"):
                ProfilePlanner().plan(snapshot, target, {"shadowsocks": {"password": "test"}},
                                      {"shadowsocks": ["SS"]}, ResolveContext({}))

    def test_default_jinja_and_migrated_balancers_render_after_selection(self):
        first = self.host("First", is_hidden=True)
        pool = automatic_template("sing-box", [first.id])
        template = self.template("sing-box", "migrated", {"outbounds": [], "route": {"final": "best"}},
                                 migration_settings={"version": 1, "aggregate": [{
                                     "enabled": True, "member_ids": [first.id], "node": pool["outbounds"][0]}]})
        template.content = '{% set label = "saved" %}' + template.content.replace('"migrated"', '{{ label | tojson }}')
        self.set_default(template)
        before = template.content, json.dumps(template.migration_settings)
        document = self.document("sing-box")
        self.assertEqual(document["template_marker"], "saved")
        self.assertEqual(document["outbounds"][0]["outbounds"], ["First"])
        self.assertEqual((template.content, json.dumps(template.migration_settings)), before)
