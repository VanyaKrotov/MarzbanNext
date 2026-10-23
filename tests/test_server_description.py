"""Client-only server descriptions survive storage and follow each supported wire format."""

import base64
from contextlib import nullcontext
import json
from unittest import TestCase
from unittest.mock import patch

import yaml
from fastapi import HTTPException

from app.db.crud import proxy_hosts
from app.models.host import HostPatch
from app.subscription.share import generate_subscription_config

import test_client_config_generation as configurations
import test_unified_hosts as fixtures


class ServerDescriptionTests(TestCase):
    setUp = fixtures.UnifiedHostTests.setUp
    tearDown = fixtures.UnifiedHostTests.tearDown
    host = fixtures.UnifiedHostTests.host
    assign = configurations.ClientConfigurationTests.assign

    def render(self, target, agent="Happ/2.0", **options):
        with patch('app.db.GetDB', return_value=nullcontext(self.db)), patch(
                'app.utils.runtime_settings.get_runtime_settings', return_value=self.settings):
            return generate_subscription_config(
                configurations.CREDENTIALS, {self.inbound.content['protocol']: [self.inbound.tag]},
                {'username': 'test', 'used_traffic': 0}, target, user_agent=agent, **options)

    def test_known_clients_receive_descriptions_and_other_clients_do_not(self):
        self.host('Example', overrides={'clients': {'server_description': 'Европа 🌍'}})
        supported = ('FlClashX/1', 'FlClash X/1', 'Flowvy/1', 'prizrak-box/1', 'koala-clash/1', 'Happ/2', 'INCY/1')
        unsupported = ('', 'Clash/1', 'FlClash/1', 'Mihomo/1', 'v2rayNG/1.9.0', 'Streisand/1',
                       'Happ', 'prefix-Happ/2', 'happ/2')
        for agent in (*supported, *unsupported):
            expected = agent in supported
            for target in ('v2ray-json', 'clash', 'v2ray'):
                with self.subTest(agent=agent, target=target):
                    output = self.render(target, agent)
                    self.assertEqual('serverDescription' in output, expected)

    def test_xray_description_is_profile_metadata_and_preserves_template_metadata(self):
        host = self.host('Example', overrides={'clients': {'server_description': 'Европа 🌍'}})
        self.assign(host, 'v2ray-json', {'outbounds': [], 'meta': {'custom': 'retained'}})
        output = json.loads(self.render('v2ray-json'))[0]
        self.assertEqual(output['meta'], {'custom': 'retained', 'serverDescription': 'Европа 🌍'})
        self.assertNotIn('meta', output['outbounds'][0])

    def test_composite_xray_description_comes_from_the_recipient(self):
        owner = self.host('Owner', overrides={'clients': {'server_description': 'Владелец'}})
        source = self.host('Source', is_hidden=True, overrides={'clients': {'server_description': 'Источник'}})
        self.assign(owner, 'v2ray-json', {'outbounds': [], 'marzban': {
            'addVirtualHostAsOutbound': False, 'injectHosts': [{
                'tagPrefix': 'pool', 'selectFrom': 'ALL', 'selector': {'type': 'ids', 'values': [source.id]},
            }],
        }})
        output = json.loads(self.render('v2ray-json', root_ids={owner.id}))[0]
        self.assertEqual(output['meta']['serverDescription'], 'Владелец')
        self.assertNotIn('meta', output['outbounds'][0])

    def test_xray_rejects_invalid_profile_metadata_with_a_configuration_error(self):
        host = self.host('Example', overrides={'clients': {'server_description': 'Европа'}})
        self.assign(host, 'v2ray-json', {'outbounds': [], 'meta': 'invalid'})
        with self.assertRaises(HTTPException) as raised:
            self.render('v2ray-json')
        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn('meta must be an object', raised.exception.detail)

    def test_uri_suffix_is_utf8_base64_and_whole_subscription_can_be_base64_encoded(self):
        description = 'Европа 🌍?&/#'
        self.host('Example', overrides={'clients': {'server_description': description}})
        ordinary = self.render('v2ray', agent='v2rayNG/1.9.0')
        suffix = '?serverDescription=' + base64.b64encode(description.encode()).decode()
        self.assertEqual(self.render('v2ray'), ordinary + suffix)
        self.assertEqual(base64.b64decode(self.render('v2ray', as_base64=True)).decode(), ordinary + suffix)
        proxy = yaml.safe_load(self.render('clash'))['proxies'][0]
        self.assertEqual(proxy['serverDescription'], description)

    def test_uri_extension_preserves_vless_vmess_and_trojan_links_after_mapping(self):
        self.host('Example', overrides={'clients': {'server_description': 'Европа'}, 'mapper': {
            'base64': [{'op': 'set', 'to': 'custom', 'value': 'mapped'}],
        }})
        for protocol in ('vless', 'vmess', 'trojan'):
            self.inbound.content = {**self.inbound.content, 'protocol': protocol}
            self.db.commit()
            with self.subTest(protocol=protocol):
                original = self.render('v2ray', agent='ordinary-client')
                extended = self.render('v2ray')
                self.assertEqual(extended, original + '?serverDescription=0JXQstGA0L7Qv9Cw')
                if protocol == 'vmess':
                    payload = json.loads(base64.b64decode(original.removeprefix('vmess://')))
                    self.assertEqual(payload['custom'], 'mapped')
                else:
                    self.assertIn('custom=mapped', original)

    def test_missing_empty_and_removed_description_are_not_emitted_and_other_formats_are_unchanged(self):
        host = self.host('Example')
        for description in (None, ''):
            overrides = {'clients': {'server_description': description}}
            proxy_hosts.update_host(self.db, host, HostPatch(overrides=overrides))
            for target in ('v2ray', 'v2ray-json', 'clash', 'sing-box', 'outline'):
                with self.subTest(description=description, target=target):
                    self.assertNotIn('serverDescription', self.render(target))
        proxy_hosts.update_host(self.db, host, HostPatch(overrides={'clients': {'server_description': 'Европа'}}))
        for target in ('sing-box', 'outline'):
            self.assertEqual(self.render(target), self.render(target, agent='Mihomo/1'))
        self.assertEqual(host.overrides['clients']['server_description'], 'Европа')
