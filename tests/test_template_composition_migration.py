from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.db.migrations.template_composition_v1 import convert, encode_snapshot, read_snapshot
from app.subscription.contracts import RenderInput
from app.subscription.generators import GeneratorRegistry
from app.subscription.loader import SubscriptionSnapshotLoader
from app.subscription.planning import ProfilePlanner
from app.subscription.resolver import ResolveContext
from app.utils.runtime_settings import build_default_runtime_settings


class TemplateCompositionMigrationTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="template-composition-")
        self.url = "sqlite:///" + (Path(self.directory.name) / "test.db").as_posix()
        self.engine = sa.create_engine(self.url)
        self.migrate("upgrade", "c82a6f0159bd")

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def migrate(self, action, revision, success=True, foreign_keys=True):
        script = ("import sys, sqlalchemy as sa; "
                  "sa.event.listen(sa.engine.Engine, 'connect', lambda conn, _: conn.execute('PRAGMA foreign_keys="
                  + ("ON" if foreign_keys else "OFF") + "')); "
                  "from alembic.config import main; main(argv=sys.argv[1:])")
        result = subprocess.run([sys.executable, "-c", script, action, revision],
                                env=dict(os.environ, SQLALCHEMY_DATABASE_URL=self.url, MARZBAN_CLI="1"),
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def seed(self):
        metadata = sa.MetaData()
        metadata.reflect(self.engine)
        with self.engine.begin() as connection:
            inbound = connection.execute(metadata.tables["inbounds"].insert().values(
                tag="SS", content={"tag": "SS", "protocol": "shadowsocks", "port": 443,
                                   "settings": {"clients": [], "method": "aes-256-gcm"},
                                   "streamSettings": {"network": "tcp", "security": "none"}},
                enabled=True, readonly=False)).inserted_primary_key[0]
            templates = list(connection.execute(metadata.tables["subscription_templates"].select()).mappings())
            host_ids = []
            for index in range(2):
                host_id = connection.execute(metadata.tables["hosts"].insert().values(
                    remark=f"Host {index}", address=f"host-{index}.example.com", inbound_id=inbound,
                    enabled=True, position=index, show_when_composed=True,
                    overrides={"security": {"allow_insecure": False, "alpn": []}},
                    balancer_settings={"strategy": "round_robin", "probe_url": "https://example.com/204",
                                       "probe_interval": 60, "clients": {
                                           "sing-box": {"strategy": "least_ping", "tolerance": 0,
                                                        "interrupt_existing_connections": False},
                                           "clash": {"lazy": False, "tolerance": 0}}} if index == 0 else None,
                    created_at=datetime(2024, 1, 2), updated_at=datetime(2024, 1, 2))).inserted_primary_key[0]
                host_ids.append(host_id)
                for template in templates:
                    connection.execute(metadata.tables["host_subscription_templates"].insert().values(
                        host_id=host_id, format=template["format"], template_id=template["id"]))
            connection.execute(metadata.tables["host_links"].insert().values(
                owner_host_id=host_ids[0], member_host_id=host_ids[1], position=0))
        return host_ids

    def test_preserve_settings_generate_every_format_downgrade_and_reupgrade_with_foreign_keys(self):
        ids = self.seed()
        with self.engine.connect() as connection:
            original = encode_snapshot(read_snapshot(connection))
        self.migrate("upgrade", "head")
        self.assertNotIn("host_links", sa.inspect(self.engine).get_table_names())
        with Session(self.engine) as db:
            settings = build_default_runtime_settings()
            snapshot = SubscriptionSnapshotLoader().load(db, settings)
            self.assertEqual(len(snapshot.hosts), 3)
            self.assertEqual(snapshot.hosts[0].overrides, {"security": {"allow_insecure": False, "alpn": []}})
            recipient = next(host for host in snapshot.hosts if host.id not in ids)
            self.assertEqual(set(recipient.subscription_template_ids), {"v2ray-json"})
            for target in ("v2ray", "v2ray-json", "clash", "sing-box", "outline"):
                with self.subTest(target=target):
                    plans, _ = ProfilePlanner().plan(snapshot, target,
                                                     {"shadowsocks": {"password": "test-password", "method": "aes-256-gcm"}},
                                                     {"shadowsocks": ["SS"]}, ResolveContext({}))
                    result = GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults))
                    self.assertTrue(result.body)
                    if target == "v2ray-json":
                        document = next(item for item in json.loads(result.body) if item["remarks"].endswith(" · Auto"))
                        self.assertEqual(document["routing"]["balancers"][0]["strategy"]["type"], "roundRobin")
                        self.assertEqual(len([item for item in document["outbounds"]
                                         if item["tag"].startswith("mb-auto-")]), 2)
                    if target == "sing-box":
                        group = next(node for node in json.loads(result.body)[
                                     "outbounds"] if node["tag"] == "Host 0 · Auto")
                        self.assertEqual(group["tolerance"], 0)
                        self.assertFalse(group["interrupt_exist_connections"])
        self.migrate("downgrade", "c82a6f0159bd")
        with self.engine.connect() as connection:
            self.assertEqual(encode_snapshot(read_snapshot(connection)), original)
            self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_key_check").all(), [])
        self.migrate("upgrade", "head", foreign_keys=False)

    def test_conflicting_observatory_fails_before_ddl(self):
        self.seed()
        with self.engine.begin() as connection:
            hosts = sa.Table("hosts", sa.MetaData(), autoload_with=connection)
            connection.execute(hosts.update().where(hosts.c.id == 1).values(balancer_settings={
                "strategy": "least_ping", "probe_url": "https://example.com", "probe_interval": 30}))
            templates = sa.Table("subscription_templates", sa.MetaData(), autoload_with=connection)
            connection.execute(templates.update().where(templates.c.format == "v2ray-json").values(
                content='{"outbounds": [], "observatory": {"probeUrl": "https://other.example.com"}}'))
        result = self.migrate("upgrade", "head", success=False)
        self.assertIn("cannot be migrated safely", result.stderr)
        self.assertNotIn("host_composition_archive", sa.inspect(self.engine).get_table_names())
        self.assertIn("host_links", sa.inspect(self.engine).get_table_names())

    def test_downgrade_refuses_to_overwrite_new_settings(self):
        self.seed()
        self.migrate("upgrade", "head")
        with self.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE hosts SET remark='Edited' WHERE id=1")
        result = self.migrate("downgrade", "c82a6f0159bd", success=False)
        self.assertIn("changed after upgrading", result.stderr)
        self.assertIn("host_composition_archive", sa.inspect(self.engine).get_table_names())

    def test_least_load_costs_and_disabled_owner_groups_are_preserved(self):
        ids = self.seed()
        with self.engine.begin() as connection:
            hosts = sa.Table("hosts", sa.MetaData(), autoload_with=connection)
            settings = connection.execute(sa.select(hosts.c.balancer_settings).where(hosts.c.id == ids[0])).scalar()
            settings["clients"]["v2ray-json"] = {
                "strategy": "least_load", "enable_concurrency": False,
                "strategy_settings": {"expected": 2, "max_rtt_ms": 500, "failure_tolerance": 0,
                                      "baselines_ms": [100, 200], "costs": [{"host_id": ids[0], "value": 2}]}}
            connection.execute(hosts.update().where(hosts.c.id == ids[0]).values(balancer_settings=settings))
        self.migrate("upgrade", "head")
        with Session(self.engine) as db:
            settings = build_default_runtime_settings()
            snapshot = SubscriptionSnapshotLoader().load(db, settings)
            proxies = {"shadowsocks": {"password": "password", "method": "aes-256-gcm"}}
            plans, _ = ProfilePlanner().plan(snapshot, "v2ray-json", proxies,
                                             {"shadowsocks": ["SS"]}, ResolveContext({}))
            result = GeneratorRegistry().for_target("v2ray-json").generate(RenderInput("v2ray-json", plans, snapshot.defaults))
            document = next(item for item in json.loads(result.body) if item["remarks"].endswith(" · Auto"))
            strategy = document["routing"]["balancers"][0]["strategy"]
            self.assertEqual(strategy["type"], "leastLoad")
            self.assertEqual(strategy["settings"]["tolerance"], 0)
            self.assertEqual(strategy["settings"]["maxRTT"], "500ms")
            self.assertEqual(strategy["settings"]["costs"][0]["match"], f"mb-auto-{ids[0]}-host-{ids[0]}")
            self.assertFalse(document["observatory"]["enableConcurrency"])
            from app.db.models.proxies import ProxyHost

            owner = db.get(ProxyHost, ids[0])
            owner.enabled = False
            db.commit()
            snapshot = SubscriptionSnapshotLoader().load(db, settings)
            for target in ("sing-box", "clash"):
                plans, _ = ProfilePlanner().plan(snapshot, target, proxies, {"shadowsocks": ["SS"]}, ResolveContext({}))
                result = GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults))
                self.assertNotIn("Host 0 · Auto", result.body)

    def test_mysql_and_mariadb_runtime_schema_compiles(self):
        from app.db.base import Base

        for name in ("hosts", "subscription_templates", "host_subscription_templates"):
            for dialect in (mysql.dialect(), MariaDBDialect()):
                self.assertIn("CREATE TABLE", str(CreateTable(Base.metadata.tables[name]).compile(dialect=dialect)))
