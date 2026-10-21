import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


class ClashMetaMigrationTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="clash-meta-")
        self.root = Path(__file__).resolve().parents[1]
        self.url = "sqlite:///" + (Path(self.directory.name) / "test.db").as_posix()
        self.engine = sa.create_engine(self.url)
        self.migrate("upgrade", "a319d48e7062")
        self.metadata = sa.MetaData()
        self.metadata.reflect(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def migrate(self, operation, revision, succeeds=True):
        result = subprocess.run([sys.executable, "-m", "alembic", operation, revision], cwd=self.root,
                                env={**os.environ, "MARZBAN_CLI": "1", "SQLALCHEMY_DATABASE_URL": self.url},
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(result.returncode == 0, succeeds, result.stdout + result.stderr)
        return result

    def seed(self, conflict=False):
        tables = self.metadata.tables
        with self.engine.begin() as connection:
            template = connection.execute(tables["subscription_templates"].select().where(
                tables["subscription_templates"].c.format == "clash")).mappings().one()
            inbound = connection.execute(tables["inbounds"].insert().values(
                tag="VMess", content={"tag": "VMess", "protocol": "vmess", "port": 443},
                enabled=True, readonly=False)).inserted_primary_key[0]
            clients = {"clash": {"tolerance": 0}, "mihomo": {"lazy": False}}
            if conflict:
                clients = {"clash": {"probe_interval": 60}, "mihomo": {"probe_interval": 120}}
            host_id = connection.execute(tables["hosts"].insert().values(
                inbound_id=inbound, remark="A", address="example.com", enabled=True, position=0,
                show_when_composed=True, created_at=template["created_at"], updated_at=template["updated_at"],
                overrides={"clients": {"mihomo": {"ip_version": "ipv4"}},
                           "mapper": {"mihomo": [{"op": "set", "to": "udp", "value": False}]}},
                balancer_settings={"strategy": "least_ping", "probe_url": "https://example.com/204",
                                   "probe_interval": 300, "clients": clients})).inserted_primary_key[0]
            connection.execute(tables["host_subscription_templates"].insert().values(
                host_id=host_id, format="clash", template_id=template["id"]))
        return host_id, template["id"], template["content"]

    def assert_upgraded(self, host_id, template_id, content):
        metadata = sa.MetaData()
        metadata.reflect(self.engine)
        with self.engine.connect() as connection:
            template = connection.execute(metadata.tables["subscription_templates"].select().where(
                metadata.tables["subscription_templates"].c.id == template_id)).mappings().one()
            self.assertEqual((template["format"], template["content"]), ("clash-meta", content))
            binding = connection.execute(metadata.tables["host_subscription_templates"].select()).mappings().one()
            self.assertEqual((binding["format"], binding["template_id"]), ("clash-meta", template_id))
            host = connection.execute(metadata.tables["hosts"].select()).mappings().one()
            self.assertEqual(host["id"], host_id)
            self.assertEqual(host["overrides"]["clients"], {"clash-meta": {"ip_version": "ipv4"}})
            self.assertEqual(set(host["overrides"]["mapper"]), {"clash-meta"})
            self.assertEqual(host["balancer_settings"]["clients"], {"clash-meta": {"tolerance": 0, "lazy": False}})
            self.assertEqual(list(connection.exec_driver_sql("PRAGMA foreign_key_check")), [])

    def test_upgrade_downgrade_preserves_ids_content_and_options(self):
        saved = self.seed()
        self.migrate("upgrade", "head")
        self.assert_upgraded(*saved)
        self.migrate("downgrade", "a319d48e7062")
        self.migrate("upgrade", "head")
        self.assert_upgraded(*saved)

    def test_conflicts_fail_before_schema_or_data_changes(self):
        self.seed(conflict=True)
        result = self.migrate("upgrade", "head", succeeds=False)
        self.assertIn("conflicting Clash/Mihomo", result.stderr)
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version").scalar(), "a319d48e7062")
            self.assertEqual(connection.exec_driver_sql(
                "SELECT format FROM host_subscription_templates").scalar(), "clash")

    def test_upgrade_with_sqlite_foreign_keys_enabled(self):
        saved = self.seed()
        migration = importlib.import_module("app.db.migrations.versions.b57c20e91a46_unify_clash_meta_format")
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
            context = MigrationContext.configure(connection)
            with context.begin_transaction(), Operations.context(context):
                migration.upgrade()
            self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)
        self.assert_upgraded(*saved)
