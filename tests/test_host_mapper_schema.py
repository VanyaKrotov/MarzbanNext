"""Mapper request validation, editor schema parity and operation semantics."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from pydantic import ValidationError

from app.models.host import HostOverrides, normalize_stored_host_overrides
from app.models.host_mapper import HostMapperOptions
from app.subscription.mapper import HostMapper
from app.subscription.capabilities import host_capabilities


FORMATS = ("xrayJson", "clash", "singbox", "base64")
JSON_VALUES = ("example.com", 0, -1, 1.5, False, True, None, [], {}, [None, False, {"key": 0}])


class HostMapperSchemaTests(TestCase):
    def test_each_operation_and_every_json_value_round_trip_in_each_format(self):
        for target in FORMATS:
            for value in JSON_VALUES:
                with self.subTest(target=target, value=value):
                    operations = [
                        {"op": "set", "to": "options.value", "value": value},
                        {"op": "copy", "from": "$host.port", "to": "options.port"},
                        {"op": "unset", "to": "options.obsolete"},
                    ]
                    parsed = HostOverrides.model_validate({"mapper": {target: operations}})
                    stored = parsed.model_dump(exclude_none=True, exclude_unset=True, by_alias=True)
                    self.assertEqual(stored, {"mapper": {target: operations}})
                    self.assertEqual(HostOverrides.model_validate(stored), parsed)

    def test_invalid_variants_are_rejected_for_every_format(self):
        invalid = [
            {}, {"op": "move", "to": "udp"}, {"op": "set", "value": True},
            {"op": "set", "to": "udp"}, {"op": "copy", "to": "udp"},
            {"op": "copy", "to": "udp", "from": ""},
            {"op": "copy", "to": "udp", "from": None},
            {"op": "copy", "to": "udp", "from": 1},
            {"op": "set", "to": "udp", "value": True, "from": "$host.port"},
            {"op": "copy", "to": "udp", "from": "$host.port", "value": True},
            {"op": "unset", "to": "udp", "value": None},
            {"op": "unset", "to": "udp", "from": "$host.port"},
            {"op": "unset", "to": "udp", "unknown": True},
            *({"op": "unset", "to": path} for path in ("", 1, None, "a.__proto__.b", "constructor", "__class__")),
        ]
        for target in FORMATS:
            for operation in invalid:
                with self.subTest(target=target, operation=operation), self.assertRaises(ValidationError):
                    HostMapperOptions.model_validate({target: [operation]})
        for target in ("outline", "v2ray-json", "sing-box", "clash-meta", "mihomo"):
            with self.subTest(target=target), self.assertRaises(ValidationError):
                HostMapperOptions.model_validate({target: []})

    def test_editor_fixture_is_the_actual_backend_schema(self):
        fixture = Path(__file__).resolve().parents[1] / "app/dashboard/tests/fixtures/host-mapper-schema.json"
        schema = HostMapperOptions.model_json_schema()
        self.assertEqual(json.loads(fixture.read_text(encoding="utf-8")), schema)
        capabilities = host_capabilities()["overrides_schema"]["$defs"]
        self.assertEqual(capabilities["HostMapperOptions"], {
                         key: value for key, value in schema.items() if key != "$defs"})
        for name, definition in schema["$defs"].items():
            self.assertEqual(capabilities[name], definition)

    def test_schema_documents_every_family_operation_and_property(self):
        schema = HostMapperOptions.model_json_schema()
        for snippet in schema["defaultSnippets"]:
            HostMapperOptions.model_validate(snippet["body"])
        for target in FORMATS:
            field = schema["properties"][target]
            self.assertTrue(field["description"])
            operations = field["anyOf"][0]["items"]
            self.assertEqual(operations["discriminator"]["propertyName"], "op")
            self.assertEqual(len(operations["oneOf"]), 3)
        for name, required in (("MapperSet", {"op", "to", "value"}),
                               ("MapperCopy", {"op", "to", "from"}), ("MapperUnset", {"op", "to"})):
            definition = schema["$defs"][name]
            self.assertEqual(set(definition["required"]), required)
            self.assertFalse(definition["additionalProperties"])
            self.assertTrue(definition["description"])
            self.assertTrue(definition["defaultSnippets"])
            for field in definition["properties"].values():
                self.assertTrue(field["description"])
        value_types = schema["$defs"]["MapperSet"]["properties"]["value"]["anyOf"]
        self.assertEqual({option["type"] for option in value_types},
                         {"string", "number", "boolean", "null", "array", "object"})
        self.assertTrue(all(option["description"] for option in value_types))

    def test_stored_ignored_fields_and_omitted_null_set_preserve_behavior(self):
        stored = {"mapper": {"clash": [
            {"op": "set", "to": "a", "from": "ignored"},
            {"op": "copy", "to": "b", "from": "$host.port", "value": "ignored"},
            {"op": "unset", "to": "c", "from": "ignored", "value": False},
        ]}}
        before = deepcopy(stored)
        expected = {"mapper": {"clash": [
            {"op": "set", "to": "a", "value": None},
            {"op": "copy", "to": "b", "from": "$host.port"},
            {"op": "unset", "to": "c"},
        ]}}
        actual = normalize_stored_host_overrides(stored)
        self.assertEqual(actual, expected)
        self.assertEqual(stored, before)
        self.assertEqual(normalize_stored_host_overrides(actual), actual)
        self.assertEqual(HostOverrides.model_validate(actual).model_dump(exclude_none=True, by_alias=True), expected)

    def test_copy_sources_missing_null_order_arrays_and_flat_keys(self):
        connection = SimpleNamespace(
            address="example.com", port=8443, remark="Example",
            inbound={"protocol": "vless", "network": "tcp", "tls": "tls"},
            credentials={"id": "user-id"}, raw_inbound={"settings": {"clients": [{"id": "raw-id"}]}, "empty": None},
        )
        node = {"array": [1, 2, 3], "keep": True}
        operations = [
            {"op": "set", "to": "array[0]", "value": 0},
            {"op": "unset", "to": "array[1]"},
            {"op": "copy", "from": "$host.port", "to": "options[0].port"},
            {"op": "copy", "from": "settings.clients[0].id", "to": "options[0].id"},
            {"op": "copy", "from": "empty", "to": "nullValue"},
            {"op": "copy", "from": "missing.key", "to": "absent"},
            {"op": "unset", "to": "missing.child"},
        ]
        result = HostMapper().apply(node, operations, connection)
        self.assertEqual(result, {
            "array": [0, 3], "keep": True, "options": [{"port": 8443, "id": "raw-id"}], "nullValue": None,
        })
        self.assertEqual(node, {"array": [1, 2, 3], "keep": True})
        flat = HostMapper().apply({}, [{"op": "set", "to": "a.b[0]", "value": False}], connection, flat=True)
        self.assertEqual(flat, {"a.b[0]": False})
        with self.assertRaisesRegex(ValueError, "smaller than 1024"):
            HostMapper().apply({}, [{"op": "set", "to": "options[1024].value", "value": 1}], connection)
