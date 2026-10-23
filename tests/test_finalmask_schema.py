"""FinalMask loader coverage, sparse storage and parity with the editor schema."""

from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase

from pydantic import ValidationError

from app.models.finalmask import FinalMask
from app.models.host import HostOverrides
from app.subscription.capabilities import host_capabilities


TCP_MASKS = {
    "filter": {"blockedSourceIPs": ["192.0.2.0/24"], "allowedSourceIPs": []},
    "header-custom": {"clients": [[{"type": "hex", "packet": "160301", "capture": "hello", "delay": "0-10"}]],
                      "servers": [[{"reuse": "hello"}]], "errors": []},
    "fragment": {"packets": "tlshello", "lengths": [0, "100-200"], "delays": [0, "10-20"], "maxSplit": 0},
    "sudoku": {"password": "shared", "ascii": "prefer_ascii", "customTables": ["xpxpvvvv"], "paddingMin": 0},
    "xmc": {"password": "shared", "hostname": "minecraft.example.com", "profiles": [{
        "username": "test_player", "uuid": "12345678-1234-5678-1234-567812345678",
        "texturesValue": "signed-payload", "texturesSignature": "signature",
    }]},
}
UDP_MASKS = {
    "filter": TCP_MASKS["filter"],
    "header-custom": {"mode": "prefix", "client": [{"rand": 4, "randRange": "0-255", "capture": "seed"}],
                      "server": [{"transform": {"op": "concat", "args": [
                          {"reuse": "seed"}, {"transform": {"op": "be16", "args": [{"metadata": "remote_port"}]}},
                      ]}}]},
    "mkcp-legacy": {"header": "dns", "value": "dns.example.com"},
    "noise": {"reset": "30-60", "noise": [{"type": "exp", "packet": "<b 0001><r 8-16><rc 3><rd 2><t><c><n>",
                                           "delay": "0-10"}]},
    "salamander": {"password": "shared", "packetSize": "1024-1280"},
    "sudoku": TCP_MASKS["sudoku"],
    "xdns": {"domains": [{"names": ["tunnel.example.com"], "lenLimit": 255, "labelLimit": 63,
                          "types": [1, 5, 16, 28], "edns0": 1232}],
             "resolvers": [{"addrs": ["1.1.1.1:53", "https://dns.example.com/dns-query"], "worker": 32,
                            "tlsConfig": {"serverName": "dns.example.com", "alpn": ["h2"]},
                            "quicConfig": {"congestion": "bbr"}}], "extraPoll": 3},
    "xicmp": {"dgram": False, "ips": ["192.0.2.1", "2001:db8::1"]},
    "realm": {"url": "realm://token@signal.example.com/session", "stunServers": ["stun.example.com:3478"],
              "ipMode": "dual", "tlsConfig": {"serverName": "signal.example.com"},
              "portMapping": {"enabled": False, "timeout": 10, "lifetime": 60}},
    "udphop": {"mode": "intervallocal,intervalremote", "interval": "5-30", "remoteIPs": ["192.0.2.0/24"],
               "remotePorts": "443,20000-50000"},
}


class FinalMaskSchemaTests(TestCase):
    def test_all_registered_tcp_and_udp_loaders_round_trip_without_defaults(self):
        for family, masks in (("tcp", TCP_MASKS), ("udp", UDP_MASKS)):
            for mask_type, settings in masks.items():
                with self.subTest(family=family, mask=mask_type):
                    value = {family: [{"type": mask_type, "settings": deepcopy(settings)}]}
                    parsed = HostOverrides.model_validate({"stream": {"final_mask": value}})
                    stored = parsed.model_dump(exclude_none=True, exclude_unset=True, by_alias=True)
                    self.assertEqual(stored, {"stream": {"final_mask": value}})
        for empty in ({}, {"tcp": [], "udp": []}, {"udp": [{"type": "salamander"}]}):
            self.assertEqual(FinalMask.model_validate(empty).model_dump(exclude_none=True, exclude_unset=True), empty)

    def test_legacy_ranges_names_and_explicit_zero_false_and_null_packets_are_preserved(self):
        value = {
            "tcp": [{"type": "fragment", "settings": {"length": "200-100", "delay": "", "maxSplit": 0}},
                    {"type": "sudoku", "settings": {"custom_table": "xpxpvvvv", "custom_tables": [],
                                                    "padding_min": 0, "padding_max": 100}}],
            "udp": [{"type": "header-custom", "settings": {"client": [{"packet": None}]}},
                    {"type": "xicmp", "settings": {"dgram": False, "ips": []}}],
            "quicParams": {"disableGSO": False, "brutalUp": "0", "maxIdleTimeout": 0,
                           "udpHop": {"ports": "443,20000-50000", "interval": "5-30"}},
        }
        self.assertEqual(FinalMask.model_validate(value).model_dump(exclude_none=True, exclude_unset=True), value)

    def test_unknown_fields_wrong_families_and_bad_settings_are_rejected(self):
        invalid = [
            {"tcp": [{"type": "noise"}]}, {"udp": [{"type": "fragment", "settings": {"length": 100}}]},
            {"tcp": [{"type": "unknown"}]}, {"unknown": True},
            {"udp": [{"type": "salamander", "settings": {"unknown": True}}]},
            {"tcp": [{"type": "fragment", "settings": {}}]},
            {"tcp": [{"type": "fragment", "settings": {"lengths": ["0-10"]}}]},
            {"tcp": [{"type": "fragment", "settings": {"length": -1}}]},
            {"tcp": [{"type": "fragment", "settings": {"length": True}}]},
            {"tcp": [{"type": "xmc", "settings": {"password": "", "profiles": []}}]},
            {"udp": [{"type": "header-custom", "settings": {"client": [{"delay": 10}]}}]},
            {"udp": [{"type": "realm", "settings": {"url": "https://example.com/id", "stunServers": []}}]},
            {"udp": [{"type": "udphop", "settings": {"mode": "random"}}]},
            {"udp": [{"type": "udphop", "settings": {"mode": "intervalremote", "interval": "0-10"}}]},
            {"udp": [{"type": "salamander", "settings": {"packetSize": 2049}}]},
            {"udp": [{"type": "salamander", "settings": {"packetSize": "0-100"}}]},
            {"udp": [{"type": "xicmp", "settings": {"ips": ["192.0.2.0/24"]}}]},
            {"udp": [{"type": "xdns", "settings": {"extraPoll": 4}}]},
            {"udp": [{"type": "xdns", "settings": {"resolvers": [{"addrs": ["tls://dns.example.com"]}]}}]},
            {"udp": [{"type": "sudoku", "settings": {"customTable": "xxxxxxxx"}}]},
            {"quicParams": {"maxIdleTimeout": 3}}, {"quicParams": {"initStreamReceiveWindow": 16383}},
            {"quicParams": {"congestion": "force-brutal"}}, {"quicParams": {"brutalUp": "1 kbps"}},
            {"quicParams": {"brutalUp": "10 bbps"}}, {"quicParams": {"brutalUp": 0}},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                FinalMask.model_validate(value)

    def test_headers_payloads_expressions_and_noise_conflicts(self):
        valid = [
            {"type": "hex", "packet": "0001ff"}, {"type": "base64", "packet": "AAE="},
            {"type": "str", "packet": "hello"}, {"packet": [0, 255]}, {"packet": "AAE="},
            {"rand": 0}, {"transform": {"op": "be16", "args": [{"u64": 0}]}},
            {"packet": [1], "rand": 0, "reuse": ""},
            {"transform": {"op": "concat", "args": [{"bytes": [1]}, {"type": "hex", "bytes": "02"}]}},
        ]
        for item in valid:
            value = {"udp": [{"type": "header-custom", "settings": {"client": [item]}}]}
            self.assertEqual(FinalMask.model_validate(value).model_dump(exclude_none=True, exclude_unset=True), value)
        invalid = [
            {"packet": [256]}, {"randRange": "0-256"}, {"type": "hex", "packet": "0xf"},
            {"type": "base64", "packet": "!"}, {"type": "str", "packet": [1]},
            {"packet": [1], "rand": 1}, {"capture": "bad-name", "packet": []}, {"capture": "name"},
            {"transform": {"op": "unknown", "args": [{"u64": 0}]}},
            {"transform": {"op": "be16", "args": [{"u64": 0}, {"u64": 1}]}},
            {"transform": {"op": "be16", "args": [{"u64": 0, "bytes": []}]}},
            {"transform": {"op": "be16", "args": [{"metadata": "unknown"}]}},
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValidationError):
                FinalMask.model_validate({"udp": [{"type": "header-custom", "settings": {"client": [item]}}]})
        for settings in (
            {"noise": [{"rand": 1, "packet": []}]}, {"noise": [{"type": "exp", "packet": "<r 65536>"}]},
            {"noise": [{"type": "exp", "packet": "<t 1>"}]}, {"noise": [{"type": "exp", "packet": "<b 0>"}]},
            {"script": "return {}", "noise": [{"rand": 1}]},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValidationError):
                FinalMask.model_validate({"udp": [{"type": "noise", "settings": settings}]})

    def test_quic_bounds_bandwidth_units_and_tls_fields(self):
        settings = {"congestion": "force-brutal", "brutalUp": ".524288 mbps", "brutalDown": "60 mbps",
                    "initStreamReceiveWindow": 16384, "maxIdleTimeout": 120, "keepAlivePeriod": 60,
                    "maxIncomingStreams": 8, "disableChromeParrot": False, "disableStatelessReset": True}
        self.assertEqual(FinalMask.model_validate({"quicParams": settings}).quicParams.brutalUp, ".524288 mbps")
        for rate in ("", "0", "524288", "524288bps", "512 kbps", ".5 mbps", "1m", "1 gbps", "1 tbps"):
            with self.subTest(rate=rate):
                FinalMask.model_validate({"quicParams": {"brutalUp": rate}})

    def test_editor_fixture_and_capabilities_document_every_loader_and_property(self):
        schema = FinalMask.model_json_schema()
        fixture = Path(__file__).resolve().parents[1] / "app/dashboard/tests/fixtures/finalmask-schema.json"
        self.assertEqual(json.loads(fixture.read_text(encoding="utf-8")), schema)
        definitions = host_capabilities()["overrides_schema"]["$defs"]
        self.assertEqual(definitions["FinalMask"], {key: value for key, value in schema.items() if key != "$defs"})
        for name, definition in schema["$defs"].items():
            self.assertEqual(definitions[name], definition)
            self.assertFalse(definition["additionalProperties"], name)
            self.assertTrue(definition["description"], name)
            for field, value in definition.get("properties", {}).items():
                self.assertTrue(value.get("description"), f"{name}.{field}")
        for family, masks in (("tcp", TCP_MASKS), ("udp", UDP_MASKS)):
            items = schema["properties"][family]["anyOf"][0]["items"]
            self.assertEqual(set(items["discriminator"]["mapping"]), set(masks))
        for snippet in schema["defaultSnippets"]:
            FinalMask.model_validate(snippet["body"])
