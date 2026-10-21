import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


class ClashFormatMigrationTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="clash-format-")
        self.root = Path(__file__).resolve().parents[1]
        self.url = "sqlite:///" + (Path(self.directory.name) / "test.db").as_posix()
        self.engine = sa.create_engine(self.url)
        self.migrate("upgrade", "b57c20e91a46")
        self.metadata = sa.MetaData()
        self.metadata.reflect(self.engine)
        tables = self.metadata.tables
        with self.engine.begin() as connection:
            template = connection.execute(tables["subscription_templates"].select().where(
                tables["subscription_templates"].c.format == "clash-meta")).mappings().one()
            self.template_id, self.content = template["id"], template["content"]
            inbound_id = connection.execute(tables["inbounds"].insert().values(
                tag="VMess", content={"tag": "VMess", "protocol": "vmess", "port": 443},
                enabled=True, readonly=False)).inserted_primary_key[0]
            self.host_id = connection.execute(tables["hosts"].insert().values(
                inbound_id=inbound_id, remark="A", address="example.com", enabled=True, position=0,
                show_when_composed=True, created_at=template["created_at"], updated_at=template["updated_at"],
                overrides={"clients": {"clash-meta": {"ip_version": "ipv4"}},
                           "mapper": {"clash-meta": [{"op": "set", "to": "udp", "value": False}]}},
                balancer_settings={"strategy": "least_ping", "probe_url": "https://example.com/204",
                                   "probe_interval": 300, "clients": {"clash-meta": {"tolerance": 0, "lazy": False}}}
            )).inserted_primary_key[0]
            connection.execute(tables["host_subscription_templates"].insert().values(
                host_id=self.host_id, format="clash-meta", template_id=self.template_id))

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def migrate(self, operation, revision, succeeds=True):
        result = subprocess.run([sys.executable, "-m", "alembic", operation, revision], cwd=self.root,
                                env={**os.environ, "MARZBAN_CLI": "1", "SQLALCHEMY_DATABASE_URL": self.url},
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(result.returncode == 0, succeeds, result.stdout + result.stderr)
        return result

    def assert_format(self, format):
        metadata = sa.MetaData()
        metadata.reflect(self.engine)
        with self.engine.connect() as connection:
            template = connection.execute(metadata.tables["subscription_templates"].select().where(
                metadata.tables["subscription_templates"].c.id == self.template_id)).mappings().one()
            self.assertEqual((template["format"], template["content"], template["default_marker"]),
                             (format, self.content, 1))
            binding = connection.execute(metadata.tables["host_subscription_templates"].select()).mappings().one()
            self.assertEqual((binding["format"], binding["template_id"]), (format, self.template_id))
            host = connection.execute(metadata.tables["hosts"].select()).mappings().one()
            self.assertEqual(host["id"], self.host_id)
            self.assertEqual(host["overrides"]["clients"], {format: {"ip_version": "ipv4"}})
            self.assertEqual(host["overrides"]["mapper"], {format: [{"op": "set", "to": "udp", "value": False}]})
            self.assertEqual(host["balancer_settings"]["clients"], {format: {"tolerance": 0, "lazy": False}})
            self.assertEqual(list(connection.exec_driver_sql("PRAGMA foreign_key_check")), [])

    def test_upgrade_downgrade_and_reupgrade_preserve_data(self):
        self.migrate("upgrade", "head")
        self.assert_format("clash")
        self.migrate("downgrade", "b57c20e91a46")
        self.assert_format("clash-meta")
        self.migrate("upgrade", "head")
        self.assert_format("clash")

    def test_conflicts_are_rejected_before_schema_changes(self):
        hosts = self.metadata.tables["hosts"]
        with self.engine.begin() as connection:
            connection.execute(hosts.update().values(overrides={"clients": {
                "clash-meta": {"ip_version": "ipv4"}, "clash": {"ip_version": "ipv6"}}}))
        result = self.migrate("upgrade", "head", succeeds=False)
        self.assertIn(f"Host {self.host_id}: conflicting clash-meta/clash settings", result.stderr)
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar(),
                             "b57c20e91a46")
            self.assertEqual(connection.exec_driver_sql("SELECT format FROM host_subscription_templates").scalar(),
                             "clash-meta")

    def test_sqlite_foreign_keys_remain_enabled_in_both_directions(self):
        migration = importlib.import_module("app.db.migrations.versions.c82a6f0159bd_use_clash_format_name")
        for operation, format in ((migration.upgrade, "clash"), (migration.downgrade, "clash-meta")):
            with self.subTest(format=format), self.engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
                context = MigrationContext.configure(connection)
                with context.begin_transaction(), Operations.context(context):
                    operation()
                self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)
            self.assert_format(format)
