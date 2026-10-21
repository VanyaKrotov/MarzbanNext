import base64
from dataclasses import replace
import json
from unittest import TestCase

import yaml

from app.db.models.proxies import HostGroup
from app.db.models.subscription_templates import SubscriptionTemplate
from app.models.host import HostCreate, HostPatch
from app.models.subscription_template import SubscriptionFormat
from app.subscription.contracts import RenderInput, TemplateConflict
from app.subscription.generators import GeneratorRegistry
from app.subscription.planning import ProfilePlanner
from app.subscription.resolver import ResolveContext
from app.utils.subscription_templates import validate_subscription_template

import test_unified_hosts as fixtures


class TemplateCompositionTests(TestCase):
    setUp = fixtures.UnifiedHostTests.setUp
    tearDown = fixtures.UnifiedHostTests.tearDown
    host = fixtures.UnifiedHostTests.host
    plan = fixtures.UnifiedHostTests.plan
    generate = fixtures.UnifiedHostTests.generate

    def template(self, host, target, document):
        template = self.db.get(SubscriptionTemplate, host.subscription_template_ids[target])
        template.content = yaml.safe_dump(document) if target == "clash" else json.dumps(document)
        self.db.commit()
        return template

    def injection(self, ids, prefix="pool"):
        return {"selector": {"type": "ids", "values": ids}, "selectFrom": "ALL", "tagPrefix": prefix}

    def test_hidden_hosts_never_standalone_but_uri_outline_and_base64_include_them(self):
        self.host("Visible")
        self.host("Hidden", is_hidden=True)
        for target in ("v2ray-json", "clash", "sing-box"):
            with self.subTest(target=target):
                self.assertEqual(len(self.plan(target)[1]), 1)
        self.assertEqual(len(self.generate("v2ray").splitlines()), 2)
        self.assertEqual(len(self.plan("outline")[1]), 2)
        self.assertEqual(json.loads(self.generate("outline"))["tag"], "Hidden")
        snapshot, plans, _ = self.plan("v2ray")
        result = GeneratorRegistry().for_target("v2ray").generate(
            RenderInput("v2ray", plans, snapshot.defaults, as_base64=True))
        self.assertEqual(len(base64.b64decode(result.body).decode().splitlines()), 2)

    def test_xray_injection_preserves_id_order_deduplicates_and_strips_metadata(self):
        recipient, a, b = self.host("Recipient"), self.host("A", is_hidden=True), self.host("B", is_hidden=True)
        self.template(recipient, "v2ray-json", {
            "outbounds": [], "marzban": {"addVirtualHostAsOutbound": False,
                                         "injectHosts": [self.injection([b.id, a.id, b.id, recipient.id])]},
            "observatory": {"subjectSelector": ["pool"], "probeInterval": "30s"},
            "routing": {"balancers": [{"tag": "best", "selector": ["pool"], "strategy": {"type": "leastPing"}}],
                        "rules": [{"balancerTag": "best", "network": "tcp,udp"}]}})
        document = json.loads(self.generate())[0]
        self.assertEqual([node["tag"] for node in document["outbounds"]], ["pool", "pool-2"])
        self.assertEqual(document["outbounds"][0]["settings"]["servers"][0]["address"], "b.example.com")
        self.assertNotIn("marzban", document)
        self.assertEqual(document["observatory"]["probeInterval"], "30s")

    def test_injection_defaults_to_hidden_and_never_bypasses_bindings_or_permissions(self):
        recipient, hidden = self.host("Recipient"), self.host("Hidden", is_hidden=True)
        self.host("Visible")
        forbidden = self.host("DisabledFormat", subscription_template_ids={})
        self.template(recipient, "v2ray-json", {"outbounds": [], "marzban": {
            "injectHosts": [{"tagPrefix": "hidden"}]}})
        snapshot, plans, diagnostics = self.plan(root_ids={recipient.id})
        output = GeneratorRegistry().for_target("v2ray-json").generate(RenderInput("v2ray-json", plans, snapshot.defaults))
        self.assertEqual([item["tag"] for item in json.loads(output.body)[0]["outbounds"]], ["proxy", "hidden"])
        self.assertIn({"host_id": forbidden.id, "reason": "format_disabled"}, diagnostics)
        snapshot = replace(snapshot, inbounds={})
        self.assertEqual(ProfilePlanner().plan(snapshot, "v2ray-json", {}, {}, ResolveContext({}))[0], ())
        self.assertIn({"host_id": hidden.id, "reason": "selected"}, output.diagnostics)

    def test_xray_groups_are_flat_and_same_groups_uses_recipient_groups(self):
        group = HostGroup(id="eu", name="Europe")
        self.db.add(group)
        self.db.commit()
        recipient = self.host("Recipient", group_ids=["eu"])
        self.host("A", group_ids=["eu"], is_hidden=True)
        self.host("B", is_hidden=True)
        self.template(recipient, "v2ray-json", {"outbounds": [], "marzban": {"injectHosts": [
            {"tagPrefix": "eu", "selector": {"type": "sameGroupsAsRecipient"}}]}})
        document = json.loads(self.generate(root_ids={recipient.id}))[0]
        self.assertEqual([node["tag"] for node in document["outbounds"]], ["proxy", "eu"])

    def test_clash_includes_hidden_in_requested_group_and_not_default_group(self):
        recipient, hidden, unused = self.host("A"), self.host("B", is_hidden=True), self.host("C", is_hidden=True)
        self.template(recipient, "clash", {"proxies": [], "proxy-groups": [
            {"name": "Best", "type": "url-test", "proxies": [], "url": "https://example.com", "interval": 30,
             "marzban": {"include-proxies": True, "selectFrom": "ALL",
                         "selector": {"type": "ids", "values": [hidden.id, recipient.id]}}},
            {"name": "Default", "type": "select", "proxies": ["DIRECT"]},
            {"name": "Static", "type": "select", "proxies": ["DIRECT"],
             "marzban": {"include-proxies": False}}]})
        output = yaml.safe_load(self.generate("clash"))
        self.assertEqual([item["name"] for item in output["proxies"]], ["A", "B"])
        self.assertEqual(output["proxy-groups"][0]["proxies"], ["B", "A"])
        self.assertEqual(output["proxy-groups"][1]["proxies"], ["DIRECT", "A"])
        self.assertEqual(output["proxy-groups"][2]["proxies"], ["DIRECT"])
        self.assertNotIn("marzban", json.dumps(output))

    def test_clash_jinja_conf_does_not_duplicate_generated_nodes_and_inline_provider_is_isolated(self):
        recipient, hidden = self.host("A"), self.host("B", is_hidden=True)
        template = self.db.get(SubscriptionTemplate, recipient.subscription_template_ids["clash"])
        template.content = '{{ conf | yaml }}\nproxy-providers:\n  hidden:\n    type: inline\n    payload: []\n    marzban:\n      include-proxies: true\n      selectFrom: HIDDEN\n'
        self.db.commit()
        output = yaml.safe_load(self.generate("clash"))
        self.assertEqual([item["name"] for item in output["proxies"]], ["A"])
        self.assertEqual([item["name"] for item in output["proxy-providers"]["hidden"]["payload"]], ["B"])

    def test_singbox_native_parameters_zero_false_and_explicit_lists_survive(self):
        recipient, hidden = self.host("A"), self.host("B", is_hidden=True)
        self.template(recipient, "sing-box", {"outbounds": [
            {"type": "direct", "tag": "direct"},
            {"type": "urltest", "tag": "best", "outbounds": [], "tolerance": 0,
             "interrupt_exist_connections": False, "marzban": {"includeProxies": True, "selectFrom": "ALL"}},
            {"type": "selector", "tag": "choice", "outbounds": None},
            {"type": "selector", "tag": "manual", "outbounds": ["direct"]}], "route": {"final": "choice"}})
        output = json.loads(self.generate("sing-box"))
        nodes = {item["tag"]: item for item in output["outbounds"]}
        self.assertEqual(nodes["best"]["outbounds"], ["A", "B"])
        self.assertEqual(nodes["best"]["tolerance"], 0)
        self.assertFalse(nodes["best"]["interrupt_exist_connections"])
        self.assertEqual(nodes["choice"]["outbounds"], ["A", "best"])
        self.assertEqual(nodes["manual"]["outbounds"], ["direct"])
        self.assertNotIn("marzban", json.dumps(output))

    def test_aggregate_template_override_supports_all_hidden_without_creating_standalones(self):
        hidden = self.host("A", is_hidden=True)
        template = self.template(hidden, "sing-box", {"outbounds": [
            {"tag": "best", "type": "urltest", "outbounds": [],
             "marzban": {"includeProxies": True, "selectFrom": "ALL"}}]})
        self.assertEqual(self.generate("sing-box"), "")
        self.assertTrue(self.generate("sing-box", template_id=template.id))

    def test_missing_explicit_sources_skip_unusable_document(self):
        recipient = self.host("A")
        self.template(recipient, "v2ray-json", {"outbounds": [], "marzban": {
            "addVirtualHostAsOutbound": False, "injectHosts": [self.injection([9999])]}})
        self.assertEqual(self.generate(), "")

    def test_explicit_default_templates_do_not_fall_back_to_direct_with_only_hidden_sources(self):
        hidden = self.host("A", is_hidden=True)
        for target in ("clash", "sing-box"):
            with self.subTest(target=target):
                self.assertEqual(self.generate(target, template_id=hidden.subscription_template_ids[target]), "")

    def test_default_aggregate_selection_respects_the_root_filter(self):
        a = self.host("A")
        self.host("B")
        self.template(a, "clash", {"proxies": [], "proxy-groups": [
            {"name": "choice", "type": "select", "proxies": [], "marzban": {"include-proxies": True}}]})
        document = yaml.safe_load(self.generate("clash", root_ids={a.id}))
        self.assertEqual(document["proxy-groups"][0]["proxies"], ["A"])
        self.assertEqual([node["name"] for node in document["proxies"]], ["A"])

    def test_duplicate_tags_unknown_references_and_cycles_are_rejected(self):
        recipient = self.host("A")
        for outbounds in ([{"tag": "proxy", "protocol": "freedom"}],):
            self.template(recipient, "v2ray-json", {"outbounds": outbounds})
            with self.assertRaises(ValueError):
                self.generate()
        for outbounds in ([{"tag": "choice", "type": "selector", "outbounds": ["missing"]}],
                          [{"tag": "a", "type": "selector", "outbounds": ["b"]},
                           {"tag": "b", "type": "selector", "outbounds": ["a"]}]):
            self.template(recipient, "sing-box", {"outbounds": outbounds})
            with self.assertRaises(ValueError):
                self.generate("sing-box")

    def test_invalid_directives_are_rejected_at_save_time(self):
        for metadata in ({"injectHosts": [{"tagPrefix": "x", "selector": {"type": "ids", "values": [True]}}]},
                         {"unknown": True}, {"addVirtualHostAsOutbound": "true"}):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                validate_subscription_template(SubscriptionFormat.v2ray_json,
                                               json.dumps({"outbounds": [], "marzban": metadata}))
        with self.assertRaises(ValueError):
            HostCreate(inbound_id=1, remark="Old", address="old.example.com", linked_host_ids=[2])

    def test_hidden_bindings_do_not_conflict_with_visible_aggregate_template(self):
        recipient, hidden = self.host("A"), self.host("B", is_hidden=True)
        default = self.db.get(SubscriptionTemplate, hidden.subscription_template_ids["clash"])
        other = SubscriptionTemplate(name="Other", format="clash", content=default.content)
        self.db.add(other)
        self.db.commit()
        self.db.refresh(other)
        from app.db.crud import proxy_hosts

        proxy_hosts.update_host(self.db, hidden, HostPatch(subscription_template_ids={"clash": other.id}))
        self.assertTrue(self.generate("clash"))
        proxy_hosts.update_host(self.db, hidden, HostPatch(is_hidden=False))
        with self.assertRaises(TemplateConflict):
            self.generate("clash")

    def test_unused_hidden_mappers_do_not_break_other_profiles(self):
        self.host("A")
        self.host("B", is_hidden=True, overrides={"mapper": {
            "singbox": [{"op": "unset", "to": "tag"}], "clash": [{"op": "unset", "to": "name"}]}})
        self.assertTrue(self.generate("sing-box"))
        self.assertTrue(self.generate("clash"))

    def test_rendered_singbox_template_is_not_interpreted_as_jinja_again(self):
        host = self.host("A")
        template = self.db.get(SubscriptionTemplate, host.subscription_template_ids["sing-box"])
        template.content = '{"outbounds": [], "literal": {{ "{{ keep_literal }}" | tojson }}}'
        self.db.commit()
        self.assertEqual(json.loads(self.generate("sing-box"))["literal"], "{{ keep_literal }}")

    def test_mixed_protocol_sources_use_own_credentials_and_overrides(self):
        from app.db.models.proxies import ProxyInbound
        from app.db.crud import proxy_hosts

        recipient = self.host("Recipient")
        vmess = ProxyInbound(tag="VMess", content={"tag": "VMess", "protocol": "vmess", "port": 8443,
                                                   "settings": {"clients": []}, "streamSettings": {"network": "ws", "security": "none",
                                                                                                   "wsSettings": {"path": "/vmess"}}})
        self.db.add(vmess)
        self.db.commit()
        source = proxy_hosts.create_host(self.db, HostCreate(inbound_id=vmess.id, remark="VMess",
                                                             address="vmess.example.com", is_hidden=True, overrides={"transport": {"path": "/own"}}))
        self.template(recipient, "v2ray-json", {"outbounds": [],
                      "marzban": {"injectHosts": [self.injection([source.id])]}})
        self.template(recipient, "clash", {"proxies": [], "proxy-groups": [
            {"name": "Best", "type": "url-test", "proxies": [], "url": "https://example.com", "interval": 30,
             "marzban": {"include-proxies": True, "selectFrom": "ALL",
                         "selector": {"type": "ids", "values": [source.id]}}}]})
        self.template(recipient, "sing-box", {"outbounds": [
            {"tag": "Best", "type": "urltest", "outbounds": [], "url": "https://example.com", "interval": "30s",
             "marzban": {"includeProxies": True, "selectFrom": "ALL",
                         "selector": {"type": "ids", "values": [source.id]}}}]})
        for target in ("v2ray-json", "v2ray", "clash", "sing-box", "outline"):
            with self.subTest(target=target):
                snapshot, _, _ = self.plan(target)
                plans, _ = ProfilePlanner().plan(snapshot, target, {
                    "shadowsocks": {"password": "own-ss-password", "method": "aes-256-gcm"},
                    "vmess": {"id": "11111111-1111-4111-8111-111111111111"}},
                    {"shadowsocks": ["SS"], "vmess": ["VMess"]}, ResolveContext({}))
                result = GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults))
                self.assertTrue(result.body)
                if target == "v2ray-json":
                    node = next(node for node in json.loads(result.body)[0]["outbounds"] if node["tag"] == "pool")
                    self.assertEqual(node["protocol"], "vmess")
                    self.assertEqual(node["settings"]["vnext"][0]["users"][0]
                                     ["id"], "11111111-1111-4111-8111-111111111111")
                    self.assertEqual(node["streamSettings"]["wsSettings"]["path"], "/own")
                elif target == "clash":
                    node = next(node for node in yaml.safe_load(result.body)["proxies"] if node["type"] == "vmess")
                    self.assertEqual(node["uuid"], "11111111-1111-4111-8111-111111111111")
                    self.assertEqual(node["ws-opts"]["path"], "/own")
                elif target == "sing-box":
                    node = next(node for node in json.loads(result.body)["outbounds"] if node["type"] == "vmess")
                    self.assertEqual(node["uuid"], "11111111-1111-4111-8111-111111111111")
                    self.assertEqual(node["transport"]["path"], "/own")
                elif target == "v2ray":
                    link = next(link for link in result.body.splitlines() if link.startswith("vmess://"))
                    self.assertEqual(json.loads(base64.b64decode(link[8:]))["id"],
                                     "11111111-1111-4111-8111-111111111111")
                else:
                    self.assertEqual(json.loads(result.body)["password"], "own-ss-password")

    def test_template_preview_is_sudo_only_read_only_and_matches_all_renderers(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.db import get_db
        from app.db.models.proxies import Proxy
        from app.db.models.users import User
        from app.models.admin import Admin
        from app.models.proxy import ProxyTypes
        from app.routers.subscription_templates import router
        from unittest.mock import patch

        self.host("A")
        user = User(username="preview", proxies=[Proxy(type=ProxyTypes.Shadowsocks,
                    settings={"password": "preview-password", "method": "aes-256-gcm"})])
        self.db.add(user)
        self.db.commit()
        application = FastAPI()
        application.include_router(router)
        application.dependency_overrides[get_db] = lambda: self.db
        with TestClient(application) as client:
            self.assertEqual(client.post("/api/subscription-templates/preview", json={}).status_code, 401)
            self.assertEqual(client.get("/api/subscription-templates/preview-users").status_code, 401)
            application.dependency_overrides[Admin.check_sudo_admin] = lambda: object()
            self.assertEqual(client.get("/api/subscription-templates/preview-users").json(),
                             [{"id": user.id, "username": "preview"}])
            for target in ("v2ray", "v2ray-json", "clash", "sing-box", "outline"):
                with self.subTest(target=target), patch("app.utils.runtime_settings.get_runtime_settings",
                                                        return_value=self.settings):
                    template = next(row for row in self.db.query(SubscriptionTemplate) if row.format == target)
                    response = client.post("/api/subscription-templates/preview", json={"format": target,
                                                                                        "content": template.content, "user_id": user.id})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertTrue(response.json()["body"])
            self.assertEqual(client.post("/api/subscription-templates/preview", json={"format": "v2ray-json",
                                                                                      "content": '{"outbounds": []}', "user_id": 99999}).status_code, 404)
        self.assertEqual(self.db.query(SubscriptionTemplate).count(), 5)
