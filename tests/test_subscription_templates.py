import base64
import json
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.db.base import Base
from app.db.crud import proxy_hosts as host_crud
from app.db.crud import proxy_inbounds as inbound_crud
from app.db.crud import subscription_templates as template_crud
from app.db.models.proxies import ProxyInbound
from app.db.models.subscription_templates import (
    HostSubscriptionTemplate,
    SubscriptionTemplate,
)
from app.dependencies import get_validated_sub
from app.models.admin import Admin
from app.models.proxy import (
    ProxyTypes,
    ShadowsocksSettings,
)
from app.models.subscription_template import (
    SubscriptionFormat,
    SubscriptionTemplateCreate,
    SubscriptionTemplateModify,
)
from app.models.host import HostCreate as ProxyHostCreate, HostPatch as ProxyHostModify, HostResponse as ProxyHostV2
from app.models.user import UserResponse, UserStatus
from app.routers.settings import router as settings_router
from app.routers.subscription import router as public_router
from app.routers.subscription_templates import router
from app.services import subscription_template_service as service
from app.services.subscription_service import _subscription_response
from app.subscription.share import (
    build_subscription_hosts_by_inbound,
    generate_subscription_config,
)
from app.utils.runtime_settings import build_default_runtime_settings
from app.utils.subscription_template_defaults import default_subscription_content
from app.utils.subscription_templates import (
    validate_generator_settings,
    validate_subscription_template,
)


class SubscriptionTemplateTests(TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        event.listen(self.engine, 'connect', lambda connection, _: connection.execute('PRAGMA foreign_keys=ON'))
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(ProxyInbound(tag='SS', content={
            'tag': 'SS', 'protocol': 'shadowsocks', 'port': 1080,
            'settings': {'clients': [], 'method': 'aes-256-gcm', 'network': 'tcp,udp'},
            'streamSettings': {'network': 'tcp', 'security': 'none'},
        }))
        template_crud.seed_defaults(self.db)
        self.db.commit()
        self.defaults = template_crud.get_default_bindings(self.db)
        self.admin = SimpleNamespace(username='test-admin')
        self.settings = build_default_runtime_settings()
        self.settings.external_config = ''
        self.settings_patch = patch('app.utils.runtime_settings.get_runtime_settings', return_value=self.settings)
        self.settings_patch.start()
        self.service_settings_patch = patch(
            'app.services.subscription_service.get_runtime_settings', return_value=self.settings)
        self.service_settings_patch.start()
        api = FastAPI()
        api.include_router(router)
        api.include_router(public_router)
        api.include_router(settings_router)
        api.dependency_overrides[get_db] = lambda: self.db
        api.dependency_overrides[Admin.check_sudo_admin] = lambda: self.admin
        self.client = TestClient(api)

    def subscription_user(self):
        return UserResponse.model_construct(
            username='test', status=UserStatus.active, used_traffic=0, created_at=datetime(2024, 1, 1, tzinfo=UTC),
            proxies={ProxyTypes.Shadowsocks: ShadowsocksSettings(password='password', method='aes-256-gcm')},
            inbounds={ProxyTypes.Shadowsocks: ['SS']}, links=['ss://test'], subscription_url='/test',
        )

    def tearDown(self):
        self.client.close()
        self.settings_patch.stop()
        self.service_settings_patch.stop()
        self.db.close()
        self.engine.dispose()

    def create_host(self, name='First', **kwargs):
        return host_crud.create_host(self.db, ProxyHostCreate(
            inbound_id=1, remark=name, address=f'{name.lower()}.example.com', **kwargs,
        ))

    def create_template(self, format='v2ray-json', name='custom', content=None):
        return service.create_template(SubscriptionTemplateCreate(
            name=name, format=format, content=content or default_subscription_content(format),
        ), db=self.db, admin=self.admin)

    def update_host(self, host, **kwargs):
        return host_crud.update_host(self.db, host, ProxyHostModify(
            **kwargs,
        ))

    def generate(self, format, hosts=None, **kwargs):
        with patch('app.db.GetDB', return_value=nullcontext(self.db)):
            return generate_subscription_config(
                proxies={ProxyTypes.Shadowsocks: ShadowsocksSettings(password='password', method='aes-256-gcm')},
                inbounds={ProxyTypes.Shadowsocks: ['SS']}, extra_data={'username': 'test', 'used_traffic': 0},
                config_format=format, as_base64=False, reverse=False,
                hosts_by_inbound=build_subscription_hosts_by_inbound(hosts) if hosts is not None else None,
                **kwargs,
            )

    def test_api_crud_clone_filter_and_default(self):
        response = self.client.get('/api/subscription-templates', params={'format': 'clash', 'limit': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 1)
        self.assertNotIn('content', response.json()['items'][0])
        default_id = self.defaults['clash']
        created = self.client.post(f'/api/subscription-templates/{default_id}/clone', json={'name': '  custom  '})
        self.assertEqual(created.status_code, 201, created.text)
        template = created.json()
        self.assertEqual(template['name'], 'custom')
        self.assertFalse(template['is_default'])
        self.assertEqual(template['content'], self.db.get(SubscriptionTemplate, default_id).content)
        template_id = template['id']
        response = self.client.patch(f'/api/subscription-templates/{template_id}', json={'name': 'Renamed'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Renamed')
        response = self.client.get('/api/subscription-templates', params={'search': 'NAMED', 'offset': 0})
        self.assertEqual(response.json()['total'], 1)
        self.assertEqual(self.client.get('/api/subscription-templates/99999').status_code, 404)
        response = self.client.delete(f'/api/subscription-templates/{default_id}')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail'], 'Default templates cannot be deleted')
        self.assertEqual(self.client.delete(f'/api/subscription-templates/{template_id}').status_code, 204)

    def test_rename_defaults_preserves_bindings_and_generation(self):
        host = self.create_host()
        links = self.generate('v2ray')
        for format, template_id in self.defaults.items():
            with self.subTest(format=format):
                content = self.db.get(SubscriptionTemplate, template_id).content
                response = self.client.patch(f'/api/subscription-templates/{template_id}', json={
                    'name': f'  Main {format}  ',
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['id'], template_id)
                self.assertEqual(response.json()['name'], f'Main {format}')
                self.assertTrue(response.json()['is_default'])
                self.assertEqual(response.json()['content'], content)
                self.assertTrue(self.generate(format))
        self.assertEqual(host.subscription_template_ids, self.defaults)
        self.assertEqual(self.generate('v2ray'), links)
        self.assertEqual(self.create_host('Second').subscription_template_ids, self.defaults)
        template_crud.seed_defaults(self.db)
        self.assertEqual(self.db.query(SubscriptionTemplate).count(), 5)
        self.assertEqual(template_crud.get_default_bindings(self.db), self.defaults)

    def test_default_rename_retains_validation_and_protection(self):
        template_id = self.defaults['clash']
        self.create_template('clash', name='Custom')
        response = self.client.patch(f'/api/subscription-templates/{template_id}', json={'name': 'CUSTOM'})
        self.assertEqual(response.status_code, 409)
        for name in ('', '   ', None, 'x' * 129):
            response = self.client.patch(f'/api/subscription-templates/{template_id}', json={'name': name})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.patch(f'/api/subscription-templates/{template_id}', json={
            'name': 'Renamed', 'format': 'outline',
        }).status_code, 409)
        self.assertEqual(self.client.delete(f'/api/subscription-templates/{template_id}').status_code, 409)
        self.assertEqual(self.db.get(SubscriptionTemplate, template_id).name, 'default')

    def test_api_validation_and_authorization(self):
        for content in ('not json', '[]', '{"outbounds": {}}', '{"outbounds": [1]}',
                        '{{ missing }}', '{{ now() | tojson }}', '{{ 1 / 0 }}'):
            response = self.client.post('/api/subscription-templates', json={
                'name': 'invalid', 'format': 'v2ray-json', 'content': content,
            })
            self.assertEqual(response.status_code, 422, response.text)
        response = self.client.patch(f'/api/subscription-templates/{self.defaults["clash"]}', json={'name': None})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.post('/api/subscription-templates', json={
            'name': 'DEFAULT', 'format': 'clash', 'content': default_subscription_content('clash'),
        }).status_code, 409)
        self.client.app.dependency_overrides.pop(Admin.check_sudo_admin)
        self.assertEqual(self.client.get('/api/subscription-templates').status_code, 401)

    def test_default_changes_only_affect_new_hosts(self):
        existing = self.create_host()
        custom = self.create_template()
        service.set_default_template(custom.id, self.db, self.admin)
        self.assertTrue(custom.is_default)
        self.assertEqual(len(template_crud.get_defaults(self.db)), 5)
        self.assertEqual(existing.subscription_template_ids, self.defaults)
        self.assertEqual(self.create_host('Second').subscription_template_ids['v2ray-json'], custom.id)
        inbound_crud.add_default_host(self.db, self.db.query(ProxyInbound).filter_by(tag='SS').one())
        self.assertEqual(host_crud.list_hosts(self.db, inbound_id=1).all()
                         [-1].subscription_template_ids['v2ray-json'], custom.id)

    def test_assignment_replace_omit_disable_and_copy(self):
        host = self.create_host()
        self.assertEqual(ProxyHostV2.model_validate(host).subscription_template_ids, self.defaults)
        self.update_host(host)
        self.assertEqual(host.subscription_template_ids, self.defaults)
        custom = self.create_template()
        bindings = {'v2ray-json': custom.id, 'clash': self.defaults['clash']}
        self.update_host(host, subscription_template_ids=bindings)
        self.assertEqual(host.subscription_template_ids, bindings)
        copy = self.create_host('Copy', subscription_template_ids=host.subscription_template_ids)
        self.assertEqual(copy.subscription_template_ids, bindings)
        self.update_host(host, subscription_template_ids={})
        self.assertEqual(host.subscription_template_ids, {})
        self.update_host(host)
        self.assertEqual(host.subscription_template_ids, {})
        self.assertEqual(self.create_host('Disabled', subscription_template_ids={}).subscription_template_ids, {})
        hidden = self.create_host('Hidden', enabled=False)
        self.update_host(hidden, subscription_template_ids={})
        self.assertFalse(hidden.enabled)
        self.db.delete(copy)
        self.db.commit()
        self.assertEqual(self.db.query(HostSubscriptionTemplate).filter_by(host_id=copy.id).count(), 0)

    def test_invalid_assignment_does_not_mutate_host(self):
        host = self.create_host()
        for bindings in ({'v2ray': self.defaults['clash']}, {'clash': 999999}):
            with self.assertRaises(ValueError):
                self.update_host(host, subscription_template_ids=bindings)
            self.assertEqual(host.subscription_template_ids, self.defaults)
        for bindings in ({'mux': 1}, {'clash': None}, {'clash': True}, {'clash': '1'}, {'clash': 0}, None):
            with self.assertRaises(ValidationError):
                ProxyHostCreate(inbound_id=1, remark='Invalid',
                                address='example.com', subscription_template_ids=bindings)
        for alias in ('clash-meta', 'mihomo'):
            with self.subTest(alias=alias), self.assertRaises(ValidationError):
                ProxyHostCreate(inbound_id=1, remark='Alias', address='example.com',
                                subscription_template_ids={alias: self.defaults['clash']})

    def test_assigned_templates_cannot_be_deleted_or_change_format(self):
        custom = self.create_template()
        self.create_host(subscription_template_ids={'v2ray-json': custom.id})
        with self.assertRaises(HTTPException) as error:
            service.delete_template(custom.id, self.db, self.admin)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(error.exception.detail, "Templates assigned to hosts cannot be deleted")
        with self.assertRaises(HTTPException):
            service.update_template(custom.id, SubscriptionTemplateModify(format='sing-box'), self.db, self.admin)
        self.db.delete(custom)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_delete_handles_assignment_added_after_usage_check(self):
        custom = self.create_template()
        host = self.create_host(subscription_template_ids={'v2ray-json': custom.id})
        with patch.object(template_crud, 'is_used', return_value=False):
            response = self.client.delete(f'/api/subscription-templates/{custom.id}')
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['detail'], 'Templates assigned to hosts cannot be deleted')
        self.assertIsNotNone(template_crud.get_template(self.db, custom.id))
        self.assertEqual(host.subscription_template_ids, {'v2ray-json': custom.id})

    def test_all_formats_generate_using_defaults(self):
        self.create_host()
        for format in SubscriptionFormat:
            with self.subTest(format=format):
                result = self.generate(format)
                self.assertTrue(result)
                if format == SubscriptionFormat.v2ray:
                    self.assertTrue(result.startswith('ss://'))
                elif format == SubscriptionFormat.clash:
                    self.assertEqual(yaml.safe_load(result)['proxies'][0]['server'], 'first.example.com')
                elif format == SubscriptionFormat.outline:
                    self.assertEqual(json.loads(result)['server'], 'first.example.com')
                elif format == SubscriptionFormat.v2ray_json:
                    self.assertEqual(json.loads(result)[0]['remarks'], 'First')
                else:
                    self.assertTrue(any(outbound.get('server') ==
                                    'first.example.com' for outbound in json.loads(result)['outbounds']))

    def test_disabled_formats_stay_disabled_with_explicit_template(self):
        host = self.create_host(subscription_template_ids={})
        for format in SubscriptionFormat:
            with self.subTest(format=format):
                self.assertEqual(self.generate(format), '')
                self.assertEqual(self.generate(format, template_id=self.defaults[format]), '')
        response = _subscription_response('', 'application/json', {'profile-title': 'test'})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.body, b'')
        self.assertEqual(host.subscription_template_ids, {})

    def test_http_client_detection_and_disabled_json_do_not_fall_back_to_links(self):
        self.create_host(subscription_template_ids={'v2ray': self.defaults['v2ray']})
        self.client.app.dependency_overrides[get_validated_sub] = self.subscription_user
        self.settings.use_custom_json_default = True
        with patch('app.db.GetDB', return_value=nullcontext(self.db)), patch('app.db.crud.users.update_user_sub'):
            for user_agent in ('Clash/1.0', 'Mihomo/1.0', 'HiddifyNext/1.0', 'Outline/1.0', 'v2rayN/6.40'):
                response = self.client.get(f'{public_router.prefix}/test', headers={'User-Agent': user_agent})
                self.assertEqual(response.status_code, 204, (user_agent, response.text))
                self.assertEqual(response.content, b'')
            response = self.client.get(f'{public_router.prefix}/test', headers={'User-Agent': 'unknown-client'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(base64.b64decode(response.text).startswith(b'ss://'))
            for format in ('json', 'xray-json', 'clash', 'singbox'):
                response = self.client.get(f'{public_router.prefix}/test/{format}')
                self.assertEqual(response.status_code, 204, response.text)
            for format in ('clash-meta', 'mihomo'):
                response = self.client.get(f'{public_router.prefix}/test/{format}')
                self.assertEqual(response.status_code, 422, response.text)
                response = self.client.get('/api/subscription-templates', params={'format': format})
                self.assertEqual(response.status_code, 422, response.text)

    def test_public_subscription_routes_pass_client_metadata_capabilities(self):
        self.create_host(overrides={'clients': {'server_description': 'Европа'}})
        self.client.app.dependency_overrides[get_validated_sub] = self.subscription_user
        self.settings.use_custom_json_default = True
        cases = (
            ('', 'Happ/2.0', True, True),
            ('', 'Happ/2.0.0', True, False),
            ('', 'FlClashX/1.0', True, False),
            ('', 'Clash/1.0', False, False),
            ('/v2ray-json', 'Happ/2.0', True, False),
            ('/v2ray-json', 'v2rayNG/1.9.0', False, False),
            ('/clash', 'Flowvy/1.0', True, False),
            ('/clash', 'Mihomo/1.0', False, False),
            ('/v2ray', 'Happ/2.0', True, True),
            ('/v2ray', 'unknown', False, True),
            ('/sing-box', 'Happ/2.0', False, False),
            ('/outline', 'Happ/2.0', False, False),
        )
        with patch('app.db.GetDB', return_value=nullcontext(self.db)), patch('app.db.crud.users.update_user_sub'):
            for path, agent, expected, encoded in cases:
                with self.subTest(path=path, agent=agent):
                    response = self.client.get(f'{public_router.prefix}/test{path}', headers={'User-Agent': agent})
                    self.assertEqual(response.status_code, 200, response.text)
                    body = base64.b64decode(response.text).decode() if encoded else response.text
                    self.assertEqual('serverDescription' in body, expected)

    def test_per_host_json_and_link_templates_and_live_edits(self):
        first = self.create_host()
        content = json.loads(default_subscription_content('v2ray-json'))
        content['template_marker'] = 'custom'
        custom = self.create_template(content=json.dumps(content))
        second = self.create_host('Second', subscription_template_ids={'v2ray-json': custom.id})
        result = json.loads(self.generate('v2ray-json'))
        self.assertNotIn('template_marker', result[0])
        self.assertEqual(result[1]['template_marker'], 'custom')
        content['template_marker'] = 'updated'
        service.update_template(custom.id, SubscriptionTemplateModify(content=json.dumps(content)), self.db, self.admin)
        self.assertEqual(json.loads(self.generate('v2ray-json'))[1]['template_marker'], 'updated')
        link_template = self.create_template('v2ray', content="{{ links | join('\\n') | replace('#', '#custom-') }}")
        self.update_host(second, subscription_template_ids={'v2ray': link_template.id})
        result = self.generate('v2ray')
        self.assertIn('#First', result)
        self.assertIn('#custom-Second', result)
        self.assertEqual(len(result.splitlines()), 2)
        with patch('app.db.GetDB', return_value=nullcontext(self.db)):
            encoded = generate_subscription_config(
                proxies={ProxyTypes.Shadowsocks: ShadowsocksSettings(password='password', method='aes-256-gcm')},
                inbounds={ProxyTypes.Shadowsocks: ['SS']}, extra_data={'used_traffic': 0},
                config_format='v2ray', as_base64=True, reverse=False,
            )
        self.assertEqual(base64.b64decode(encoded).decode(), result)
        self.assertEqual(len(self.generate('v2ray', hosts=[first]).splitlines()), 1)

    def test_aggregate_conflict_and_explicit_override(self):
        first = self.create_host()
        for format in ('clash', 'sing-box', 'outline'):
            with self.subTest(format=format):
                custom = self.create_template(format)
                second = self.create_host(format, subscription_template_ids={format: custom.id})
                with self.assertRaises(HTTPException) as error:
                    self.generate(format, hosts=[first, second])
                self.assertEqual(error.exception.status_code, 409)
                self.assertTrue(self.generate(format, hosts=[first, second], template_id=custom.id))
                with self.assertRaises(HTTPException) as error:
                    self.generate(format, hosts=[first, second], template_id=self.defaults['v2ray'])
                self.assertEqual(error.exception.status_code, 422)
                self.update_host(second, subscription_template_ids={})
                self.assertTrue(self.generate(format, hosts=[first, second]))

    def test_balancers_respect_disabled_host_formats(self):
        first = self.create_host()
        disabled = self.create_host('Disabled', subscription_template_ids={})
        template = self.db.get(SubscriptionTemplate, self.defaults['clash'])
        template.content = json.dumps({'proxies': [], 'proxy-groups': [{
            'type': 'url-test', 'name': 'Automatic', 'proxies': [],
            'marzban': {'include-proxies': True, 'selectFrom': 'ALL',
                        'selector': {'type': 'ids', 'values': [first.id, disabled.id]}}}]})
        self.db.commit()
        self.assertTrue(self.generate('v2ray'))
        self.assertTrue(self.generate('outline'))
        json_config = self.generate('v2ray-json')
        self.assertIn('first.example.com', json_config)
        self.assertNotIn('disabled.example.com', json_config)
        for format in ('sing-box', 'clash'):
            output = self.generate(format)
            self.assertIn('first.example.com', output)
            self.assertNotIn('disabled.example.com', output)

    def test_patch_preserves_explicit_disabled_bindings(self):
        host = self.create_host(subscription_template_ids={})
        self.update_host(host, remark='Renamed')
        self.assertEqual(host_crud.get_host(self.db, host.id).subscription_template_ids, {})

    def test_json_balancer_uses_owner_template(self):
        first = self.create_host()
        custom = self.create_template()
        second = self.create_host('Second', subscription_template_ids={'v2ray-json': custom.id})
        template = self.db.get(SubscriptionTemplate, self.defaults['v2ray-json'])
        template.content = json.dumps({'outbounds': [], 'marzban': {'injectHosts': [{
            'tagPrefix': 'member', 'selectFrom': 'ALL', 'selector': {'type': 'ids', 'values': [second.id]}}]}})
        self.db.commit()
        output = self.generate('v2ray-json')
        self.assertIn('first.example.com', output)
        self.assertIn('second.example.com', output)
        self.assertIn('member', output)
        self.assertTrue(self.generate('v2ray-json', template_id=custom.id))

    def test_template_sandbox_and_generator_validation(self):
        with self.assertRaises(ValueError):
            validate_subscription_template(SubscriptionFormat.v2ray, "{{ ''.__class__.__mro__ }}")
        for key in ('mux', 'user_agent', 'grpc_user_agent', 'clash_settings', 'singbox_settings', 'v2ray_settings'):
            validate_generator_settings(key, getattr(self.settings, key))
        with self.assertRaises(ValueError):
            validate_generator_settings('user_agent', '{"list": [null]}')

    def test_generator_settings_are_editable_separately_from_full_templates(self):
        content = '{"v2ray": {"enabled": false}, "clash": {}, "sing-box": {}}'
        response = self.client.patch('/api/settings', json={'mux': content})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['mux'], content)
        self.assertNotIn('clash_subscription', response.json())
        self.assertEqual(self.client.get('/api/settings/subscription-templates').status_code, 404)
        for payload in ({'mux': 'not JSON'}, {'mux': None}, {'user_agent': '{"list": [1]}'}, {'clash_settings': '[]'}):
            response = self.client.patch('/api/settings', json=payload)
            self.assertEqual(response.status_code, 422, response.text)
