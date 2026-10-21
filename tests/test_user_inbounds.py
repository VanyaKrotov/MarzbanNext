import importlib
from types import SimpleNamespace
from contextlib import nullcontext
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


from app.db.base import Base
from app import xray
from app.db.models.proxies import Proxy, ProxyInbound
from app.db.models.users import User
from app.models import user as user_models
from app.models.proxy import InboundCreate
from app.models.proxy import ProxyTypes
from app.db.crud import proxy_inbounds as inbound_crud

xray_config = importlib.import_module("app.xray.config")


VLESS_INBOUNDS = [
    {"tag": "VLESS TCP", "protocol": "vless", "port": 443, "settings": {"clients": []}},
    {"tag": "VLESS WS", "protocol": "vless", "port": 8443, "settings": {"clients": []}},
]


class FakeConfig:
    inbounds_by_protocol = {ProxyTypes.VLESS: VLESS_INBOUNDS}
    inbounds_by_tag = {inbound["tag"]: inbound for inbound in VLESS_INBOUNDS}


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def join(self, *args, **kwargs):
        return self

    def outerjoin(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, rows):
        self.rows = rows

    def query(self, *args, **kwargs):
        return FakeQuery(self.rows)


class FakeGetDB:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return FakeDB(self.rows)

    def __exit__(self, exc_type, exc, traceback):
        return False


class UserInboundTests(TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_create_missing_inbounds_preserves_explicit_assignment_policy(self):
        with patch("app.utils.xray_config_registry.get_enabled_inbound_registry", return_value=FakeConfig), \
                patch("app.db.GetDB", return_value=nullcontext(self.db)):
            user = user_models.UserCreate(
                username="test_user",
                proxies={"vless": {}},
            )
            self.assertEqual(user.excluded_inbounds[ProxyTypes.VLESS], ["VLESS TCP", "VLESS WS"])

    def test_create_empty_inbounds_excludes_all_current_protocol_inbounds(self):
        with patch("app.utils.xray_config_registry.get_enabled_inbound_registry", return_value=FakeConfig), \
                patch("app.db.GetDB", return_value=nullcontext(self.db)):
            user = user_models.UserCreate(
                username="test_user",
                proxies={"vless": {}},
                inbounds={"vless": []},
            )
            self.assertEqual(
                user.excluded_inbounds[ProxyTypes.VLESS],
                ["VLESS TCP", "VLESS WS"],
            )

    def test_modify_empty_inbounds_excludes_all_current_protocol_inbounds(self):
        with patch("app.utils.xray_config_registry.get_enabled_inbound_registry", return_value=FakeConfig), \
                patch("app.db.GetDB", return_value=nullcontext(self.db)):
            user = user_models.UserModify(inbounds={"vless": []})
            self.assertIn("inbounds", user.model_fields_set)
            self.assertEqual(
                user.excluded_inbounds[ProxyTypes.VLESS],
                ["VLESS TCP", "VLESS WS"],
            )

    def test_inbound_create_auto_assign_users_defaults_to_true(self):
        inbound = InboundCreate(tag="VLESS WS", content=VLESS_INBOUNDS[1])
        manual = InboundCreate(
            tag="VLESS TCP",
            content=VLESS_INBOUNDS[0],
            auto_assign_users=False,
        )

        self.assertTrue(inbound.auto_assign_users)
        self.assertFalse(manual.auto_assign_users)

    def test_db_user_inbounds_include_new_non_excluded_inbound(self):
        dbuser = User(username="test_user")
        dbuser.proxies = [
            Proxy(
                type=ProxyTypes.VLESS,
                settings={},
                excluded_inbounds=[
                    ProxyInbound(
                        tag="VLESS TCP",
                        content=VLESS_INBOUNDS[0],
                    )
                ],
            )
        ]

        with patch("app.utils.xray_config_registry.get_enabled_inbound_registry", return_value=FakeConfig), \
                patch("app.db.GetDB", return_value=nullcontext(self.db)):
            self.assertEqual(dbuser.inbounds[ProxyTypes.VLESS], ["VLESS WS"])

    def test_ensure_protocol_inbounds_adds_missing_proxy_with_only_new_tags(self):
        old_inbound = ProxyInbound(
            tag="VLESS TCP",
            content=VLESS_INBOUNDS[0],
        )
        new_inbound = ProxyInbound(
            tag="VLESS WS",
            content=VLESS_INBOUNDS[1],
        )
        missing_proxy_user = User(username="missing_proxy")
        existing_proxy_user = User(
            username="existing_proxy",
            proxies=[
                Proxy(
                    type=ProxyTypes.VLESS,
                    settings={"id": "00000000-0000-0000-0000-000000000001"},
                )
            ],
        )
        self.db.add_all([
            old_inbound,
            new_inbound,
            missing_proxy_user,
            existing_proxy_user,
        ])
        self.db.commit()

        users = inbound_crud.ensure_protocol_inbounds_for_users(
            self.db,
            protocol="vless",
            included_tags=["VLESS WS"],
            protocol_inbound_tags=["VLESS TCP", "VLESS WS"],
        )
        self.db.commit()

        self.assertEqual([user.username for user in users], ["missing_proxy"])
        self.db.refresh(missing_proxy_user)
        self.db.refresh(existing_proxy_user)
        created_proxy = missing_proxy_user.proxies[0]
        self.assertEqual(created_proxy.type, ProxyTypes.VLESS)
        self.assertIn("id", created_proxy.settings)
        self.assertEqual(
            [inbound.tag for inbound in created_proxy.excluded_inbounds],
            ["VLESS TCP"],
        )
        self.assertEqual(len(existing_proxy_user.proxies), 1)
        self.assertEqual(existing_proxy_user.proxies[0].excluded_inbounds, [])

    def test_exclude_protocol_inbounds_adds_manual_inbound_to_existing_proxies(self):
        new_inbound = ProxyInbound(
            tag="VLESS WS",
            content=VLESS_INBOUNDS[1],
        )
        existing_proxy_user = User(
            username="existing_proxy",
            proxies=[
                Proxy(
                    type=ProxyTypes.VLESS,
                    settings={"id": "00000000-0000-0000-0000-000000000001"},
                )
            ],
        )
        missing_proxy_user = User(username="missing_proxy")
        self.db.add_all([new_inbound, existing_proxy_user, missing_proxy_user])
        self.db.commit()

        proxies = inbound_crud.exclude_protocol_inbounds_for_users(
            self.db,
            protocol="vless",
            excluded_tags=["VLESS WS"],
        )
        self.db.commit()

        self.assertEqual(len(proxies), 1)
        self.db.refresh(existing_proxy_user)
        self.db.refresh(missing_proxy_user)
        self.assertEqual(
            [inbound.tag for inbound in existing_proxy_user.proxies[0].excluded_inbounds],
            ["VLESS WS"],
        )
        self.assertEqual(missing_proxy_user.proxies, [])

    def test_include_db_users_skips_excluded_inbound(self):
        row = SimpleNamespace(
            id=1,
            username="test_user",
            type="vless",
            settings={"id": "00000000-0000-0000-0000-000000000001"},
            excluded_inbound_tags="VLESS WS",
        )
        config = xray_config.XRayConfig(
            {
                "inbounds": VLESS_INBOUNDS,
                "outbounds": [{"tag": "direct", "protocol": "freedom"}],
            }
        )

        with patch.object(xray_config, "GetDB", lambda: FakeGetDB([row])):
            included = config.include_db_users()

        tcp_clients = included.get_inbound("VLESS TCP")["settings"]["clients"]
        ws_clients = included.get_inbound("VLESS WS")["settings"]["clients"]
        self.assertEqual(tcp_clients[0]["email"], "1.test_user")
        self.assertEqual(ws_clients, [])
