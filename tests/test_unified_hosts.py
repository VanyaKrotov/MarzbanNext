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

    def test_renderers_use_detached_snapshot_without_database_access(self):
        self.host("A")
        for target in ("v2ray", "v2ray-json", "clash", "sing-box", "outline"):
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
        self.assertFalse(row["is_hidden"])
        self.assertIsNone(row["port"])
        self.assertEqual(row["inbound_port"], 443)
        self.assertEqual(client.get("/api/hosts", params={"limit": 1}).json()["total"], 1)
        response = client.patch(f"/api/hosts/{row['id']}", json={"port": 8443})
        self.assertEqual(response.json()["port"], 8443)
        self.assertEqual(response.json()["inbound_port"], 443)
        self.inbound.content = {**self.inbound.content, "port": 9443}
        self.db.commit()
        response = client.patch(f"/api/hosts/{row['id']}", json={"port": None})
        self.assertIsNone(response.json()["port"])
        self.assertEqual(response.json()["inbound_port"], 9443)
        self.assertEqual(client.get("/api/hosts").json()["items"][0]["inbound_port"], 9443)
        response = client.patch(f"/api/hosts/{row['id']}", json={"enabled": False})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["enabled"])
        cloned = client.post(f"/api/hosts/{row['id']}/clone", json={"remark": "Copy"})
        self.assertEqual(cloned.status_code, 201, cloned.text)
        self.assertEqual(client.delete(f"/api/hosts/{row['id']}").status_code, 204)
        self.assertEqual(client.get(f"/api/hosts/{row['id']}").status_code, 404)
        self.assertEqual(client.get("/api/hosts/capabilities").json()["schema_version"], 4)
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

    def test_empty_paths_headers_and_tls_false_survive_format_defaults(self):
        import yaml

        self.inbound.content = {"tag": "SS", "protocol": "vmess", "port": 443, "settings": {"clients": []},
                                "streamSettings": {"network": "ws", "security": "tls", "tlsSettings": {"serverName": "front.example.com"},
                                                   "wsSettings": {"path": "/original", "headers": {"Host": "front.example.com", "X-Test": "kept"}}}}
        self.db.commit()
        self.host("A", overrides={"transport": {"path": "", "host": ""},
                                  "security": {"alpn": [], "allow_insecure": False}})
        snapshot = SubscriptionSnapshotLoader().load(self.db, self.settings)
        for target in ("v2ray-json", "clash", "sing-box"):
            with self.subTest(target=target):
                plans, _ = ProfilePlanner().plan(snapshot, target,
                                                 {"vmess": {"id": "d2719ec9-8f2d-4b70-91ad-621c6b10a13a"}}, {"vmess": ["SS"]}, ResolveContext({}))
                body = GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults)).body
                if target == "v2ray-json":
                    node = json.loads(body)[0]["outbounds"][0]
                    transport, tls = node["streamSettings"]["wsSettings"], node["streamSettings"]["tlsSettings"]
                    self.assertFalse(tls["allowInsecure"])
                elif target == "clash":
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

    def test_clash_is_the_only_yaml_target_and_accepts_client_overrides(self):
        from app.models.subscription_template import normalize_subscription_client_type
        from app.subscription.capabilities import host_capabilities
        import yaml

        self.host("A", overrides={"clients": {"clash": {"ip_version": "ipv4"}},
                                  "mapper": {"clash": [{"op": "set", "to": "udp", "value": False}]}})
        self.assertEqual(set(GeneratorRegistry.generators), {"v2ray", "v2ray-json", "clash", "sing-box", "outline"})
        self.assertNotIn("strategies", host_capabilities())
        self.assertEqual(normalize_subscription_client_type("clash"), "clash")
        for alias in ("clash-meta", "mihomo"):
            with self.subTest(alias=alias), self.assertRaises(ValueError):
                normalize_subscription_client_type(alias)
            with self.assertRaises(ValidationError):
                HostCreate(inbound_id=self.inbound.id, remark="Invalid", address="example.com",
                           overrides={"clients": {alias: {"ip_version": "ipv4"}}})
        node = yaml.safe_load(self.generate("clash"))["proxies"][0]
        self.assertEqual(node["ip-version"], "ipv4")
        self.assertFalse(node["udp"])
