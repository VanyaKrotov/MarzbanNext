"""XHTTP settings survive persistence and reach each compatible subscription representation."""

import base64
from copy import deepcopy
import json
from unittest import TestCase
from urllib.parse import parse_qs, urlsplit

import yaml

from app.db.crud import proxy_hosts
from app.models.host import HostPatch, HostResponse
from app.subscription.contracts import RenderInput
from app.subscription.generators import GeneratorRegistry
from app.subscription.generators.xhttp import clash_download
from app.subscription.loader import SubscriptionSnapshotLoader
from app.subscription.planning import ProfilePlanner
from app.subscription.resolver import ResolveContext

import test_client_config_generation as configurations
import test_unified_hosts as fixtures
from test_xhttp_schema import DOWNLOAD, EXTRA
from test_xhttp_hosts import make_xhttp_inbound


class XhttpGenerationTests(TestCase):
    setUp = fixtures.UnifiedHostTests.setUp
    tearDown = fixtures.UnifiedHostTests.tearDown
    host = fixtures.UnifiedHostTests.host
    render = configurations.ClientConfigurationTests.render

    def test_clash_download_does_not_inherit_uplink_security_or_ignored_legacy_settings(self):
        download = deepcopy(DOWNLOAD)
        download["realitySettings"] = {"serverName": "unused.example.com", "publicKey": "unused"}
        result = clash_download(download)
        self.assertEqual(result["servername"], "download.example.com")
        self.assertEqual(result["reality-opts"], {})
        self.assertFalse(result["skip-cert-verify"])
        self.assertEqual(result["ech-opts"], {})
        self.assertEqual(result["certificate"], "")
        download.update(xhttpSettings={}, splithttpSettings={"path": "/ignored"})
        self.assertEqual(clash_download(download)["path"], "")
        download["security"] = "reality"
        reality = clash_download(download)
        self.assertEqual(reality["reality-opts"]["public-key"], "unused")
        self.assertEqual(reality["alpn"], [])
        self.assertEqual(reality["servername"], "unused.example.com")

    def configure(self, protocol="vless", extra=None):
        raw = make_xhttp_inbound(protocol)
        raw["tag"] = self.inbound.tag
        raw["streamSettings"]["xhttpSettings"] = {"mode": "packet-up", "path": "/upload", **(extra or {})}
        self.inbound.content = raw
        self.db.commit()

    def test_extra_round_trip_clone_edit_replace_and_inherit_preserve_saved_values(self):
        self.configure()
        value = {"transport": {"xhttp": {"extra": deepcopy(EXTRA)}}}
        host = self.host("Saved", overrides=value)
        for row in (host, proxy_hosts.clone_host(self.db, host, "Copy")):
            self.assertEqual(HostResponse.model_validate(row).overrides, value)
        proxy_hosts.update_host(self.db, host, HostPatch(remark="Renamed"))
        self.assertEqual(host.overrides, value)
        changed = {"xmux": {"maxConnections": "2-4"}, "noGRPCHeader": False, "scMaxBufferedPosts": 0}
        proxy_hosts.update_host(self.db, host, HostPatch(overrides={"transport": {"xhttp": {"extra": changed}}}))
        self.assertEqual(host.overrides["transport"]["xhttp"]["extra"], changed)
        proxy_hosts.update_host(self.db, host, HostPatch(overrides={"transport": {"xhttp": {"extra": {}}}}))
        self.assertEqual(host.overrides["transport"]["xhttp"]["extra"], {})
        proxy_hosts.update_host(self.db, host, HostPatch(overrides={"transport": {"xhttp": {"extra": None}}}))
        self.assertNotIn("extra", host.overrides["transport"]["xhttp"])

    def test_native_and_atomic_inbound_extra_are_inherited_without_inventing_defaults(self):
        for index, native in enumerate((EXTRA, {"extra": EXTRA}, {"extra": {}, "uplinkHTTPMethod": "GET"})):
            with self.subTest(native=native):
                self.configure(extra=native)
                host = self.host(f"Inherited{index}")
                snapshot = SubscriptionSnapshotLoader().load(self.db, self.settings)
                plans, _ = ProfilePlanner().plan(snapshot, "v2ray-json", configurations.CREDENTIALS,
                                                 {"vless": [self.inbound.tag]}, ResolveContext({}), root_ids={host.id})
                expected = native.get("extra", native)
                self.assertEqual(plans[0].connections[0].inbound["_xhttp_extra"], expected)
                before = deepcopy(self.inbound.content)
                self.render("v2ray-json", root_ids={host.id})
                self.assertEqual(self.inbound.content, before)

    def test_extended_extra_reaches_xray_uri_vmess_base64_and_clash_without_loss(self):
        for protocol in ("vless", "vmess", "trojan"):
            with self.subTest(protocol=protocol):
                self.configure(protocol)
                host = self.host(protocol, overrides={"transport": {"xhttp": {"extra": EXTRA}}})
                roots = {host.id}
                document = json.loads(self.render("v2ray-json", root_ids=roots))[0]
                stream = document["outbounds"][0]["streamSettings"]
                settings = stream.get("xhttpSettings") or stream["splithttpSettings"]
                self.assertEqual(settings["extra"], EXTRA)
                link = self.render("v2ray", root_ids=roots)
                if protocol == "vmess":
                    encoded = json.loads(base64.b64decode(link.removeprefix("vmess://")))
                    self.assertEqual(encoded["extra"], EXTRA)
                else:
                    self.assertEqual(json.loads(parse_qs(urlsplit(link).query)["extra"][0]), EXTRA)
                snapshot = SubscriptionSnapshotLoader().load(self.db, self.settings)
                plans, _ = ProfilePlanner().plan(snapshot, "v2ray", configurations.CREDENTIALS,
                                                 {protocol: [self.inbound.tag]}, ResolveContext({}), root_ids=roots)
                encoded = GeneratorRegistry().for_target("v2ray").generate(
                    RenderInput("v2ray", plans, snapshot.defaults, as_base64=True))
                self.assertEqual(base64.b64decode(encoded.body).decode(), link)
                options = yaml.safe_load(self.render("clash", root_ids=roots))["proxies"][0]["xhttp-opts"]
                self.assertEqual(options["uplink-http-method"], "PUT")
                self.assertEqual(options["session-placement"], "header")
                self.assertEqual(options["session-table"], "Base62")
                self.assertEqual(options["session-length"], "16-24")
                self.assertEqual(options["reuse-settings"]["max-connections"], "4-2")
                self.assertEqual(options["reuse-settings"]["h-keep-alive-period"], -1)
                self.assertFalse(options["x-padding-obfs-mode"])
                self.assertEqual(options["download-settings"]["server"], DOWNLOAD["address"])
                self.assertEqual(options["download-settings"]["path"], "/down")
                self.assertEqual(options["download-settings"]["reuse-settings"]["max-connections"], "4-2")
                self.assertTrue(options["download-settings"]["tls"])
                self.assertEqual(options["download-settings"]["alpn"], ["h2"])
                self.assertEqual(self.render("sing-box", root_ids=roots), "")
                self.assertEqual(self.render("outline", root_ids=roots), "")

    def test_host_and_inbound_changes_recheck_mode_dependent_constraints(self):
        self.configure()
        for extra in ({"uplinkHTTPMethod": "GET"}, {"uplinkDataPlacement": "header"},
                      {"uplinkDataPlacement": "cookie"}, {"downloadSettings": DOWNLOAD}):
            host = self.host(f"Host{len(self.db.identity_map)}", overrides={"transport": {"xhttp": {"extra": extra}}})
            invalid = deepcopy(self.inbound.content)
            invalid["streamSettings"]["xhttpSettings"]["mode"] = "stream-one"
            from app.db.models.proxies import ProxyInbound

            with self.subTest(extra=extra), self.assertRaises(ValueError):
                proxy_hosts.validate_connection_options(ProxyInbound(content=invalid), host.overrides)
        self.configure(extra={"mode": "stream-up"})
        with self.assertRaises(ValueError):
            self.host("BadGET", overrides={"transport": {"xhttp": {"extra": {"uplinkHTTPMethod": "GET"}}}})
