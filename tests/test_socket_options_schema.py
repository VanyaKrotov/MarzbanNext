"""Socket request validation, sparse serialization and editor capabilities parity."""

from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase

from pydantic import ValidationError

from app.models.host import HostOverrides
from app.models.socket_options import SocketOptions
from app.subscription.capabilities import host_capabilities


SOCKET_OPTIONS = {
    "mark": 0, "tcpFastOpen": False, "tcpMaxSeg": 1440, "tcpWindowClamp": 600, "tcpUserTimeout": 10000,
    "tcpKeepAliveIdle": -1, "tcpKeepAliveInterval": 0, "tcpcongestion": "bbr", "tcpMptcp": False,
    "tproxy": "off", "domainStrategy": "UseIP", "addressPortStrategy": "none",
    "happyEyeballs": {"tryDelayMs": 250, "prioritizeIPv6": False, "interleave": 1, "maxConcurrentTry": 4},
    "dialerProxy": "", "interface": "", "V6Only": False, "acceptProxyProtocol": False,
    "trustedXForwardedFor": [], "penetrate": False,
    "customSockopt": [
        {"system": "linux", "network": "tcp", "type": "str", "level": "6", "opt": "13", "value": "bbr"},
        {"system": "windows", "network": "tcp4", "type": "int", "opt": "1", "value": "0"},
    ],
}


class SocketOptionsSchemaTests(TestCase):
    def test_socket_options_round_trip_without_adding_defaults_or_mutating_input(self):
        for value in (SOCKET_OPTIONS, {}, {"tcpFastOpen": 0, "customSockopt": [], "happyEyeballs": {}}):
            original = deepcopy(value)
            options = HostOverrides.model_validate({"stream": {"sockopt": value}})
            stored = options.model_dump(exclude_none=True, exclude_unset=True, by_alias=True)
            self.assertEqual(stored, {"stream": {"sockopt": value}})
            self.assertEqual(value, original)
            self.assertEqual(HostOverrides.model_validate(stored), options)

    def test_fast_open_preserves_boolean_and_integer_values(self):
        for value in (False, True, -2147483648, -1, 0, 1, 256, 2147483647):
            with self.subTest(value=value):
                parsed = SocketOptions.model_validate({"tcpFastOpen": value})
                self.assertIs(type(parsed.tcpFastOpen), type(value))
                self.assertEqual(parsed.model_dump(exclude_none=True, exclude_unset=True), {"tcpFastOpen": value})

    def test_documented_strategy_names_and_native_case_variations_preserve_their_values(self):
        schema = SocketOptions.model_json_schema()
        for name in ("tproxy", "domainStrategy", "addressPortStrategy"):
            choices = schema["properties"][name]["anyOf"][0]["anyOf"][0]["enum"]
            for choice in choices:
                for value in (choice, choice.lower(), choice.upper()):
                    with self.subTest(name=name, value=value):
                        self.assertEqual(SocketOptions.model_validate({name: value}).model_dump(
                            exclude_none=True, exclude_unset=True), {name: value})

    def test_alternate_key_spellings_keep_xray_last_key_wins_order(self):
        for pairs in (
            [("tcpcongestion", "bbr"), ("tcpCongestion", "cubic"), ("V6Only", True), ("v6only", False)],
            [("tcpCongestion", "cubic"), ("tcpcongestion", "bbr"), ("v6only", False), ("V6Only", True)],
        ):
            value = dict(pairs)
            result = SocketOptions.model_validate(value).model_dump(exclude_none=True, exclude_unset=True)
            self.assertEqual(list(result.items()), pairs)

    def test_invalid_types_ranges_fields_strategies_and_keepalive_conflicts_are_rejected(self):
        invalid = [
            {"unknown": True}, {"tcpFastOpen": "true"}, {"tcpFastOpen": 1.5}, {"tcpFastOpen": 2147483648},
            {"mark": True}, {"mark": 2147483648}, {"tcpKeepAliveIdle": -2147483649}, {"tcpMaxSeg": "1440"},
            {"tcpMptcp": 1}, {"domainStrategy": "IPv4"}, {"addressPortStrategy": "SRV"}, {"tproxy": "enabled"},
            {"tcpKeepAliveIdle": -1, "tcpKeepAliveInterval": 1},
            {"tcpKeepAliveIdle": 45, "tcpKeepAliveInterval": -1},
            {"happyEyeballs": {"unknown": 1}}, {"happyEyeballs": {"tryDelayMs": -1}},
            {"happyEyeballs": {"interleave": 4294967296}}, {"happyEyeballs": {"maxConcurrentTry": True}},
            {"trustedXForwardedFor": [1]}, {"interface": False}, {"dialerProxy": []},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                SocketOptions.model_validate(value)
        for value in ({"tcpKeepAliveIdle": -1}, {"tcpKeepAliveInterval": -1},
                      {"tcpKeepAliveIdle": 0, "tcpKeepAliveInterval": -1},
                      {"happyEyeballs": {"interleave": 0, "maxConcurrentTry": 0}}):
            SocketOptions.model_validate(value)

    def test_custom_socket_variants_validate_decimal_strings_and_platform_constraints(self):
        valid = [
            {"type": "int", "opt": "1", "value": "0"}, {"type": "int", "opt": "+1", "value": "-1", "level": ""},
            {"type": "int", "opt": "1", "value": "-9223372036854775808"},
            {"type": "int", "opt": "1", "value": "9223372036854775807"},
            {"type": "str", "opt": "13", "value": ""}, {"type": "str", "opt": "13", "value": "bbr"},
        ]
        for option in valid:
            value = {"customSockopt": [option]}
            with self.subTest(option=option):
                self.assertEqual(SocketOptions.model_validate(value).model_dump(
                    exclude_none=True, exclude_unset=True), value)
        invalid = [
            {}, {"type": "int", "value": "1"}, {"type": "str", "opt": "13"},
            {"type": "bool", "opt": "1", "value": "1"}, {"type": "int", "opt": 1, "value": "1"},
            {"type": "int", "opt": "0x1", "value": "1"}, {"type": "int", "opt": "1", "value": 1},
            {"type": "int", "opt": "1", "value": "bbr"}, {"type": "int", "opt": "1", "value": "1.5"},
            {"type": "int", "opt": "1", "value": "9223372036854775808"},
            {"type": "str", "opt": "1", "value": "bbr", "system": "windows"},
            {"type": "int", "opt": "1", "value": "1", "network": "http"},
            {"type": "int", "opt": "1", "value": "1", "extra": True},
        ]
        for option in invalid:
            with self.subTest(option=option), self.assertRaises(ValidationError):
                SocketOptions.model_validate({"customSockopt": [option]})

    def test_ech_socket_uses_the_same_contract(self):
        value = {"stream": {"final_mask": {"udp": [{"type": "realm", "settings": {
            "url": "realm://token@signal.example.com/id", "stunServers": ["stun.example.com:3478"],
            "tlsConfig": {"echSockopt": SOCKET_OPTIONS},
        }}]}}}
        parsed = HostOverrides.model_validate(value)
        self.assertEqual(parsed.model_dump(exclude_none=True, exclude_unset=True), value)
        value["stream"]["final_mask"]["udp"][0]["settings"]["tlsConfig"]["echSockopt"] = {"tcpFastOpen": "yes"}
        with self.assertRaises(ValidationError):
            HostOverrides.model_validate(value)

    def test_editor_fixture_and_capabilities_describe_all_fields_and_examples(self):
        fixture = Path(__file__).resolve().parents[1] / "app/dashboard/tests/fixtures/socket-options-schema.json"
        schema = SocketOptions.model_json_schema()
        self.assertEqual(json.loads(fixture.read_text(encoding="utf-8")), schema)
        definitions = host_capabilities()["overrides_schema"]["$defs"]
        self.assertEqual(definitions["SocketOptions"], {key: value for key, value in schema.items() if key != "$defs"})
        expected = {
            "mark", "tcpFastOpen", "tcpMaxSeg", "tcpWindowClamp", "tcpUserTimeout", "tcpKeepAliveIdle",
            "tcpKeepAliveInterval", "tcpcongestion", "tcpCongestion", "tcpMptcp", "tproxy", "domainStrategy",
            "addressPortStrategy", "happyEyeballs", "dialerProxy", "interface", "V6Only", "v6only",
            "acceptProxyProtocol", "trustedXForwardedFor", "penetrate", "customSockopt",
        }
        self.assertEqual(set(schema["properties"]), expected)
        for definition in (schema, *schema["$defs"].values()):
            self.assertFalse(definition["additionalProperties"])
            self.assertTrue(definition["description"])
            for value in definition["properties"].values():
                self.assertTrue(value.get("description"))
        for name, definition in schema["$defs"].items():
            self.assertEqual(definitions[name], definition)
        for snippet in schema["defaultSnippets"]:
            SocketOptions.model_validate(snippet["body"])
