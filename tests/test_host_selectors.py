import json
from pathlib import Path
from unittest import TestCase

from fastapi import HTTPException
from pydantic import ValidationError
import yaml

from app.db.crud import proxy_hosts
from app.models.host import HostCreate
from app.models.subscription_template import SubscriptionTemplateModify
from app.services.subscription_template_service import get_capabilities, update_template
from app.subscription.contracts import ResolvedConnection, SubscriptionError
from app.subscription.host_selectors import Selector, select_by_name
from app.subscription.template_directives import Selection, selected_sources

import test_template_composition as fixtures


class SelectorContractTests(TestCase):
    def test_invalid_selectors_are_rejected(self):
        invalid = [
            {"type": "remarks"}, {"type": "remarks", "values": []},
            {"type": "remarks", "values": [1]}, {"type": "remarks", "values": [""]},
            {"type": "remarkPrefix"}, {"type": "remarkPrefix", "prefix": ""},
            {"type": "remarkPrefix", "prefix": None}, {"type": "remarkPrefix", "prefix": "a" * 257},
            {"type": "remarkPrefix", "prefix": "EU", "values": []},
            {"type": "remarkRegex"}, {"type": "remarkRegex", "pattern": ""},
            {"type": "remarkRegex", "pattern": "["}, {"type": "remarkRegex", "pattern": 1},
            {"type": "remarkRegex", "pattern": "a" * 1025},
            {"type": "remarkRegex", "pattern": "EU", "prefix": None},
            {"type": "ids", "values": [True]}, {"type": "ids", "values": ["1"]},
            {"type": "ids", "values": [0]}, {"type": "groups", "values": [1]},
            {"type": "sameGroupsAsRecipient", "values": ["eu"]},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                Selector.model_validate(value)

    def test_expensive_regex_is_interrupted(self):
        source = ResolvedConnection(1, "a" * 250 + "!", "example.com", 443, {}, {}, {})
        selector = Selector(type="remarkRegex", pattern="(a|aa)+$")
        with self.assertRaisesRegex(SubscriptionError, "time limit"):
            select_by_name((source,), selector)

    def test_editor_fixture_matches_backend_capabilities(self):
        fixture = Path(__file__).resolve().parents[1] / (
            "app/dashboard/tests/fixtures/template-directives-schema.json")
        self.assertEqual(json.loads(fixture.read_text(encoding="utf-8")), get_capabilities(admin=object()))


class NameSelectionTests(TestCase):
    setUp = fixtures.TemplateCompositionTests.setUp
    tearDown = fixtures.TemplateCompositionTests.tearDown
    template = fixtures.TemplateCompositionTests.template
    plan = fixtures.TemplateCompositionTests.plan
    generate = fixtures.TemplateCompositionTests.generate

    def host(self, name, **options):
        return proxy_hosts.create_host(self.db, HostCreate(
            inbound_id=self.inbound.id, remark=name,
            address=name.replace("{USERNAME}", "test").lower() + ".example.com", **options))

    def test_names_are_resolved_and_matching_preserves_catalog_order(self):
        owner = self.host("Auto")
        first = self.host("EU-{USERNAME}", is_hidden=True)
        second = self.host("EU-test", is_hidden=True)
        literal = self.host("EU.+-test", is_hidden=True)
        self.host("eu-test", is_hidden=True)
        self.host("Other", is_hidden=True)
        self.host("EU-disabled", enabled=False)
        self.host("EU-no-format", subscription_template_ids={})
        profile = self.plan(root_ids={owner.id})[1][0]
        cases = [
            ({"type": "remarks", "values": ["EU.+-test", "EU-test"]}, [first.id, second.id, literal.id]),
            ({"type": "remarks", "values": ["EU-{USERNAME}"]}, []),
            ({"type": "remarkPrefix", "prefix": "EU"}, [first.id, second.id, literal.id]),
            ({"type": "remarkPrefix", "prefix": "EU.+"}, [literal.id]),
            ({"type": "remarkRegex", "pattern": "^EU-test$"}, [first.id, second.id]),
            ({"type": "remarkRegex", "pattern": "test$"},
             [item.host_id for item in profile.sources if item.remark.endswith("test")]),
            ({"type": "remarkRegex", "pattern": "missing"}, []),
        ]
        for selector, expected in cases:
            with self.subTest(selector=selector):
                options = Selection(selector=selector, selectFrom="ALL")
                self.assertEqual([item.host_id for item in selected_sources(profile, options)], expected)

    def test_visibility_permissions_and_xray_recipient_rules_are_preserved(self):
        owner = self.host("EU-Auto")
        visible = self.host("EU-Visible")
        hidden = self.host("EU-Hidden", is_hidden=True)
        profile = self.plan(root_ids={owner.id})[1][0]
        for mode, expected in (("ALL", [visible.id, hidden.id]), ("VISIBLE", [visible.id]), ("HIDDEN", [hidden.id])):
            options = Selection(selector={"type": "remarkPrefix", "prefix": "EU-"}, selectFrom=mode)
            self.assertEqual([item.host_id for item in selected_sources(profile, options, recipient=profile.owner)],
                             expected)
        # The selector can only inspect resolved, authorized sources, even when the host catalog contains more.
        from dataclasses import replace

        restricted = replace(profile, sources=tuple(item for item in profile.sources if item.host_id == hidden.id))
        options = Selection(selector={"type": "remarkRegex", "pattern": "EU-"}, selectFrom="ALL")
        self.assertEqual([item.host_id for item in selected_sources(restricted, options)], [hidden.id])

    def test_all_name_selectors_generate_real_compositions_in_each_format(self):
        owner = self.host("Auto")
        self.host("EU-{USERNAME}", is_hidden=True)
        self.host("EU-Backup", is_hidden=True)
        self.host("US-Other", is_hidden=True)
        selectors = [
            {"type": "remarks", "values": ["EU-Backup", "EU-test"]},
            {"type": "remarkPrefix", "prefix": "EU-"},
            {"type": "remarkRegex", "pattern": "^EU-"},
        ]
        for selector in selectors:
            with self.subTest(selector=selector):
                self.template(owner, "v2ray-json", {"outbounds": [], "marzban": {
                    "addVirtualHostAsOutbound": False,
                    "injectHosts": [{"tagPrefix": "eu", "selectFrom": "ALL", "selector": selector}]}})
                xray = json.loads(self.generate())[0]
                self.assertEqual([item["tag"] for item in xray["outbounds"]], ["eu", "eu-2"])
                self.assertEqual([item["settings"]["servers"][0]["address"] for item in xray["outbounds"]],
                                 ["eu-test.example.com", "eu-backup.example.com"])
                self.template(owner, "clash", {"proxies": [], "proxy-groups": [
                    {"name": "Best", "type": "url-test", "proxies": [], "url": "https://example.com", "interval": 30,
                     "marzban": {"include-proxies": True, "selectFrom": "ALL", "selector": selector}}]})
                clash = yaml.safe_load(self.generate("clash"))
                self.assertEqual(clash["proxy-groups"][0]["proxies"], ["EU-test", "EU-Backup"])
                self.template(owner, "sing-box", {"outbounds": [
                    {"tag": "Best", "type": "urltest", "outbounds": [],
                     "marzban": {"includeProxies": True, "selectFrom": "ALL", "selector": selector}}]})
                singbox = json.loads(self.generate("sing-box"))
                best = next(item for item in singbox["outbounds"] if item["tag"] == "Best")
                self.assertEqual(best["outbounds"], ["EU-test", "EU-Backup"])
                for document in (xray, clash, singbox):
                    self.assertNotIn('"marzban":', json.dumps(document))

    def test_invalid_regex_cannot_replace_a_saved_template(self):
        owner = self.host("Auto")
        saved = self.template(owner, "v2ray-json", {"outbounds": []})
        content = saved.content
        payload = SubscriptionTemplateModify(content=json.dumps({"outbounds": [], "marzban": {
            "injectHosts": [{"tagPrefix": "pool", "selector": {"type": "remarkRegex", "pattern": "["}}]}}))
        with self.assertRaises(HTTPException) as caught:
            update_template(saved.id, payload, self.db, object())
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("regular expression", caught.exception.detail)
        self.db.refresh(saved)
        self.assertEqual(saved.content, content)
