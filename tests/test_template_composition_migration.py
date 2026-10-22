from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import mysql
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.db.migrations.template_composition_v1 import LEGACY_TABLES, encode_snapshot, read_snapshot
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
        self.migrate("upgrade", "f6a82c1d5e90")

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
                    position=index, security="inbound_default", mux_enable=False, random_user_agent=False,
                    use_sni_as_host=False, is_disabled=False)).inserted_primary_key[0]
                host_ids.append(host_id)
                for template in templates:
                    connection.execute(metadata.tables["host_subscription_templates"].insert().values(
                        host_id=host_id, format=template["format"], template_id=template["id"]))
            balancer_id = connection.execute(metadata.tables["subscription_balancers"].insert().values(
                name="Automatic", enabled=True, strategy="round_robin", probe_url="https://example.com/204",
                probe_interval=60, position=0, created_at=datetime(2024, 1, 2),
                updated_at=datetime(2024, 1, 2))).inserted_primary_key[0]
            for host_id in host_ids:
                connection.execute(metadata.tables["subscription_balancer_hosts"].insert().values(
                    balancer_id=balancer_id, host_id=host_id))
                group_id = f"group-{host_id}"
                connection.execute(metadata.tables["host_groups"].insert().values(
                    id=group_id, name=group_id, created_at=datetime(2024, 1, 2), tags=[]))
                connection.execute(metadata.tables["host_group_hosts"].insert().values(
                    host_id=host_id, group_id=group_id))
        return host_ids

    def test_preserve_settings_generate_every_format_downgrade_and_reupgrade_with_foreign_keys(self):
        ids = self.seed()
        original_schema = self.schema()
        with self.engine.connect() as connection:
            original = encode_snapshot(read_snapshot(connection, LEGACY_TABLES))
        self.migrate("upgrade", "head")
        self.assertNotIn("host_links", sa.inspect(self.engine).get_table_names())
        with Session(self.engine) as db:
            settings = build_default_runtime_settings()
            snapshot = SubscriptionSnapshotLoader().load(db, settings)
            self.assertEqual(len(snapshot.hosts), 3)
            self.assertEqual(snapshot.hosts[0].overrides, {})
            recipient = next(host for host in snapshot.hosts if host.id not in ids)
            self.assertEqual(set(recipient.subscription_template_ids), {"v2ray-json"})
            group_bindings = sa.Table("host_group_hosts", sa.MetaData(), autoload_with=self.engine)
            self.assertEqual(set(db.execute(sa.select(group_bindings.c.group_id).where(
                group_bindings.c.host_id == recipient.id)).scalars()), {f"group-{host_id}" for host_id in ids})
            templates = sa.Table("subscription_templates", sa.MetaData(), autoload_with=self.engine)
            current = {row["id"]: row for row in db.execute(templates.select()).mappings()}
            for template in original["subscription_templates"]:
                migrated = current[template["id"]]
                self.assertIn(template["content"], migrated["content"])
                self.assertEqual(migrated["format"], template["format"])
                self.assertEqual(migrated["name"], template["name"])
                self.assertEqual(migrated["default_marker"], template["default_marker"])
                self.assertEqual(migrated["updated_at"].isoformat(), template["updated_at"])
            for target in ("v2ray", "v2ray-json", "clash", "sing-box", "outline"):
                with self.subTest(target=target):
                    plans, _ = ProfilePlanner().plan(snapshot, target,
                                                     {"shadowsocks": {"password": "test-password",
                                                                      "method": "aes-256-gcm"}},
                                                     {"shadowsocks": ["SS"]}, ResolveContext({}))
                    result = GeneratorRegistry().for_target(target).generate(
                        RenderInput(target, plans, snapshot.defaults))
                    self.assertTrue(result.body)
                    if target == "v2ray-json":
                        document = next(item for item in json.loads(result.body) if item["remarks"] == "Automatic")
                        self.assertEqual(document["routing"]["balancers"][0]["strategy"]["type"], "roundRobin")
                        self.assertEqual(len([item for item in document["outbounds"]
                                         if item["tag"].startswith("mb-auto-")]), 2)
                    if target == "sing-box":
                        group = next(node for node in json.loads(result.body)[
                                     "outbounds"] if node["tag"] == "Automatic")
                        self.assertEqual(group["type"], "urltest")
                        self.assertEqual(group["interval"], "60s")
        self.migrate("downgrade", "f6a82c1d5e90")
        self.assertEqual(self.schema(), original_schema)
        with self.engine.connect() as connection:
            self.assertEqual(encode_snapshot(read_snapshot(connection, LEGACY_TABLES)), original)
            self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_key_check").all(), [])
        self.migrate("upgrade", "head", foreign_keys=False)
        self.migrate("downgrade", "f6a82c1d5e90", foreign_keys=False)
        self.assertEqual(self.schema(), original_schema)

    def schema(self):
        inspector = sa.inspect(self.engine)
        return {name: {
            "columns": {column["name"]: (str(column["type"]), column["nullable"], column["default"])
                        for column in inspector.get_columns(name)},
            "foreign_keys": inspector.get_foreign_keys(name),
            "indexes": inspector.get_indexes(name),
            "unique": inspector.get_unique_constraints(name),
            "checks": inspector.get_check_constraints(name),
        } for name in LEGACY_TABLES}

    def test_single_direct_revision_after_master(self):
        scripts = ScriptDirectory.from_config(Config("alembic.ini"))
        self.assertEqual(scripts.get_heads(), ["e5c14a9d72b0"])
        changes = list(scripts.iterate_revisions("head", "f6a82c1d5e90"))
        self.assertEqual([revision.revision for revision in changes], ["e5c14a9d72b0"])
        self.assertEqual(changes[0].down_revision, "f6a82c1d5e90")

    def test_conflicting_observatory_fails_before_ddl(self):
        self.seed()
        with self.engine.begin() as connection:
            balancers = sa.Table("subscription_balancers", sa.MetaData(), autoload_with=connection)
            connection.execute(balancers.update().values(
                strategy="least_ping", probe_url="https://example.com", probe_interval=30))
            templates = sa.Table("subscription_templates", sa.MetaData(), autoload_with=connection)
            connection.execute(templates.update().where(templates.c.format == "v2ray-json").values(
                content='{"outbounds": [], "observatory": {"probeUrl": "https://other.example.com"}}'))
        result = self.migrate("upgrade", "head", success=False)
        self.assertIn("cannot be migrated safely", result.stderr)
        self.assertNotIn("host_composition_archive", sa.inspect(self.engine).get_table_names())
        self.assertIn("subscription_balancers", sa.inspect(self.engine).get_table_names())

    def test_downgrade_refuses_to_overwrite_new_settings(self):
        self.seed()
        self.migrate("upgrade", "head")
        with self.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE hosts SET remark='Edited' WHERE id=1")
        result = self.migrate("downgrade", "f6a82c1d5e90", success=False)
        self.assertIn("changed after upgrading", result.stderr)
        self.assertIn("host_composition_archive", sa.inspect(self.engine).get_table_names())

    def test_legacy_explicit_clash_group_does_not_gain_generated_members(self):
        self.seed()
        with self.engine.begin() as connection:
            connection.exec_driver_sql("DELETE FROM subscription_balancer_hosts")
            connection.exec_driver_sql("DELETE FROM subscription_balancers")
            templates = sa.Table("subscription_templates", sa.MetaData(), autoload_with=connection)
            connection.execute(templates.update().where(templates.c.format == "clash").values(content=json.dumps({
                "proxies": [], "proxy-groups": [{"name": "Manual", "type": "select", "proxies": ["DIRECT"]}],
                "rules": ["MATCH,Manual"]})))
        self.migrate("upgrade", "head")
        import yaml

        with Session(self.engine) as db:
            snapshot = SubscriptionSnapshotLoader().load(db, build_default_runtime_settings())
            plans, _ = ProfilePlanner().plan(snapshot, "clash",
                                             {"shadowsocks": {"password": "password", "method": "aes-256-gcm"}},
                                             {"shadowsocks": ["SS"]}, ResolveContext({}))
            result = GeneratorRegistry().for_target("clash").generate(RenderInput("clash", plans, snapshot.defaults))
            self.assertEqual(yaml.safe_load(result.body)["proxy-groups"][0]["proxies"], ["DIRECT"])
        self.migrate("downgrade", "f6a82c1d5e90")

    def test_all_legacy_strategies_and_disabled_balancers(self):
        self.seed()
        with self.engine.begin() as connection:
            table = sa.Table("subscription_balancers", sa.MetaData(), autoload_with=connection)
            links = sa.Table("subscription_balancer_hosts", sa.MetaData(), autoload_with=connection)
            base = dict(connection.execute(table.select()).mappings().one())
            for index, strategy in enumerate(("least_ping", "least_load", "random", "round_robin"), start=2):
                connection.execute(table.insert().values(dict(base, id=index, strategy=strategy, name=strategy,
                                                              enabled=index != 5, position=index)))
                connection.execute(links.insert(), [{"balancer_id": index, "host_id": host_id} for host_id in (1, 2)])
        self.migrate("upgrade", "head")
        with Session(self.engine) as db:
            snapshot = SubscriptionSnapshotLoader().load(db, build_default_runtime_settings())
            proxies = {"shadowsocks": {"password": "password", "method": "aes-256-gcm"}}
            for target in ("v2ray-json", "clash", "sing-box"):
                plans, _ = ProfilePlanner().plan(snapshot, target, proxies, {"shadowsocks": ["SS"]}, ResolveContext({}))
                result = GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults))
                self.assertNotIn('"round_robin"', result.body)
                if target == "v2ray-json":
                    documents = {item["remarks"]: item for item in json.loads(result.body)}
                    for name, kind in (("least_ping", "leastPing"), ("least_load", "leastLoad"), ("random", "random")):
                        self.assertEqual(documents[name]["routing"]["balancers"][0]["strategy"]["type"], kind)
                    self.assertNotIn("round_robin", documents)
                else:
                    import yaml

                    document = yaml.safe_load(result.body)
                    nodes = document["proxy-groups" if target == "clash" else "outbounds"]
                    names = {node["name" if target == "clash" else "tag"] for node in nodes}
                    self.assertTrue({"Automatic", "least_ping", "least_load", "random"}.issubset(names))
                    self.assertNotIn("round_robin", names)
        self.migrate("downgrade", "f6a82c1d5e90")

    def test_excluded_format_is_not_enabled_for_a_source(self):
        ids = self.seed()
        with self.engine.begin() as connection:
            table = sa.Table("host_subscription_templates", sa.MetaData(), autoload_with=connection)
            connection.execute(table.delete().where(table.c.host_id == ids[1], table.c.format == "v2ray-json"))
        self.migrate("upgrade", "head")
        with Session(self.engine) as db:
            snapshot = SubscriptionSnapshotLoader().load(db, build_default_runtime_settings())
            plans, _ = ProfilePlanner().plan(snapshot, "v2ray-json",
                                             {"shadowsocks": {"password": "password", "method": "aes-256-gcm"}},
                                             {"shadowsocks": ["SS"]}, ResolveContext({}))
            result = GeneratorRegistry().for_target("v2ray-json").generate(
                RenderInput("v2ray-json", plans, snapshot.defaults))
            document = next(item for item in json.loads(result.body) if item["remarks"] == "Automatic")
            injected = [node for node in document["outbounds"] if node["tag"].startswith("mb-auto-")]
            self.assertEqual(len(injected), 1)
            self.assertIn(f"host-{ids[0]}", injected[0]["tag"])

    def test_unavailable_first_member_does_not_remove_remaining_sources(self):
        ids = self.seed()
        self.migrate("upgrade", "head")
        with self.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE hosts SET enabled=0 WHERE id=?", (ids[0],))
        with Session(self.engine) as db:
            snapshot = SubscriptionSnapshotLoader().load(db, build_default_runtime_settings())
            for target in ("v2ray-json", "clash", "sing-box"):
                plans, _ = ProfilePlanner().plan(snapshot, target,
                                                 {"shadowsocks": {"password": "password", "method": "aes-256-gcm"}},
                                                 {"shadowsocks": ["SS"]}, ResolveContext({}))
                result = GeneratorRegistry().for_target(target).generate(RenderInput(target, plans, snapshot.defaults))
                self.assertTrue(result.body)
                if target == "v2ray-json":
                    document = next(item for item in json.loads(result.body) if item["remarks"] == "Automatic")
                    tags = [node["tag"] for node in document["outbounds"] if node["tag"].startswith("mb-auto-")]
                    self.assertEqual(tags, [f"mb-auto-1-host-{ids[1]}"])
                else:
                    import yaml

                    document = yaml.safe_load(result.body)
                    node = next(node for node in document["proxy-groups" if target == "clash" else "outbounds"]
                                if node["name" if target == "clash" else "tag"] == "Automatic")
                    self.assertEqual(node["proxies" if target == "clash" else "outbounds"], ["Host 1"])

    def test_incompatible_aggregate_templates_fail_before_ddl(self):
        self.seed()
        with self.engine.begin() as connection:
            templates = sa.Table("subscription_templates", sa.MetaData(), autoload_with=connection)
            base = dict(connection.execute(templates.select().where(templates.c.format == "clash")).mappings().one())
            base.update(id=20, name="Other", default_marker=None)
            connection.execute(templates.insert().values(**base))
            bindings = sa.Table("host_subscription_templates", sa.MetaData(), autoload_with=connection)
            connection.execute(bindings.update().where(bindings.c.host_id == 2, bindings.c.format == "clash").values(
                template_id=20))
        result = self.migrate("upgrade", "head", success=False)
        self.assertIn("incompatible aggregate templates", result.stderr)
        self.assertNotIn("host_composition_archive", sa.inspect(self.engine).get_table_names())

    def test_mysql_and_mariadb_runtime_schema_compiles(self):
        from app.db.base import Base

        for name in ("hosts", "subscription_templates", "host_subscription_templates"):
            for dialect in (mysql.dialect(), MariaDBDialect()):
                self.assertIn("CREATE TABLE", str(CreateTable(Base.metadata.tables[name]).compile(dialect=dialect)))
