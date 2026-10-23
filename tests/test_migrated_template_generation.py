"""Exercise real migrated rows through the same loader, planner and generators as subscriptions."""

import base64
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest import TestCase

import sqlalchemy as sa
from sqlalchemy.orm import Session
import yaml
from fastapi import HTTPException

from app.db.models.subscription_templates import SubscriptionTemplate
from app.models.subscription_template import SubscriptionFormat, SubscriptionTemplateClone, SubscriptionTemplateModify
from app.services.subscription_template_service import clone_template, update_template
from app.subscription.contracts import RenderInput
from app.subscription.generators import GeneratorRegistry
from app.subscription.loader import SubscriptionSnapshotLoader
from app.subscription.planning import ProfilePlanner
from app.subscription.resolver import ResolveContext
from app.utils.runtime_settings import build_default_runtime_settings
from app.utils.subscription_templates import TemplateValidationError, render_template_document

import test_host_redesign_migration as fixtures


USER_BLOCK = "{% set label %}Saved{% endset %}\n"
SOURCES = {
    "v2ray": USER_BLOCK + "{{ links | join('\\n') }}",
    "outline": USER_BLOCK + "{{ config | tojson }}",
    "v2ray-json": USER_BLOCK + '''{
      "outbounds": [{"protocol": "freedom", "tag": "direct"}],
      "routing": {"rules": [{"type": "field", "network": "tcp,udp", "outboundTag": "proxy"}]},
      "note": {{ label | tojson }}, "address": {{ host.address | tojson }}
    }''',
    "clash": USER_BLOCK + '''{{ conf | except("proxy-groups") | yaml }}
{% if proxy_remarks %}
proxy-groups:
  - name: {{ label | tojson }}
    type: select
    proxies: {{ (["DIRECT"] + proxy_remarks) | tojson }}
{% for name in ["Static 1", "Static 2"] %}
  - name: {{ name | tojson }}
    type: select
    proxies: ["DIRECT"]
{% endfor %}
{% else %}
proxy-groups: []
{% endif %}
''',
    "sing-box": USER_BLOCK + '''{
      "note": {{ label | tojson }},
      "outbounds": [{"tag": "direct", "type": "direct"},
                    {"tag": "choice", "type": "selector", "outbounds": null}],
      "route": {"final": "choice"}
    }''',
}


class MigratedDocumentTests(TestCase):
    def test_postprocessing_preserves_jinja_literals_and_does_not_mutate_settings(self):
        source = '{"outbounds": [], "note": {{ "{{ literal }}" | tojson }}}'
        settings = {"version": 1, "overlay": {"route": {"final": "direct"}}}
        before = deepcopy(settings)
        document = render_template_document(SubscriptionFormat.sing_box, source, {}, settings)
        self.assertEqual(document["note"], "{{ literal }}")
        self.assertEqual(document["route"], {"final": "direct"})
        self.assertEqual(settings, before)

    def test_invalid_balancer_name_is_a_validation_error(self):
        settings = {"version": 1, "aggregate": [{"member_ids": [1], "enabled": True,
                    "node": {"name": "{USERNAME.invalid}", "type": "select", "proxies": []}}]}
        with self.assertRaises(TemplateValidationError):
            render_template_document(SubscriptionFormat.clash, '{"proxies": []}',
                                     {"host_ids": [1], "proxy_remarks": [], "USERNAME": "test"}, settings)


class MigratedTemplateGenerationTests(TestCase):
    setUp = fixtures.HostRedesignMigrationTests.setUp
    tearDown = fixtures.HostRedesignMigrationTests.tearDown
    migrate = fixtures.HostRedesignMigrationTests.migrate

    def seed(self):
        ids = fixtures.HostRedesignMigrationTests.seed(self)
        metadata = sa.MetaData()
        metadata.reflect(self.engine)
        with self.engine.begin() as connection:
            inbounds = metadata.tables["inbounds"]
            connection.execute(inbounds.update().where(inbounds.c.tag == "XHTTP").values(tag="TransferredSS", content={
                "tag": "TransferredSS", "protocol": "shadowsocks", "port": 443,
                "settings": {"clients": [], "method": "aes-256-gcm"}, "streamSettings": {"network": "tcp"}}))
            connection.execute(metadata.tables["hosts"].update().values(
                sc_max_buffered_posts=None, x_padding_obfs_mode=None, uplink_http_method=None))
            hosts = metadata.tables["hosts"]
            connection.execute(hosts.update().where(hosts.c.id == ids[0]).values(port=8443))
            templates = metadata.tables["subscription_templates"]
            for target, content in SOURCES.items():
                connection.execute(templates.update().where(templates.c.format == target).values(content=content))
        return ids

    def render(self, target, as_base64=False):
        with Session(self.engine) as db:
            snapshot = SubscriptionSnapshotLoader().load(db, build_default_runtime_settings())
        before = deepcopy(snapshot)
        plans, _ = ProfilePlanner().plan(
            snapshot, target, {"shadowsocks": {"password": "own-password", "method": "aes-256-gcm"}},
            {"shadowsocks": ["TransferredSS"]}, ResolveContext({"USERNAME": "test"}))
        result = GeneratorRegistry().for_target(target).generate(
            RenderInput(target, plans, snapshot.defaults, as_base64=as_base64))
        body = base64.b64decode(result.body).decode() if as_base64 else result.body
        self.assertEqual(snapshot, before)
        self.assertNotIn("{%", body)
        self.assertNotIn('"marzban"', body)
        self.assertNotIn("migration_settings", body)
        return yaml.safe_load(body) if target == "clash" else (
            body.splitlines() if target == "v2ray" else json.loads(body))

    def assert_original_sources(self):
        with Session(self.engine) as db:
            for template in db.query(SubscriptionTemplate).all():
                self.assertEqual(template.content, SOURCES[template.format])
                if template.migration_settings:
                    self.assertEqual(template.migration_settings["version"], 1)

    def test_sources_and_all_balancer_strategies_survive_real_upgrade_and_generation(self):
        ids = self.seed()
        metadata = sa.MetaData()
        metadata.reflect(self.engine)
        with self.engine.begin() as connection:
            balancers = metadata.tables["subscription_balancers"]
            original = dict(connection.execute(balancers.select()).mappings().one())
            for index, strategy in enumerate(("least_ping", "least_load", "random"), start=2):
                connection.execute(balancers.insert().values(
                    **dict(original, id=index, name=strategy, strategy=strategy, probe_interval=17)))
                connection.execute(metadata.tables["subscription_balancer_hosts"].insert(),
                                   [{"balancer_id": index, "host_id": host_id} for host_id in ids])
            connection.execute(balancers.insert().values(**dict(original, id=5, name="Disabled", enabled=False)))
            connection.execute(metadata.tables["subscription_balancer_hosts"].insert().values(
                balancer_id=5, host_id=ids[0]))
        self.migrate("upgrade", "head")
        self.assert_original_sources()
        xray = self.render("v2ray-json")
        self.assertEqual(len(xray), 6)
        by_name = {document["remarks"]: document for document in xray}
        for name, strategy in (("Automatic", "roundRobin"), ("least_ping", "leastPing"),
                               ("least_load", "leastLoad"), ("random", "random")):
            document = by_name[name]
            balancer = document["routing"]["balancers"][0]
            self.assertEqual(balancer["strategy"]["type"], strategy)
            self.assertEqual(len([node for node in document["outbounds"] if node["protocol"] == "shadowsocks"]), 2)
            servers = [node["settings"]["servers"][0] for node in document["outbounds"]
                       if node["protocol"] == "shadowsocks"]
            self.assertEqual([(server["address"], server["port"]) for server in servers],
                             [("host-0.example.com", 8443), ("host-1.example.com", 443)])
            self.assertTrue(all(server["password"] == "own-password" for server in servers))
            self.assertTrue(all(rule.get("balancerTag") == balancer["tag"]
                                for rule in document["routing"]["rules"]))
            self.assertEqual(document["note"], "Saved")
            if name in {"least_ping", "least_load"}:
                self.assertEqual(document["observatory"]["probeInterval"], "17s")
        clash = self.render("clash")
        groups = {node["name"]: node for node in clash["proxy-groups"]}
        self.assertNotIn("Disabled", groups)
        self.assertEqual(groups["Automatic"]["strategy"], "round-robin")
        self.assertEqual(groups["Automatic"]["proxies"], ["Host 0", "Host 1"])
        self.assertIn("Automatic", groups["Saved"]["proxies"])
        self.assertEqual(groups["Saved"]["proxies"].count("Host 0"), 1)
        self.assertEqual(groups["Static 1"]["proxies"], ["DIRECT"])
        self.assertEqual(groups["Static 2"]["proxies"], ["DIRECT"])
        self.assertEqual([(node["server"], node["port"]) for node in clash["proxies"]],
                         [("host-0.example.com", 8443), ("host-1.example.com", 443)])
        singbox = self.render("sing-box")
        groups = {node["tag"]: node for node in singbox["outbounds"]}
        self.assertEqual(groups["Automatic"]["outbounds"], ["Host 0", "Host 1"])
        self.assertIn("Automatic", groups["choice"]["outbounds"])
        self.assertNotIn("Disabled", groups)
        self.assertEqual([(node["server"], node["server_port"]) for node in singbox["outbounds"]
                          if node.get("server")], [("host-0.example.com", 8443), ("host-1.example.com", 443)])
        self.assertEqual(len(self.render("v2ray")), 2)
        for link, address in zip(self.render("v2ray"), ("host-0.example.com:8443", "host-1.example.com:443")):
            self.assertIn(address, link)
        self.assertEqual(self.render("v2ray", as_base64=True), self.render("v2ray"))
        self.assertEqual(self.render("outline")["password"], "own-password")
        self.migrate("downgrade", "f6a82c1d5e90")
        self.migrate("upgrade", "head")
        self.assert_original_sources()

    def test_unavailable_members_are_optional_and_disabled_balancers_are_retained(self):
        ids = self.seed()
        self.migrate("upgrade", "head")
        with self.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE hosts SET enabled=0 WHERE id=?", (ids[1],))
        xray = next(document for document in self.render("v2ray-json") if document["remarks"] == "Automatic")
        self.assertEqual(len([node for node in xray["outbounds"] if node["protocol"] == "shadowsocks"]), 1)
        clash = self.render("clash")
        self.assertEqual(clash["proxy-groups"][-1]["proxies"], ["Host 0"])
        self.assertEqual(self.render("sing-box")["outbounds"][2]["outbounds"], ["Host 0"])

    def test_migrated_source_edits_and_clones_keep_balancer_settings(self):
        self.seed()
        self.migrate("upgrade", "head")
        with self.engine.begin() as connection:
            templates = sa.Table("subscription_templates", sa.MetaData(), autoload_with=connection)
            row = connection.execute(templates.select().where(templates.c.format == "clash")).mappings().one()
            content = row["content"].replace("}Saved{", "}Edited{")
            connection.execute(templates.update().where(templates.c.id == row["id"]).values(content=content))
        self.assertEqual(self.render("clash")["proxy-groups"][0]["name"], "Edited")
        with Session(self.engine) as db:
            template = db.get(SubscriptionTemplate, row["id"])
            self.assertEqual(template.content, SOURCES["clash"].replace("}Saved{", "}Edited{"))
            cloned = clone_template(template.id, SubscriptionTemplateClone(name="Copy"), db,
                                    SimpleNamespace(username="test"))
            self.assertEqual(cloned.migration_settings, template.migration_settings)
            self.assertEqual(cloned.content, template.content)
            updated = update_template(cloned.id, SubscriptionTemplateModify(name="Renamed"), db,
                                      SimpleNamespace(username="test"))
            self.assertEqual(updated.migration_settings, template.migration_settings)
            with self.assertRaises(HTTPException) as failure:
                update_template(cloned.id, SubscriptionTemplateModify(content=json.dumps({
                    "proxies": [], "proxy-groups": [{"name": "Automatic", "type": "select", "proxies": ["DIRECT"]}]
                })), db, SimpleNamespace(username="test"))
            self.assertEqual(failure.exception.status_code, 422)
            self.assertEqual(cloned.content, template.content)
            updated = update_template(cloned.id, SubscriptionTemplateModify(
                format="outline", content="{{ config | tojson }}"), db, SimpleNamespace(username="test"))
            self.assertIsNone(updated.migration_settings)
        self.migrate("downgrade", "f6a82c1d5e90", succeeds=False)
