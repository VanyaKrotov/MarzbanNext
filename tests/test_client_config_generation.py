"""End-to-end subscription generation from detached snapshots, without client processes."""

import base64
from copy import deepcopy
import json
from pathlib import Path
import re
from unittest import TestCase
from urllib.parse import parse_qs, urlsplit

import yaml

from app.db.models.subscription_templates import SubscriptionTemplate
from app.db.models.proxies import ProxyInbound
from app.subscription.contracts import RenderInput, SubscriptionError
from app.subscription.generators import GeneratorRegistry
from app.subscription.loader import SubscriptionSnapshotLoader
from app.subscription.planning import ProfilePlanner
from app.subscription.resolver import ResolveContext
from app.subscription.validation import OutputValidator

import test_unified_hosts as fixtures


ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"
CREDENTIALS = {
    "vless": {"id": ACCOUNT_ID, "flow": ""},
    "vmess": {"id": ACCOUNT_ID},
    "trojan": {"password": "test-password"},
    "shadowsocks": {"password": "test-password", "method": "aes-256-gcm"},
    "hysteria": {"auth": "test-password"},
}


class ClientConfigurationTests(TestCase):
    setUp = fixtures.UnifiedHostTests.setUp
    tearDown = fixtures.UnifiedHostTests.tearDown
    host = fixtures.UnifiedHostTests.host

    def render(self, target, **options):
        snapshot = SubscriptionSnapshotLoader().load(self.db, self.settings)
        before = deepcopy(snapshot)
        allowed = {}
        for inbound in snapshot.inbounds.values():
            allowed.setdefault(inbound["protocol"], []).append(inbound["tag"])
        plans, _ = ProfilePlanner().plan(snapshot, target, CREDENTIALS, allowed, ResolveContext({}), **options)
        result = GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults))
        self.assertEqual(snapshot, before, "Generation must not mutate its source snapshot")
        return result.body

    def assign(self, host, target, document):
        template = self.db.get(SubscriptionTemplate, host.subscription_template_ids[target])
        template.content = json.dumps(document)
        self.db.commit()
        return template.id

    def test_protocol_credentials_and_endpoints_in_every_supported_format(self):
        host = self.host("Endpoint", port=8443)
        for protocol, credentials in CREDENTIALS.items():
            raw = deepcopy(self.inbound.content)
            raw["protocol"] = protocol
            raw["settings"]["decryption"] = "none"
            raw["streamSettings"] = {"network": "tcp", "security": "none"}
            if protocol == "hysteria":
                raw["streamSettings"].update(network="hysteria", hysteriaSettings={"version": 2})
            self.inbound.content = raw
            self.db.commit()
            for target in ("v2ray", "v2ray-json", "clash", "sing-box", "outline"):
                with self.subTest(protocol=protocol, target=target):
                    body = self.render(target)
                    if target == "outline" and protocol != "shadowsocks":
                        self.assertEqual(body, "")
                        continue
                    self.assertTrue(body)
                    identity = credentials.get("id") or credentials.get("password") or credentials.get("auth")
                    if target == "v2ray":
                        if protocol == "vmess":
                            node = json.loads(base64.b64decode(body.removeprefix("vmess://")))
                            self.assertEqual(node["add"], host.address)
                            self.assertEqual(str(node["port"]), "8443")
                            self.assertEqual(node["id"], identity)
                        else:
                            self.assertIn(host.address + ":8443", body)
                            if protocol == "shadowsocks":
                                userinfo = urlsplit(body).netloc.rsplit("@", 1)[0]
                                self.assertIn(identity, base64.urlsafe_b64decode(userinfo + "===").decode())
                            else:
                                self.assertIn(identity, body)
                    else:
                        node = yaml.safe_load(body)
                        if target == "v2ray-json":
                            node = node[0]["outbounds"][0]
                            self.assertIn(host.address, json.dumps(node))
                        elif target == "clash":
                            node = node["proxies"][0]
                            self.assertEqual(node["server"], host.address)
                            self.assertEqual(node["port"], 8443)
                        elif target == "sing-box":
                            node = next(item for item in node["outbounds"] if item.get("server"))
                            self.assertEqual(node["server"], host.address)
                            self.assertEqual(node["server_port"], 8443)
                        else:
                            self.assertEqual(node["server"], host.address)
                            self.assertEqual(node["server_port"], 8443)
                        self.assertIn(identity, json.dumps(node))

    def test_typed_mapper_operations_reach_all_supported_output_families(self):
        self.host("Mapper", overrides={"mapper": {
            "xrayJson": [
                {"op": "set", "to": "streamSettings.sockopt.tcpFastOpen", "value": False},
                {"op": "copy", "from": "$host.finalRemark", "to": "meta.serverDescription"},
                {"op": "unset", "to": "mux"},
            ],
            "clash": [
                {"op": "set", "to": "udp", "value": False},
                {"op": "copy", "from": "$host.address", "to": "server"},
                {"op": "unset", "to": "tfo"},
            ],
            "singbox": [
                {"op": "set", "to": "tcp_fast_open", "value": False},
                {"op": "copy", "from": "$host.address", "to": "server"},
                {"op": "unset", "to": "multiplex"},
            ],
            "base64": [
                {"op": "set", "to": "allowInsecure", "value": False},
                {"op": "copy", "from": "$host.address", "to": "sni"},
                {"op": "unset", "to": "obsolete"},
            ],
        }})
        xray = json.loads(self.render("v2ray-json"))[0]["outbounds"][0]
        self.assertIs(xray["streamSettings"]["sockopt"]["tcpFastOpen"], False)
        self.assertEqual(xray["meta"]["serverDescription"], "Mapper")
        self.assertNotIn("mux", xray)
        clash = yaml.safe_load(self.render("clash"))["proxies"][0]
        self.assertIs(clash["udp"], False)
        self.assertEqual(clash["server"], "mapper.example.com")
        self.assertNotIn("tfo", clash)
        singbox = next(node for node in json.loads(self.render("sing-box"))["outbounds"] if node.get("server"))
        self.assertIs(singbox["tcp_fast_open"], False)
        self.assertEqual(singbox["server"], "mapper.example.com")
        self.assertNotIn("multiplex", singbox)
        for protocol in ("shadowsocks", "vmess"):
            with self.subTest(protocol=protocol):
                self.inbound.content = {**self.inbound.content, "protocol": protocol}
                self.db.commit()
                link = self.render("v2ray")
                if protocol == "vmess":
                    payload = json.loads(base64.b64decode(link.removeprefix("vmess://")))
                    self.assertIs(payload["allowInsecure"], False)
                    self.assertEqual(payload["sni"], "mapper.example.com")
                else:
                    query = parse_qs(urlsplit(link).query)
                    self.assertEqual(query["allowInsecure"], ["false"])
                    self.assertEqual(query["sni"], ["mapper.example.com"])
                    outline = json.loads(self.render("outline"))
                    self.assertNotIn("allowInsecure", outline)
                    self.assertNotIn("sni", outline)

    def test_finalmask_reaches_xray_unchanged_and_does_not_leak_into_other_formats(self):
        from app.models.host import HostPatch
        from app.db.crud import proxy_hosts as crud
        from test_finalmask_schema import TCP_MASKS, UDP_MASKS

        final_mask = {
            "tcp": [{"type": name, "settings": settings} for name, settings in TCP_MASKS.items()],
            "udp": [{"type": name, "settings": settings} for name, settings in UDP_MASKS.items()],
            "quicParams": {"congestion": "bbr", "disableGSO": False, "maxIdleTimeout": 0},
        }
        host = self.host("Mask", overrides={"stream": {"final_mask": final_mask}})
        crud.update_host(self.db, host, HostPatch(remark="Updated mask"))
        clone = crud.clone_host(self.db, host, "Cloned mask")
        crud.update_host(self.db, clone, HostPatch(enabled=True))
        self.assertEqual(host.overrides["stream"]["final_mask"], final_mask)
        self.assertEqual(clone.overrides["stream"]["final_mask"], final_mask)
        xray = json.loads(self.render("v2ray-json"))
        self.assertEqual(len(xray), 2)
        for profile in xray:
            self.assertEqual(profile["outbounds"][0]["streamSettings"]["finalmask"], final_mask)
        self.inbound.content = {**self.inbound.content, "protocol": "shadowsocks"}
        self.db.commit()
        for target in ("clash", "sing-box", "v2ray", "outline"):
            with self.subTest(target=target):
                body = self.render(target)
                self.assertTrue(body)
                self.assertNotIn("finalmask", body)
                self.assertNotIn("final_mask", body)
                self.assertNotIn("quicParams", body)

    def test_socket_options_reach_xray_unchanged_and_are_not_exported_to_other_formats(self):
        from test_socket_options_schema import SOCKET_OPTIONS

        self.host("Socket", overrides={"stream": {"sockopt": SOCKET_OPTIONS}})
        document = json.loads(self.render("v2ray-json"))
        self.assertEqual(document[0]["outbounds"][0]["streamSettings"]["sockopt"], SOCKET_OPTIONS)
        for target in ("clash", "sing-box", "v2ray", "outline"):
            with self.subTest(target=target):
                body = self.render(target)
                self.assertTrue(body)
                for key in ("sockopt", "customSockopt", "happyEyeballs", "tcpKeepAliveIdle"):
                    self.assertNotIn(key, body)

    def test_socket_overrides_keep_the_generated_fragment_dialer(self):
        self.host("Fragment", overrides={"fragment": "100-200,10-20,tlshello", "stream": {"sockopt": {
            "dialerProxy": "user-dialer", "tcpFastOpen": False, "mark": 0,
        }}})
        outbounds = json.loads(self.render("v2ray-json"))[0]["outbounds"]
        proxy = next(node for node in outbounds if node["tag"] == "proxy")
        sockopt = proxy["streamSettings"]["sockopt"]
        self.assertEqual(sockopt, {"dialerProxy": "mb-dialer-proxy", "tcpFastOpen": False, "mark": 0})
        self.assertIn(sockopt["dialerProxy"], {node["tag"] for node in outbounds})

    def test_tls_websocket_overrides_keep_blank_sni_empty_alpn_false_and_headers(self):
        raw = deepcopy(self.inbound.content)
        raw.update(protocol="vless")
        raw["streamSettings"] = {
            "network": "ws", "security": "tls",
            "tlsSettings": {"serverName": "inbound.example.com", "alpn": ["h2"], "allowInsecure": True},
            "wsSettings": {"path": "/inbound", "headers": {"Host": "inbound.example.com", "X-Test": "kept"}},
        }
        self.inbound.content = raw
        self.db.commit()
        self.host("Endpoint", overrides={
            "security": {"sni": "", "alpn": [], "allow_insecure": False},
            "transport": {"path": "/override", "host": "override.example.com"},
        })
        for target in ("v2ray-json", "clash", "sing-box"):
            with self.subTest(target=target):
                document = yaml.safe_load(self.render(target))
                if target == "v2ray-json":
                    stream = document[0]["outbounds"][0]["streamSettings"]
                    tls, transport = stream["tlsSettings"], stream["wsSettings"]
                    self.assertFalse(tls["allowInsecure"])
                    self.assertFalse(tls.get("serverName"))
                elif target == "clash":
                    tls = document["proxies"][0]
                    transport = tls["ws-opts"]
                    self.assertFalse(tls["skip-cert-verify"])
                    self.assertFalse(tls.get("servername"))
                else:
                    node = next(item for item in document["outbounds"] if item.get("server"))
                    tls, transport = node["tls"], node["transport"]
                    self.assertFalse(tls["insecure"])
                    self.assertFalse(tls.get("server_name"))
                self.assertEqual(tls["alpn"], [])
                self.assertEqual(transport["path"], "/override")
                self.assertEqual(transport["headers"]["X-Test"], "kept")
                self.assertEqual(transport["headers"]["Host"], "override.example.com")
        query = parse_qs(urlsplit(self.render("v2ray")).query, keep_blank_values=True)
        self.assertEqual(query["path"], ["/override"])
        self.assertEqual(query["host"], ["override.example.com"])

    def test_saved_blank_sni_flag_and_inheritance_generate_the_same_sni_as_before(self):
        raw = deepcopy(self.inbound.content)
        raw.update(protocol="vless")
        raw["streamSettings"] = {
            "network": "grpc", "security": "reality", "grpcSettings": {"serviceName": "Proxy"},
            "realitySettings": {
                "serverNames": ["inherited.example.com"],
                "publicKey": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "shortIds": ["abcdef0123456789"],
            },
        }
        self.inbound.content = raw
        self.db.commit()
        host = self.host("Endpoint")
        for flag, expected in ((True, ""), (False, "inherited.example.com")):
            host.overrides = {"security": {"keep_sni_blank": flag}}
            self.db.commit()
            for target in ("v2ray-json", "clash", "sing-box", "v2ray"):
                with self.subTest(flag=flag, target=target):
                    body = self.render(target)
                    if target == "v2ray":
                        query = parse_qs(urlsplit(body.strip()).query, keep_blank_values=True)
                        self.assertEqual(query.get("sni", [""])[0], expected)
                    else:
                        document = yaml.safe_load(body)
                        if target == "v2ray-json":
                            tls, key = document[0]["outbounds"][0]["streamSettings"]["realitySettings"], "serverName"
                        elif target == "clash":
                            tls, key = document["proxies"][0], "servername"
                        else:
                            tls = next(item["tls"] for item in document["outbounds"] if item.get("server"))
                            key = "server_name"
                        self.assertEqual(tls.get(key, ""), expected)

    def test_documented_latency_templates_generate_the_selected_hidden_pool(self):
        text = Path("docs/subscription-templates.md").read_text(encoding="utf-8")
        owner = self.host("Recipient")
        sources = [self.host(f"Source{i}", is_hidden=True) for i in range(3)]
        for heading, target in (("Xray JSON", "v2ray-json"), ("Clash", "clash"), ("sing-box", "sing-box")):
            with self.subTest(target=target):
                section = text.split(f"### {heading}\n", 1)[1].split("\n### ", 1)[0]
                document = json.loads(re.search(r"```json\n(.*?)\n```", section, re.S).group(1))
                directive = document["marzban"] if target == "v2ray-json" else document[
                    "proxy-groups" if target == "clash" else "outbounds"][0]["marzban"]
                selection = directive["injectHosts"][0] if target == "v2ray-json" else directive
                self.assertEqual(selection["selector"]["values"], [11, 12, 13])
                selection["selector"]["values"] = [host.id for host in sources]
                template_id = self.assign(owner, target, document)
                result = yaml.safe_load(self.render(target, root_ids={owner.id}))
                if target == "v2ray-json":
                    self.assertEqual([node["tag"] for node in result[0]["outbounds"]], ["pool", "pool-2", "pool-3"])
                elif target == "clash":
                    self.assertEqual(result["proxy-groups"][0]["proxies"], [host.remark for host in sources])
                else:
                    self.assertEqual(result["outbounds"][0]["outbounds"], [host.remark for host in sources])
                owner.is_hidden = True
                self.db.commit()
                self.assertEqual(self.render(target), "")
                explicit = self.render(target, template_id=template_id)
                self.assertEqual(bool(explicit), target != "v2ray-json")
                owner.is_hidden = False
                self.db.commit()

    def test_invalid_reference_shapes_raise_configuration_errors(self):
        documents = [
            ("clash", {"proxies": [], "proxy-groups": [{"name": "Best", "type": "select", "use": [{}]}]}),
            ("clash", {"proxies": [], "rules": ["no-resolve"]}),
            ("sing-box", {"outbounds": [{"tag": "Best", "type": "selector", "outbounds": "Best"}]}),
        ]
        for target, document in documents:
            with self.subTest(target=target, document=document), self.assertRaises(SubscriptionError):
                OutputValidator().validate(document, target)

    def test_reality_grpc_metadata_is_preserved_across_supported_formats(self):
        public_key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        short_id = "abcdef0123456789"
        raw = deepcopy(self.inbound.content)
        raw["protocol"] = "vless"
        raw["streamSettings"] = {
            "network": "grpc", "security": "reality", "grpcSettings": {"serviceName": "ProxyService"},
            "realitySettings": {
                "serverNames": ["reality.example.com"], "publicKey": public_key, "shortIds": [short_id],
            },
        }
        self.inbound.content = raw
        self.db.commit()
        self.host("RealityEndpoint")
        for target in ("v2ray", "v2ray-json", "clash", "sing-box"):
            with self.subTest(target=target):
                result = self.render(target)
                for value in (public_key, short_id, "reality.example.com", "ProxyService"):
                    self.assertIn(value, result)
                if target == "v2ray":
                    query = parse_qs(urlsplit(result).query)
                    self.assertEqual(query["security"], ["reality"])
                    self.assertEqual(query["type"], ["grpc"])
                elif target == "v2ray-json":
                    stream = json.loads(result)[0]["outbounds"][0]["streamSettings"]
                    self.assertEqual(stream["security"], "reality")
                    self.assertEqual(stream["grpcSettings"]["serviceName"], "ProxyService")
                elif target == "clash":
                    node = yaml.safe_load(result)["proxies"][0]
                    self.assertEqual(node["reality-opts"]["public-key"], public_key)
                else:
                    node = next(node for node in json.loads(result)["outbounds"] if node.get("server"))
                    self.assertTrue(node["tls"]["reality"]["enabled"])

    def test_composition_keeps_each_sources_protocol_port_and_credentials(self):
        owner = self.host("Recipient")
        shadowsocks = self.host("ShadowsocksSource", is_hidden=True, port=1443)
        self.inbound = ProxyInbound(tag="VLESS", content={
            "tag": "VLESS", "protocol": "vless", "port": 2443,
            "settings": {"clients": [], "decryption": "none"},
            "streamSettings": {"network": "ws", "security": "tls",
                               "wsSettings": {"path": "/vless"}, "tlsSettings": {"serverName": "tls.example.com"}},
        })
        self.db.add(self.inbound)
        self.db.commit()
        vless = self.host("VlessSource", is_hidden=True, overrides={"security": {"sni": "tls.example.com"}})
        selection = {"selector": {"type": "ids", "values": [vless.id, shadowsocks.id]}, "selectFrom": "ALL"}
        templates = {
            "v2ray-json": {"outbounds": [], "marzban": {"addVirtualHostAsOutbound": False,
                                                        "injectHosts": [dict(selection, tagPrefix="pool")]}},
            "clash": {"proxies": [], "proxy-groups": [{"name": "Best", "type": "url-test", "proxies": [],
                      "marzban": dict(selection, **{"include-proxies": True})}]},
            "sing-box": {"outbounds": [{"type": "urltest", "tag": "best", "outbounds": [],
                         "marzban": dict(selection, includeProxies=True)}]},
        }
        for target, template in templates.items():
            with self.subTest(target=target):
                self.assign(owner, target, template)
                result = yaml.safe_load(self.render(target, root_ids={owner.id}))
                if target == "v2ray-json":
                    nodes = result[0]["outbounds"]
                    self.assertEqual([node["protocol"] for node in nodes], ["vless", "shadowsocks"])
                elif target == "clash":
                    self.assertEqual(result["proxy-groups"][0]["proxies"], [vless.remark, shadowsocks.remark])
                    nodes = [node for node in result["proxies"] if node["name"] in {vless.remark, shadowsocks.remark}]
                else:
                    self.assertEqual(result["outbounds"][0]["outbounds"], [vless.remark, shadowsocks.remark])
                    nodes = [node for node in result["outbounds"] if node.get("server")]
                    nodes = [node for node in nodes if node["tag"] in {vless.remark, shadowsocks.remark}]
                serialized = json.dumps(nodes)
                for value in (vless.address, shadowsocks.address, "1443", "2443", ACCOUNT_ID,
                              "test-password", "/vless", "tls.example.com"):
                    self.assertIn(value, serialized)
