import json
from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.db.base import Base
from app.db.crud import proxy_hosts as crud
from app.db.crud.subscription_templates import seed_defaults
from app.db.models.proxies import ProxyInbound
from app.models.admin import Admin
from app.models.host import HostCreate, HostPatch, HostResponse
from app.routers.hosts import router
from app.subscription.contracts import RenderInput
from app.subscription.generators import GeneratorRegistry
from app.subscription.loader import SubscriptionSnapshotLoader
from app.subscription.planning import ProfilePlanner
from app.subscription.resolver import ResolveContext
from app.utils.runtime_settings import build_default_runtime_settings


class UnifiedHostTests(TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        event.listen(self.engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.inbound = ProxyInbound(tag="SS", content={"tag": "SS", "protocol": "shadowsocks", "port": 443,
                                                       "settings": {"method": "aes-256-gcm", "clients": []},
                                                       "streamSettings": {"network": "tcp", "security": "none"}})
        self.db.add(self.inbound)
        seed_defaults(self.db)
        self.db.commit()
        self.settings = build_default_runtime_settings()
        self.settings.external_config = ""

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def host(self, name, **options):
        return crud.create_host(self.db, HostCreate(inbound_id=self.inbound.id, remark=name,
                                                    address=name.lower() + ".example.com", **options))

    def plan(self, target="v2ray-json", **options):
        snapshot = SubscriptionSnapshotLoader().load(self.db, self.settings)
        plans, diagnostics = ProfilePlanner().plan(snapshot, target,
                                                   {"shadowsocks": {"password": "test-password", "method": "aes-256-gcm"}},
                                                   {"shadowsocks": ["SS"]}, ResolveContext({"USERNAME": "test"}), **options)
        return snapshot, plans, diagnostics

    def generate(self, target="v2ray-json", **options):
        snapshot, plans, _ = self.plan(target, **options)
        return GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults)).body

    def test_direct_links_never_expand_nested_members(self):
        a, b, c = self.host("A"), self.host("B"), self.host("C")
        crud.update_host(self.db, b, HostPatch(linked_host_ids=[c.id]))
        crud.update_host(self.db, a, HostPatch(linked_host_ids=[b.id]))
        _, plans, _ = self.plan()
        compositions = {plan.owner.id: [item.host_id for item in plan.connections] for plan in plans if plan.automatic}
        self.assertEqual(compositions, {a.id: [a.id, b.id], b.id: [b.id, c.id]})

    def test_visibility_is_conditional_and_uri_keeps_individual_hosts(self):
        a, b = self.host("A", show_when_composed=False), self.host("B", show_when_composed=False)
        crud.update_host(self.db, a, HostPatch(linked_host_ids=[b.id]))
        _, plans, _ = self.plan()
        self.assertEqual([(plan.owner.id, plan.automatic) for plan in plans], [(a.id, True)])
        self.assertEqual(len(self.generate("v2ray").splitlines()), 2)
        crud.update_host(self.db, a, HostPatch(enabled=False))
        _, plans, _ = self.plan()
        self.assertEqual([(plan.owner.id, plan.automatic) for plan in plans], [(b.id, False)])

    def test_owner_and_member_visibility_are_independent(self):
        a, b = self.host("A"), self.host("B")
        crud.update_host(self.db, a, HostPatch(linked_host_ids=[b.id]))
        for owner_visible in (True, False):
            for member_visible in (True, False):
                with self.subTest(owner=owner_visible, member=member_visible):
                    crud.update_host(self.db, a, HostPatch(show_when_composed=owner_visible))
                    crud.update_host(self.db, b, HostPatch(show_when_composed=member_visible))
                    standalone = [plan.owner.id for plan in self.plan()[1] if not plan.automatic]
                    self.assertEqual(standalone, ([a.id] if owner_visible else []) + ([b.id] if member_visible else []))

    def test_mapper_copies_raw_inbound_and_creates_arrays_without_mutating_inputs(self):
        from app.subscription.mapper import HostMapper

        self.host("A")
        connection = self.plan()[1][0].connections[0]
        node = {"keep": True}
        result = HostMapper().apply(node, [
            {"op": "copy", "from": "settings.method", "to": "options[0].cipher"},
            {"op": "set", "to": "options[0].enabled", "value": False},
            {"op": "copy", "from": "$host.port", "to": "port"},
        ], connection)
        self.assertEqual(result["options"], [{"cipher": "aes-256-gcm", "enabled": False}])
        self.assertEqual(result["port"], 443)
        self.assertEqual(node, {"keep": True})

    def test_inbound_update_revalidates_existing_extra_before_mutation(self):
        from app.db.crud.proxy_inbounds import update_inbound
        from app.models.proxy import InboundModify

        raw = {"tag": "SS", "protocol": "vless", "port": 443, "settings": {"clients": []},
               "streamSettings": {"network": "xhttp", "xhttpSettings": {"mode": "packet-up"}}}
        self.inbound.content = raw
        self.db.commit()
        self.host("A", overrides={"transport": {"xhttp": {"extra": {"uplinkHTTPMethod": "GET"}}}})
        incompatible = {**raw, "streamSettings": {"network": "xhttp", "xhttpSettings": {"mode": "stream-up"}}}
        with self.assertRaises(ValueError):
            update_inbound(self.db, self.inbound, InboundModify(content=incompatible))
        self.assertEqual(self.inbound.content, raw)

    def test_cycles_are_two_independent_flat_profiles(self):
        a, b = self.host("A"), self.host("B")
        crud.update_host(self.db, a, HostPatch(linked_host_ids=[b.id]))
        crud.update_host(self.db, b, HostPatch(linked_host_ids=[a.id]))
        self.assertEqual(sum(plan.automatic for plan in self.plan()[1]), 2)

    def test_dependency_does_not_become_an_unselected_root(self):
        a, b = self.host("A"), self.host("B")
        crud.update_host(self.db, a, HostPatch(linked_host_ids=[b.id]))
        _, plans, _ = self.plan(root_ids={a.id})
        self.assertEqual([(plan.owner.id, plan.automatic) for plan in plans], [(a.id, False), (a.id, True)])
        self.assertEqual([item.host_id for item in plans[1].connections], [a.id, b.id])

    def test_disabled_format_is_not_reintroduced_by_composition(self):
        a, b = self.host("A"), self.host("B", subscription_template_ids={})
        crud.update_host(self.db, a, HostPatch(linked_host_ids=[b.id]))
        _, plans, diagnostics = self.plan()
        self.assertEqual([item.host_id for item in plans[1].connections], [a.id])
        self.assertIn({"host_id": b.id, "reason": "format_disabled"}, diagnostics)

    def test_reordering_and_cloning_preserve_outgoing_links_only(self):
        a, b, c = self.host("A"), self.host("B"), self.host("C")
        crud.update_host(self.db, a, HostPatch(linked_host_ids=[b.id, c.id]))
        crud.update_host(self.db, a, HostPatch(linked_host_ids=[c.id, b.id]))
        cloned = crud.clone_host(self.db, a, "Copy")
        self.assertEqual(cloned.linked_host_ids, [c.id, b.id])
        self.assertFalse(cloned.enabled)
        self.assertEqual(cloned.member_of, [])
        crud.remove_host(self.db, b)
        self.db.expire_all()
        self.assertEqual(crud.get_host(self.db, a.id).linked_host_ids, [c.id])

    def test_invalid_links_are_rejected_before_any_mutation(self):
        a = self.host("A")
        for ids in ([a.id], [9999], [a.id, a.id]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                crud.update_host(self.db, a, HostPatch(remark="Wrong", linked_host_ids=ids))
            self.assertEqual(a.remark, "A")
            self.assertEqual(a.linked_host_ids, [])

    def test_explicit_client_strategy_required_and_preserved(self):
        a = self.host("A")
        with self.assertRaises(ValueError):
            crud.update_host(self.db, a, HostPatch(balancer_settings={"strategy": "round_robin"}))
        crud.update_host(self.db, a, HostPatch(balancer_settings={
            "strategy": "round_robin", "clients": {"sing-box": {"strategy": "least_ping", "tolerance": 0,
                                                                "interrupt_existing_connections": False}}}))
        document = json.loads(self.generate("sing-box"))
        automatic = next(item for item in document["outbounds"] if item.get("tag") == "A · Auto")
        self.assertEqual(automatic["tolerance"], 0)
        self.assertFalse(automatic["interrupt_exist_connections"])
        xray = json.loads(self.generate())[-1]
        self.assertEqual(xray["routing"]["balancers"][0]["strategy"]["type"], "roundRobin")

    def test_renderers_use_detached_snapshot_without_database_access(self):
        self.host("A")
        for target in ("v2ray", "v2ray-json", "clash-meta", "sing-box", "outline"):
            with self.subTest(target=target):
                snapshot, plans, _ = self.plan(target)
                with patch("app.db.GetDB", side_effect=AssertionError("Renderer accessed DB")):
                    result = GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults))
                self.assertTrue(result.body)

    def test_identity_mapper_cannot_produce_broken_references(self):
        a = self.host("A", overrides={"mapper": {"singbox": [{"op": "unset", "to": "tag"}]}})
        with self.assertRaises(ValueError):
            self.generate("sing-box")

    def test_sparse_patch_preserves_false_and_clears_only_the_requested_key(self):
        a = self.host("A", overrides={"security": {"allow_insecure": False, "sni": "front.example.com"}})
        crud.update_host(self.db, a, HostPatch(overrides={"security": {"sni": None}}))
        self.assertEqual(a.overrides, {"security": {"allow_insecure": False}})
        crud.update_host(self.db, a, HostPatch(overrides=None))
        self.assertEqual(a.overrides, {})

    def test_api_authentication_pagination_patch_and_clone(self):
        application = FastAPI()
        application.include_router(router)
        application.dependency_overrides[get_db] = lambda: self.db
        client = TestClient(application)
        self.assertEqual(client.get("/api/hosts").status_code, 401)
        application.dependency_overrides[Admin.check_sudo_admin] = lambda: SimpleNamespace(username="test")
        response = client.post("/api/hosts", json={"inbound_id": self.inbound.id,
                               "remark": "A", "address": "a.example.com"})
        self.assertEqual(response.status_code, 201, response.text)
        row = response.json()
        self.assertTrue(row["show_when_composed"])
        self.assertEqual(client.get("/api/hosts", params={"limit": 1}).json()["total"], 1)
        response = client.patch(f"/api/hosts/{row['id']}", json={"enabled": False})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["enabled"])
        cloned = client.post(f"/api/hosts/{row['id']}/clone", json={"remark": "Copy"})
        self.assertEqual(cloned.status_code, 201, cloned.text)
        self.assertEqual(client.delete(f"/api/hosts/{row['id']}").status_code, 204)
        self.assertEqual(client.get(f"/api/hosts/{row['id']}").status_code, 404)
        self.assertEqual(client.get("/api/hosts/capabilities").json()["schema_version"], 2)
        client.close()

    def test_scalar_xhttp_fields_and_explicit_nulls_are_not_accepted(self):
        for extra in ({"uplinkHTTPMethod": None}, {"xPaddingObfsMode": None}, {"scMaxBufferedPosts": False},
                      {"uplinkHTTPMethod": "bad method"}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                HostCreate(inbound_id=1, remark="A", address="example.com",
                           overrides={"transport": {"xhttp": {"extra": extra}}})
        with self.assertRaises(ValidationError):
            HostCreate(inbound_id=1, remark="A", address="example.com", overrides={
                       "transport": {"xhttp": {"uplink_http_method": "PUT"}}})

    def test_clone_remaps_owner_cost_without_changing_source(self):
        a = self.host("A")
        crud.update_host(self.db, a, HostPatch(balancer_settings={"clients": {"v2ray-json": {
            "strategy": "least_load", "strategy_settings": {"costs": [{"host_id": a.id, "value": 2}]}}}}))
        cloned = crud.clone_host(self.db, a, "Copy")
        self.assertEqual(cloned.balancer_settings["clients"]["v2ray-json"]["strategy_settings"]["costs"],
                         [{"host_id": cloned.id, "value": 2}])
        self.assertEqual(a.balancer_settings["clients"]["v2ray-json"]["strategy_settings"]["costs"][0]["host_id"], a.id)

    def test_xhttp_extra_is_atomic_and_preserves_zero_false_and_inheritance(self):
        from urllib.parse import parse_qs, urlsplit

        self.inbound.content = {"tag": "SS", "protocol": "vless", "port": 443, "settings": {"clients": []},
                                "streamSettings": {"network": "xhttp", "security": "none", "xhttpSettings": {
                                    "mode": "packet-up", "extra": {"xPaddingBytes": "100-200", "noGRPCHeader": True}}}}
        self.db.commit()
        a = self.host("A", overrides={"transport": {"xhttp": {"extra": {
            "scMaxBufferedPosts": 0, "xPaddingObfsMode": False, "uplinkHTTPMethod": " put "}}}})
        credentials = {"vless": {"id": "d2719ec9-8f2d-4b70-91ad-621c6b10a13a"}}

        def render(target):
            snapshot = SubscriptionSnapshotLoader().load(self.db, self.settings)
            plans, _ = ProfilePlanner().plan(snapshot, target, credentials, {"vless": ["SS"]}, ResolveContext({}))
            return GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults)).body
        document = json.loads(render("v2ray-json"))[0]
        extra = document["outbounds"][0]["streamSettings"]["xhttpSettings"]["extra"]
        self.assertEqual(extra, {"scMaxBufferedPosts": 0, "xPaddingObfsMode": False, "uplinkHTTPMethod": "PUT"})
        uri_extra = json.loads(parse_qs(urlsplit(render("v2ray")).query)["extra"][0])
        self.assertEqual(uri_extra, extra)
        crud.update_host(self.db, a, HostPatch(overrides={"transport": {"xhttp": {"extra": {}}}}))
        empty = json.loads(render("v2ray-json"))[0]["outbounds"][0]["streamSettings"]["xhttpSettings"]
        self.assertFalse(empty.get("extra"))
        crud.update_host(self.db, a, HostPatch(overrides={"transport": {"xhttp": {"extra": None}}}))
        inherited = json.loads(render("v2ray-json"))[0]["outbounds"][0]["streamSettings"]["xhttpSettings"]["extra"]
        self.assertEqual(inherited["xPaddingBytes"], "100-200")

    def test_mixed_protocol_members_keep_their_own_inbounds_and_credentials(self):
        vmess = ProxyInbound(tag="VMess", content={"tag": "VMess", "protocol": "vmess", "port": 8443,
                                                   "settings": {"clients": []}, "streamSettings": {"network": "ws", "security": "none", "wsSettings": {"path": "/vmess"}}})
        self.db.add(vmess)
        self.db.commit()
        a = self.host("A")
        b = crud.create_host(self.db, HostCreate(inbound_id=vmess.id, remark="B", address="b.example.com"))
        crud.update_host(self.db, a, HostPatch(linked_host_ids=[b.id]))
        snapshot = SubscriptionSnapshotLoader().load(self.db, self.settings)
        plans, _ = ProfilePlanner().plan(snapshot, "v2ray-json", {
            "shadowsocks": {"password": "secret", "method": "aes-256-gcm"},
            "vmess": {"id": "d2719ec9-8f2d-4b70-91ad-621c6b10a13a"}},
            {"shadowsocks": ["SS"], "vmess": ["VMess"]}, ResolveContext({}))
        profile = next(plan for plan in plans if plan.automatic)
        self.assertEqual([item.port for item in profile.connections], [443, 8443])
        rendered = GeneratorRegistry().for_target("v2ray-json").generate(RenderInput("v2ray-json", (profile,), snapshot.defaults))
        outbounds = json.loads(rendered.body)[0]["outbounds"]
        self.assertEqual([item["protocol"] for item in outbounds[:2]], ["shadowsocks", "vmess"])
        self.assertEqual(outbounds[1]["streamSettings"]["wsSettings"]["path"], "/vmess")

    def test_empty_paths_headers_and_tls_false_survive_format_defaults(self):
        import yaml

        self.inbound.content = {"tag": "SS", "protocol": "vmess", "port": 443, "settings": {"clients": []},
                                "streamSettings": {"network": "ws", "security": "tls", "tlsSettings": {"serverName": "front.example.com"},
                                                   "wsSettings": {"path": "/original", "headers": {"Host": "front.example.com", "X-Test": "kept"}}}}
        self.db.commit()
        self.host("A", overrides={"transport": {"path": "", "host": ""},
                                  "security": {"alpn": [], "allow_insecure": False}})
        snapshot = SubscriptionSnapshotLoader().load(self.db, self.settings)
        for target in ("v2ray-json", "clash-meta", "sing-box"):
            with self.subTest(target=target):
                plans, _ = ProfilePlanner().plan(snapshot, target,
                                                 {"vmess": {"id": "d2719ec9-8f2d-4b70-91ad-621c6b10a13a"}}, {"vmess": ["SS"]}, ResolveContext({}))
                body = GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults)).body
                if target == "v2ray-json":
                    node = json.loads(body)[0]["outbounds"][0]
                    transport, tls = node["streamSettings"]["wsSettings"], node["streamSettings"]["tlsSettings"]
                    self.assertFalse(tls["allowInsecure"])
                elif target == "clash-meta":
                    node = yaml.safe_load(body)["proxies"][0]
                    transport, tls = node["ws-opts"], node
                    self.assertFalse(tls["skip-cert-verify"])
                else:
                    node = next(item for item in json.loads(body)["outbounds"] if item["tag"] == "A")
                    transport, tls = node["transport"], node["tls"]
                    self.assertFalse(tls["insecure"])
                self.assertEqual(transport["path"], "")
                self.assertEqual(transport["headers"]["X-Test"], "kept")
                self.assertEqual(tls["alpn"], [])

    def test_clash_meta_is_the_only_yaml_target_and_accepts_client_overrides(self):
        from app.models.subscription_template import normalize_subscription_client_type
        from app.subscription.capabilities import host_capabilities
        import yaml

        self.host("A", overrides={"clients": {"clash-meta": {"ip_version": "ipv4"}},
                                  "mapper": {"clash-meta": [{"op": "set", "to": "udp", "value": False}]}})
        self.assertEqual(set(GeneratorRegistry.generators), {"v2ray", "v2ray-json", "clash-meta", "sing-box", "outline"})
        self.assertEqual(set(host_capabilities()["strategies"]), {"v2ray-json", "clash-meta", "sing-box"})
        for alias in ("clash", "mihomo", "clash-meta"):
            self.assertEqual(normalize_subscription_client_type(alias), "clash-meta")
        node = yaml.safe_load(self.generate("clash-meta"))["proxies"][0]
        self.assertEqual(node["ip-version"], "ipv4")
        self.assertFalse(node["udp"])
