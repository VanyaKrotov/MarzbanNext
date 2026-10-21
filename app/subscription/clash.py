import copy
import json
from random import choice
from uuid import UUID

import yaml
from jinja2.exceptions import TemplateNotFound

from app.subscription.funcs import get_grpc_gun
from app.templates import render_template_content
from app.utils.helpers import yml_uuid_representer
from app.models.subscription_template import SubscriptionFormat
from app.utils.subscription_templates import parse_subscription_document, render_subscription_template


class ClashConfiguration(object):
    def __init__(self, template: str | None = None, defaults: dict | None = None):
        from app.utils.runtime_settings import build_default_generator_templates

        defaults = defaults if defaults is not None else build_default_generator_templates()

        from app.utils.subscription_template_defaults import default_subscription_content

        self.template = template if template is not None else default_subscription_content("clash")
        self.data = {
            'proxies': [],
            'proxy-groups': [],
            # Some clients rely on "rules" option and will fail without it.
            'rules': []
        }
        self.proxy_remarks = []
        self.default_proxy_remarks = []
        self.mux_template = render_template_content(defaults["mux"])
        user_agent_data = json.loads(render_template_content(defaults["user_agent"]))

        if 'list' in user_agent_data and isinstance(user_agent_data['list'], list):
            self.user_agent_list = user_agent_data['list']
        else:
            self.user_agent_list = []

        try:
            self.settings = yaml.load(
                render_template_content(defaults["clash_settings"]),
                Loader=yaml.SafeLoader,
            )
        except TemplateNotFound:
            self.settings = {}

        del user_agent_data

    def render(self, reverse=False):
        if reverse:
            self.data['proxies'].reverse()

        yaml.add_representer(UUID, yml_uuid_representer)
        return yaml.dump(
            parse_subscription_document(
                SubscriptionFormat.clash,
                render_subscription_template(
                    self.template,
                    {"conf": self.data, "proxy_remarks": self.default_proxy_remarks}
                ),
            ),
            sort_keys=False,
            allow_unicode=True,
        )

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return self.render()

    def _remark_validation(self, remark):
        if not remark in self.proxy_remarks:
            return remark
        c = 2
        while True:
            new = f'{remark} ({c})'
            if not new in self.proxy_remarks:
                return new
            c += 1

    def http_config(
            self,
            path="",
            host="",
            random_user_agent: bool = False,
    ):
        config = copy.deepcopy(self.settings.get("http-opts", {
            'headers': {}
        }))

        if path:
            config["path"] = [path]
        if host:
            config["Host"] = host
        if random_user_agent:
            if "headers" not in config:
                config["headers"] = {}
            config["header"]["User-Agent"] = choice(self.user_agent_list)

        return config

    def ws_config(
            self,
            path="",
            host="",
            max_early_data=None,
            early_data_header_name="",
            is_httpupgrade: bool = False,
            random_user_agent: bool = False,
    ):
        config = copy.deepcopy(self.settings.get("ws-opts", {}))
        if (host or random_user_agent) and "headers" not in config:
            config["headers"] = {}
        if path:
            config["path"] = path
        if host:
            config["headers"]["Host"] = host
        if random_user_agent:
            config["headers"]["User-Agent"] = choice(self.user_agent_list)
        if max_early_data and not is_httpupgrade:
            config["max-early-data"] = max_early_data
            config["early-data-header-name"] = early_data_header_name
        if is_httpupgrade:
            config["v2ray-http-upgrade"] = True
            config["v2ray-http-upgrade-fast-open"] = True

        return config

    def grpc_config(self, path=""):
        config = copy.deepcopy(self.settings.get("grpc-opts", {}))
        if path:
            config["grpc-service-name"] = path

        return config

    def h2_config(self, path="", host=""):
        config = copy.deepcopy(self.settings.get("h2-opts", {}))
        if path:
            config["path"] = path
        if host:
            config["host"] = [host]

        return config

    def tcp_config(self, path="", host=""):
        config = copy.deepcopy(self.settings.get("tcp-opts", {}))
        if path:
            config["path"] = [path]
        if host:
            if "headers" not in config:
                config["headers"] = {}
            config["headers"]["Host"] = host

        return config

    def make_node(self,
                  name: str,
                  remark: str,
                  type: str,
                  server: str,
                  port: int,
                  network: str,
                  tls: bool,
                  sni: str,
                  host: str,
                  path: str,
                  headers: str = '',
                  udp: bool = True,
                  alpn: str = '',
                  ais: bool = '',
                  mux_enable: bool = False,
                  random_user_agent: bool = False):

        if network in ["grpc", "gun"]:
            path = get_grpc_gun(path)

        if type == 'shadowsocks':
            type = 'ss'
        if network in ("http", "h2", "h3"):
            network = "h2"
        if network in ('tcp', 'raw') and headers == 'http':
            network = 'http'
        if network == 'httpupgrade':
            network = 'ws'
            is_httpupgrade = True
        else:
            is_httpupgrade = False
        node = {
            'name': remark,
            'type': type,
            'server': server,
            'port': port,
            'network': network,
            'udp': udp
        }

        if "?ed=" in path:
            path, max_early_data = path.split("?ed=")
            max_early_data, = max_early_data.split("/")
            max_early_data = int(max_early_data)
            early_data_header_name = "Sec-WebSocket-Protocol"
        else:
            max_early_data = None
            early_data_header_name = ""

        if type == 'ss':
            return node

        if tls:
            node['tls'] = True
            if type == 'trojan':
                node['sni'] = sni
            else:
                node['servername'] = sni
            if alpn:
                node['alpn'] = alpn.split(',')
            if ais:
                node['skip-cert-verify'] = ais

        if network == 'http':
            net_opts = self.http_config(
                path=path,
                host=host,
                random_user_agent=random_user_agent,
            )

        elif network == 'ws':
            net_opts = self.ws_config(
                path=path,
                host=host,
                max_early_data=max_early_data,
                early_data_header_name=early_data_header_name,
                is_httpupgrade=is_httpupgrade,
                random_user_agent=random_user_agent,
            )

        elif network == 'grpc' or network == 'gun':
            net_opts = self.grpc_config(path=path)

        elif network == 'h2':
            net_opts = self.h2_config(path=path, host=host)

        elif network in ('tcp', 'raw'):
            net_opts = self.tcp_config(path=path, host=host)

        else:
            net_opts = {}

        node[f'{network}-opts'] = net_opts

        mux_json = json.loads(self.mux_template)
        mux_config = mux_json["clash"]

        if mux_enable:
            node['smux'] = mux_config

        return node

    def add(
        self,
        remark: str,
        address: str,
        inbound: dict,
        settings: dict,
        include_in_default: bool = True,
    ):
        # not supported by clash
        if inbound['network'] in ("kcp", "splithttp", "xhttp"):
            return None

        proxy_remark = self._remark_validation(remark)

        node = self.make_node(
            name=remark,
            remark=proxy_remark,
            type=inbound['protocol'],
            server=address,
            port=inbound['port'],
            network=inbound['network'],
            tls=(inbound['tls'] == 'tls'),
            sni=inbound['sni'],
            host=inbound['host'],
            path=inbound['path'],
            headers=inbound['header_type'],
            udp=True,
            alpn=inbound.get('alpn', ''),
            ais=inbound.get('ais', False),
            mux_enable=inbound.get('mux_enable', False),
            random_user_agent=inbound.get("random_user_agent")
        )

        if inbound['protocol'] == 'vmess':
            node['uuid'] = settings['id']
            node['alterId'] = 0
            node['cipher'] = 'auto'

        elif inbound['protocol'] == 'trojan':
            node['password'] = settings['password']

        elif inbound['protocol'] == 'shadowsocks':
            node['password'] = settings['password']
            node['cipher'] = settings['method']

        else:
            return None

        self.data['proxies'].append(node)
        self.proxy_remarks.append(proxy_remark)
        if include_in_default:
            self.default_proxy_remarks.append(proxy_remark)
        return proxy_remark

    def add_balancer(
        self,
        name: str,
        endpoint_tags: list[str],
        probe_url: str,
        probe_interval: int,
        strategy: str,
    ) -> None:
        group = {
            "name": name,
            "proxies": endpoint_tags,
            "url": probe_url,
            "interval": probe_interval,
        }
        if strategy == "round_robin":
            group.update({"type": "load-balance", "strategy": "round-robin"})
        else:
            group["type"] = "url-test"
        self.data["proxy-groups"].append(group)


class ClashMetaConfiguration(ClashConfiguration):
    def make_node(self,
                  name: str,
                  remark: str,
                  type: str,
                  server: str,
                  port: int,
                  network: str,
                  tls: bool,
                  sni: str,
                  host: str,
                  path: str,
                  headers: str = '',
                  udp: bool = True,
                  alpn: str = '',
                  fp: str = '',
                  pbk: str = '',
                  sid: str = '',
                  ais: bool = '',
                  mux_enable: bool = False,
                  random_user_agent: bool = False):
        node = super().make_node(
            name=name,
            remark=remark,
            type=type,
            server=server,
            port=port,
            network=network,
            tls=tls,
            sni=sni,
            host=host,
            path=path,
            headers=headers,
            udp=udp,
            alpn=alpn,
            ais=ais,
            mux_enable=mux_enable,
            random_user_agent=random_user_agent
        )
        if fp:
            node['client-fingerprint'] = fp
        if pbk:
            node['reality-opts'] = {"public-key": pbk, "short-id": sid}

        return node

    def add(
        self,
        remark: str,
        address: str,
        inbound: dict,
        settings: dict,
        include_in_default: bool = True,
    ):
        # not supported by clash-meta
        if inbound['network'] in ("kcp", "splithttp", "xhttp") or (inbound['network'] == "quic" and inbound["header_type"] != "none"):
            return None

        proxy_remark = self._remark_validation(remark)

        if inbound["protocol"] == "hysteria":
            node = {
                "name": proxy_remark,
                "type": "hysteria2",
                "server": address,
                "port": inbound["port"],
                "password": settings["auth"],
                "udp": True,
            }
            if inbound.get("sni"):
                node["sni"] = inbound["sni"]
            if inbound.get("alpn"):
                node["alpn"] = inbound["alpn"].split(",")
            if inbound.get("ais"):
                node["skip-cert-verify"] = inbound["ais"]
            self.data["proxies"].append(node)
            self.proxy_remarks.append(proxy_remark)
            if include_in_default:
                self.default_proxy_remarks.append(proxy_remark)
            return proxy_remark

        node = self.make_node(
            name=remark,
            remark=proxy_remark,
            type=inbound['protocol'],
            server=address,
            port=inbound['port'],
            network=inbound['network'],
            tls=(inbound['tls'] in ('tls', 'reality')),
            sni=inbound['sni'],
            host=inbound['host'],
            path=inbound['path'],
            headers=inbound['header_type'],
            udp=True,
            alpn=inbound.get('alpn', ''),
            fp=inbound.get('fp', ''),
            pbk=inbound.get('pbk', ''),
            sid=inbound.get('sid', ''),
            ais=inbound.get('ais', False),
            mux_enable=inbound.get('mux_enable', False),
            random_user_agent=inbound.get("random_user_agent")
        )

        if inbound['protocol'] == 'vmess':
            node['uuid'] = settings['id']
            node['alterId'] = 0
            node['cipher'] = 'auto'

        elif inbound['protocol'] == 'vless':
            node['uuid'] = settings['id']

            if inbound['network'] in ('tcp', 'raw', 'kcp') and inbound['header_type'] != 'http' and inbound['tls'] != 'none':
                node['flow'] = settings.get('flow', '')

        elif inbound['protocol'] == 'trojan':
            node['password'] = settings['password']

        elif inbound['protocol'] == 'shadowsocks':
            node['password'] = settings['password']
            node['cipher'] = settings['method']

        else:
            return None

        self.data['proxies'].append(node)
        self.proxy_remarks.append(proxy_remark)
        if include_in_default:
            self.default_proxy_remarks.append(proxy_remark)
        return proxy_remark
