import base64
import json
from unittest import TestCase
from urllib.parse import parse_qs

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.crud import proxy_hosts as host_crud
from app.db.models.proxies import ProxyInbound
from app.models.host import HostCreate, HostPatch, HostResponse
from app.services import host_service
from app.subscription.share import build_subscription_hosts_by_inbound
from app.subscription.v2ray import V2rayJsonConfig, V2rayShareLink
from app.xray.config import XRayConfig


XHTTP_EXTRA = {
    "xPaddingKey": "padding",
    "xPaddingHeader": "Referer",
    "xPaddingMethod": "tokenish",
    "xPaddingPlacement": "queryInHeader",
    "scMaxBufferedPosts": 0,
    "xPaddingObfsMode": False,
    "uplinkHTTPMethod": "PUT",
}


def make_xhttp_inbound(protocol: str) -> dict:
    return {
        "tag": f"{protocol}-xhttp",
        "protocol": protocol,
        "port": 443,
        "settings": {"clients": [], "decryption": "none"},
        "streamSettings": {
            "network": "xhttp",
            "security": "none",
            "xhttpSettings": {
                "path": "/xhttp",
                "host": "example.com",
                "mode": "packet-up",
                **XHTTP_EXTRA,
            },
        },
    }


class XhttpHostTests(TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.xhttp_inbound = ProxyInbound(
            tag="XHTTP",
            content=make_xhttp_inbound("vless"),
        )
        self.tcp_inbound = ProxyInbound(
            tag="TCP",
            content={
                "tag": "TCP",
                "protocol": "vless",
                "port": 443,
                "settings": {"clients": [], "decryption": "none"},
                "streamSettings": {"network": "tcp", "security": "none"},
            },
        )
        self.db.add_all([self.xhttp_inbound, self.tcp_inbound])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def make_host(self, inbound_tag="XHTTP", **extra):
        inbound = self.xhttp_inbound if inbound_tag == "XHTTP" else self.tcp_inbound
        return HostCreate(inbound_id=inbound.id, remark="XHTTP host", address="example.com",
                          overrides={"transport": {"xhttp": {"extra": extra}}})

    def test_host_settings_round_trip_preserves_zero_false_and_method(self):
        host = host_crud.create_host(self.db, self.make_host(
            scMaxBufferedPosts=0, xPaddingObfsMode=False, uplinkHTTPMethod="put"))
        response = HostResponse.model_validate(host)
        extra = response.overrides["transport"]["xhttp"]["extra"]
        self.assertEqual(extra, {"scMaxBufferedPosts": 0, "xPaddingObfsMode": False, "uplinkHTTPMethod": "PUT"})
        snapshot = build_subscription_hosts_by_inbound([host])["XHTTP"][0]
        self.assertEqual(snapshot.overrides["transport"]["xhttp"]["extra"], extra)
        host_crud.update_host(self.db, host, HostPatch(overrides={"transport": {"xhttp": {"extra": None}}}))
        self.assertEqual(host.overrides, {"transport": {"xhttp": {}}})

    def test_xhttp_host_settings_require_xhttp_and_packet_up_for_get(self):
        with self.assertRaises(HTTPException) as context:
            host_service.create_host(self.make_host("TCP", xPaddingObfsMode=False), db=self.db, admin=None)
        self.assertEqual(context.exception.status_code, 422)
        self.assertIn("XHTTP", context.exception.detail)
        self.xhttp_inbound.content["streamSettings"]["xhttpSettings"]["mode"] = "stream-up"
        with self.assertRaises(HTTPException) as context:
            host_service.create_host(self.make_host(uplinkHTTPMethod="get"), db=self.db, admin=None)
        self.assertEqual(context.exception.status_code, 422)
        self.assertIn("GET requires packet-up", context.exception.detail)

    def test_xhttp_inbound_inherits_padding_settings_only_when_present(self):
        config = XRayConfig(
            {
                "inbounds": [make_xhttp_inbound("vless")],
                "outbounds": [{"tag": "direct", "protocol": "freedom"}],
            }
        )
        inbound = config.inbounds_by_tag["vless-xhttp"]
        for name in ("xPaddingKey", "xPaddingHeader", "xPaddingMethod", "xPaddingPlacement"):
            self.assertEqual(inbound[name], XHTTP_EXTRA[name])

        without_padding_options = make_xhttp_inbound("vmess")
        for name in ("xPaddingKey", "xPaddingHeader", "xPaddingMethod", "xPaddingPlacement"):
            del without_padding_options["streamSettings"]["xhttpSettings"][name]
        parsed = XRayConfig(
            {
                "inbounds": [without_padding_options],
                "outbounds": [{"tag": "direct", "protocol": "freedom"}],
            }
        ).inbounds_by_tag["vmess-xhttp"]
        self.assertTrue(
            all(name not in parsed for name in ("xPaddingKey", "xPaddingHeader", "xPaddingMethod", "xPaddingPlacement"))
        )

    def test_v2ray_links_include_configured_xhttp_options(self):
        for protocol, settings in (
            ("vmess", {"id": "d2719ec9-8f2d-4b70-91ad-621c6b10a13a"}),
            ("vless", {"id": "d2719ec9-8f2d-4b70-91ad-621c6b10a13a"}),
            ("trojan", {"password": "secret"}),
        ):
            inbound = {
                "protocol": protocol,
                "network": "xhttp",
                "path": "/xhttp",
                "port": 443,
                "tls": "none",
                "sni": "",
                "host": "example.com",
                "header_type": "",
                "fragment_setting": "",
                **XHTTP_EXTRA,
            }
            config = V2rayShareLink()
            config.add("XHTTP", "example.com", inbound, settings)
            link = config.links[0]

            if protocol == "vmess":
                payload = json.loads(base64.b64decode(link.removeprefix("vmess://")))
                extra = payload["extra"]
            else:
                query = link.split("?", 1)[1].split("#", 1)[0]
                extra = json.loads(parse_qs(query)["extra"][0])

            for name, value in XHTTP_EXTRA.items():
                self.assertEqual(extra[name], value)

    def test_v2ray_json_omits_unconfigured_xhttp_options(self):
        config = object.__new__(V2rayJsonConfig)
        config.settings = {}
        config.user_agent_list = []

        without_options = config.splithttp_config()
        self.assertTrue(all(name not in without_options for name in XHTTP_EXTRA))

        with_options = config.splithttp_config(xhttp_extra=XHTTP_EXTRA)
        for name, value in XHTTP_EXTRA.items():
            self.assertEqual(with_options["extra"][name], value)
