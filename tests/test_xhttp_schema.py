"""XHTTP API validation, sparse round trips and Monaco capabilities parity."""

from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase

from pydantic import ValidationError

from app.models.host import HostOverrides
from app.models.xhttp import XhttpDownloadSettings, XhttpExtra, XhttpMux, XhttpSettings
from app.subscription.capabilities import host_capabilities


DOWNLOAD = {
    "address": "download.example.com", "port": 443, "network": "xhttp", "security": "tls",
    "tlsSettings": {"serverName": "download.example.com", "alpn": ["h2"], "fingerprint": "chrome"},
    "xhttpSettings": {"path": "/down", "extra": {"xmux": {"maxConnections": "4-2"}}},
    "sockopt": {"tcpFastOpen": False, "tcpKeepAliveIdle": -1, "tcpKeepAliveInterval": 0},
    "finalmask": {"tcp": []},
}
EXTRA = {
    "scMaxBufferedPosts": 0, "xPaddingObfsMode": False, "uplinkHTTPMethod": "PUT",
    "xPaddingBytes": "1000-100", "xPaddingKey": "padding", "xPaddingHeader": "X-Padding",
    "xPaddingMethod": "tokenish", "xPaddingPlacement": "queryInHeader",
    "noGRPCHeader": False, "noSSEHeader": False, "scMaxEachPostBytes": "1000000-500000",
    "scMaxConcurrentPosts": 100, "scMinPostsIntervalMs": 0, "scStreamUpServerSecs": "20-80",
    "sessionIDPlacement": "header", "sessionIDKey": "X-Session", "sessionIDTable": "Base62",
    "sessionIDLength": "16-24", "seqPlacement": "query", "seqKey": "sequence",
    "uplinkDataPlacement": "body", "uplinkDataKey": "X-Data", "uplinkChunkSize": "3000-4000",
    "serverMaxHeaderBytes": 0, "headers": {"X-Test": "one", "User-Agent": "Mozilla/5.0"},
    "xmux": {"maxConnections": "4-2", "maxConcurrency": 0, "cMaxReuseTimes": "0",
             "hMaxRequestTimes": "600-900", "hMaxReusableSecs": "1800-3000", "hKeepAlivePeriod": -1},
    "downloadSettings": DOWNLOAD,
}


class XhttpSchemaTests(TestCase):
    def test_all_supported_extra_fields_and_legacy_settings_round_trip_without_defaults(self):
        for extra in ({}, EXTRA, {"xmux": {}}, {"headers": {}}, {"scMaxConcurrentPosts": "100"}):
            original = deepcopy(extra)
            value = {"transport": {"xhttp": {"extra": extra}}}
            parsed = HostOverrides.model_validate(value)
            self.assertEqual(parsed.model_dump(exclude_none=True, exclude_unset=True), value)
            self.assertEqual(extra, original)

    def test_all_xmux_ranges_preserve_numbers_numeric_strings_reversed_and_signed_ranges(self):
        for name in ("maxConnections", "maxConcurrency", "cMaxReuseTimes", "hMaxRequestTimes", "hMaxReusableSecs"):
            for value in (0, 1, -1, -2147483648, 2147483647, "", "0", "4-2", "-2--1", "+1--2"):
                with self.subTest(name=name, value=value):
                    parsed = XhttpMux.model_validate({name: value})
                    self.assertEqual(parsed.model_dump(exclude_unset=True), {name: value})
        for name in ("scMaxEachPostBytes", "scMinPostsIntervalMs", "scStreamUpServerSecs", "uplinkChunkSize",
                     "sessionIDLength", "scMaxConcurrentPosts"):
            for value in (0, -1, "", "+1", "20-10", "-1--2"):
                with self.subTest(name=name, value=value):
                    self.assertEqual(XhttpExtra.model_validate(
                        {name: value}).model_dump(exclude_unset=True), {name: value})

    def test_ranges_reject_booleans_floats_malformed_text_and_int32_overflow(self):
        for value in (True, False, 1.5, "1.5", "1 - 2", "1-", "--1", "invalid", 2147483648, -2147483649,
                      "2147483648", "-2147483649-1", "1-2147483648", [], {}):
            for document in ({"xmux": {"maxConnections": value}}, {"scMinPostsIntervalMs": value}):
                with self.subTest(document=document), self.assertRaises(ValidationError):
                    XhttpExtra.model_validate(document)

    def test_padding_enums_headers_unknown_fields_nulls_and_scalar_limits_are_validated(self):
        invalid = [
            {"unknown": 1}, {"mode": "packet-up"}, {"xPaddingMethod": "invalid"},
            {"xPaddingPlacement": "path"}, {"sessionIDPlacement": "body"}, {"seqPlacement": "invalid"},
            {"uplinkDataPlacement": "query"}, {"uplinkHTTPMethod": "GET /"}, {"uplinkHTTPMethod": ""},
            {"xPaddingBytes": -1}, {"xPaddingBytes": "0-1"}, {"xPaddingBytes": "10-0"},
            {"serverMaxHeaderBytes": -1}, {"serverMaxHeaderBytes": 2147483648},
            {"scMaxBufferedPosts": -1}, {"scMaxBufferedPosts": 9223372036854775808},
            {"noGRPCHeader": 0}, {"xPaddingObfsMode": "false"},
            {"headers": {"Host": "example.com"}}, {"headers": {"hOsT": "example.com"}},
            {"headers": {"bad name": "value"}}, {"headers": {"X-Test": "a\r\nb"}}, {"headers": {"X-Test": 1}},
            {"xmux": {"hKeepAlivePeriod": True}}, {"xmux": {"hKeepAlivePeriod": 9223372036854775808}},
        ]
        invalid += [{name: None} for name in XhttpExtra.model_fields]
        invalid += [{"xmux": {name: None}} for name in XhttpMux.model_fields]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                XhttpExtra.model_validate(value)
        for padding in (0, "", "0", "0-00", "100-1000", "1000-100", 100):
            XhttpExtra.model_validate({"xPaddingBytes": padding})
        self.assertEqual(XhttpExtra.model_validate({"uplinkHTTPMethod": " put "}).uplinkHTTPMethod, "PUT")

    def test_xmux_concurrency_and_connection_count_are_mutually_exclusive_only_when_positive(self):
        for value in ({"maxConnections": "2-4", "maxConcurrency": 1},
                      {"maxConnections": "-1-2", "maxConcurrency": "4-0"}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                XhttpMux.model_validate(value)
        for value in ({"maxConnections": 0, "maxConcurrency": "8-16"},
                      {"maxConnections": "4-2", "maxConcurrency": "-2--1"}):
            XhttpMux.model_validate(value)

    def test_session_alphabets_length_and_entropy_are_checked_without_large_integer_work(self):
        for table, length in (("Base62", 6), ("hex", 8), ("ab", 31), ("abcdefg", "1-11"),
                              ("number", "10-20"), ("Base62", 2147483647), ("", -1)):
            XhttpExtra.model_validate({"sessionIDTable": table, "sessionIDLength": length})
        for value in ({"sessionIDTable": "Base62"}, {"sessionIDTable": "Base62", "sessionIDLength": 5},
                      {"sessionIDTable": "ab", "sessionIDLength": 30},
                      {"sessionIDTable": "a", "sessionIDLength": 2147483647},
                      {"sessionIDTable": "ä", "sessionIDLength": 32},
                      {"sessionIDTable": "hex", "sessionIDLength": "0-8"}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                XhttpExtra.model_validate(value)

    def test_mode_constraints_apply_to_native_settings_and_atomic_extra(self):
        for mode in ("auto", "stream-up", "stream-one"):
            for extra in ({"uplinkHTTPMethod": "GET"}, {"uplinkDataPlacement": "header"},
                          {"uplinkDataPlacement": "cookie"}):
                with self.subTest(mode=mode, extra=extra), self.assertRaises(ValueError):
                    XhttpExtra.model_validate(extra).validate_mode(mode)
        XhttpExtra.model_validate(EXTRA).validate_mode("packet-up")
        with self.assertRaises(ValueError):
            XhttpExtra.model_validate(EXTRA).validate_mode("stream-one")
        for extra in ({"uplinkHTTPMethod": "GET"}, {"uplinkDataPlacement": "header"}):
            for document in ({"mode": "stream-up", **extra}, {"mode": "stream-up", "extra": extra}):
                with self.subTest(document=document), self.assertRaises(ValidationError):
                    XhttpSettings.model_validate(document)
        ignored = {"mode": "stream-one", "uplinkHTTPMethod": "GET", "sessionIDTable": "Base62", "extra": {}}
        self.assertEqual(XhttpSettings.model_validate(ignored).model_dump(exclude_unset=True), ignored)

    def test_downstream_requires_an_endpoint_and_xhttp_transport_and_validates_nested_models(self):
        for value in (DOWNLOAD, {"address": "one.example.com", "port": 80, "method": "splithttp"}):
            self.assertEqual(XhttpDownloadSettings.model_validate(value).model_dump(exclude_unset=True), value)
        invalid = [{}, {**DOWNLOAD, "port": 0}, {**DOWNLOAD, "address": ""}, {**DOWNLOAD, "network": "tcp"},
                   {"address": "one.example.com", "port": 80}, {**DOWNLOAD, "unknown": 1},
                   {**DOWNLOAD, "security": "reality"}, {**DOWNLOAD, "sockopt": {"tcpFastOpen": "true"}},
                   {**DOWNLOAD, "xhttpSettings": {"mode": "stream-one", "downloadSettings": DOWNLOAD}},
                   {**DOWNLOAD, "tlsSettings": {"minVersion": "2"}}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                XhttpDownloadSettings.model_validate(value)

    def test_editor_fixture_matches_capabilities_and_every_xhttp_field_is_documented(self):
        schema = XhttpExtra.model_json_schema()
        fixture = Path(__file__).resolve().parents[1] / "app/dashboard/tests/fixtures/xhttp-schema.json"
        self.assertEqual(json.loads(fixture.read_text(encoding="utf-8")), schema)
        definitions = host_capabilities()["overrides_schema"]["$defs"]
        for name, definition in schema["$defs"].items():
            self.assertEqual(definitions[name], definition)
        expected = {
            "headers", "xPaddingBytes", "xPaddingObfsMode", "xPaddingKey", "xPaddingHeader", "xPaddingPlacement",
            "xPaddingMethod", "uplinkHTTPMethod", "sessionIDPlacement", "sessionIDKey", "sessionIDTable",
            "sessionIDLength", "seqPlacement", "seqKey", "uplinkDataPlacement", "uplinkDataKey", "uplinkChunkSize",
            "noGRPCHeader", "noSSEHeader", "scMaxEachPostBytes", "scMinPostsIntervalMs", "scMaxBufferedPosts",
            "scStreamUpServerSecs", "serverMaxHeaderBytes", "xmux", "downloadSettings", "scMaxConcurrentPosts",
        }
        root = definitions["XhttpExtra"]
        self.assertEqual(set(root["properties"]), expected)
        for name in ("XhttpExtra", "XhttpMux", "XhttpDownloadSettings", "XhttpSettings", "XhttpReality", "XhttpTLS"):
            definition = definitions[name]
            self.assertFalse(definition["additionalProperties"])
            self.assertTrue(definition.get("description"), name)
            for field, value in definition["properties"].items():
                self.assertTrue(value.get("description"), (name, field))
        for snippet in root["defaultSnippets"]:
            XhttpExtra.model_validate(snippet["body"])
