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
from sqlalchemy.schema import CreateTable

from app.db.base import Base
from app.db.migrations.host_redesign_v1 import preflight


class HostRedesignMigrationTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="host-redesign-")
        self.url = "sqlite:///" + (Path(self.directory.name) / "test.db").as_posix()
        self.engine = sa.create_engine(self.url)
        self.migrate("upgrade", "f6a82c1d5e90")

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def migrate(self, operation, revision, succeeds=True):
        environment = dict(os.environ, SQLALCHEMY_DATABASE_URL=self.url)
        result = subprocess.run([sys.executable, "-m", "alembic", operation, revision],
                                cwd=Path(__file__).resolve().parents[1], env=environment,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def seed(self, empty=False):
        metadata = sa.MetaData()
        metadata.reflect(self.engine)
        now = datetime(2024, 1, 2)
        with self.engine.begin() as connection:
            inbound_id = connection.execute(metadata.tables["inbounds"].insert().values(
                tag="XHTTP", enabled=True, readonly=False,
                content={"tag": "XHTTP", "protocol": "vless", "port": 443, "settings": {"clients": []},
                         "streamSettings": {"network": "xhttp", "security": "none",
                                            "xhttpSettings": {"mode": "packet-up"}}})).inserted_primary_key[0]
            ids = []
            for index in range(2):
                ids.append(connection.execute(metadata.tables["hosts"].insert().values(
                    inbound_id=inbound_id, remark=f"Host {index}", address=f"host-{index}.example.com",
                    position=index, security="inbound_default", mux_enable=False, random_user_agent=False,
                    use_sni_as_host=False, is_disabled=False, sc_max_buffered_posts=0,
                    x_padding_obfs_mode=False, uplink_http_method="PUT")).inserted_primary_key[0])
            templates = list(connection.execute(metadata.tables["subscription_templates"].select()).mappings())
            for host_id in ids:
                for template in templates:
                    connection.execute(metadata.tables["host_subscription_templates"].insert().values(
                        host_id=host_id, format=template["format"], template_id=template["id"]))
            balancer_id = connection.execute(metadata.tables["subscription_balancers"].insert().values(
                name="Automatic", enabled=True, strategy="round_robin", probe_url="https://example.com/204",
                probe_interval=60, position=0, created_at=now, updated_at=now)).inserted_primary_key[0]
            if not empty:
                for host_id in ids:
                    connection.execute(metadata.tables["subscription_balancer_hosts"].insert().values(
                        balancer_id=balancer_id, host_id=host_id))
        return ids

    def test_transfer_preserves_ids_extra_templates_and_composition(self):
        ids = self.seed()
        cli = subprocess.run([sys.executable, "scripts/host_preflight.py", "--database-url", self.url],
                             cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
                             encoding="utf-8", timeout=30)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["host_count"], 2)
        self.assertIn("subscription_balancers", sa.inspect(self.engine).get_table_names())
        with self.engine.connect() as connection:
            self.assertEqual(preflight(connection)["errors"], [])
        self.migrate("upgrade", "head")
        metadata = sa.MetaData()
        metadata.reflect(self.engine)
        self.assertNotIn("subscription_balancers", metadata.tables)
        with self.engine.connect() as connection:
            hosts = {row["id"]: row for row in connection.execute(metadata.tables["hosts"].select()).mappings()}
            for host_id in ids:
                self.assertFalse(hosts[host_id]["is_hidden"])
                self.assertEqual(hosts[host_id]["overrides"]["transport"]["xhttp"]["extra"],
                                 {"scMaxBufferedPosts": 0, "xPaddingObfsMode": False, "uplinkHTTPMethod": "PUT"})
            recipients = [host for host in hosts.values() if host["id"] not in ids]
            self.assertEqual(len(recipients), 1)
            owner = recipients[0]
            self.assertFalse(owner["is_hidden"])
            self.assertNotIn("host_links", metadata.tables)
            self.assertNotIn("balancer_settings", metadata.tables["hosts"].c)
            self.assertNotIn("show_when_composed", metadata.tables["hosts"].c)
            formats = set(connection.execute(sa.select(metadata.tables["host_subscription_templates"].c.format).where(
                metadata.tables["host_subscription_templates"].c.host_id == owner["id"])).scalars())
            self.assertEqual(formats, {"v2ray-json"})
            self.assertEqual(list(connection.exec_driver_sql("PRAGMA foreign_key_check")), [])
        self.migrate("downgrade", "f6a82c1d5e90")
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT COUNT(*) FROM subscription_balancers").scalar(), 1)
            self.assertEqual(connection.exec_driver_sql("SELECT COUNT(*) FROM subscription_balancer_hosts").scalar(), 2)

    def test_ordinary_hosts_upgrade_downgrade_and_upgrade(self):
        ids = self.seed()
        with self.engine.begin() as connection:
            connection.exec_driver_sql("DELETE FROM subscription_balancer_hosts")
            connection.exec_driver_sql("DELETE FROM subscription_balancers")
        self.migrate("upgrade", "head")
        self.migrate("downgrade", "f6a82c1d5e90")
        self.migrate("upgrade", "head")
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT id FROM hosts ORDER BY id").scalars().all(), ids)

    def test_empty_balancer_fails_before_schema_changes(self):
        self.seed(empty=True)
        with self.engine.connect() as connection:
            report = preflight(connection)
            self.assertEqual(report["errors"][0]["reason"], "empty_balancer_requires_source_host")
        self.migrate("upgrade", "head", succeeds=False)
        inspector = sa.inspect(self.engine)
        self.assertNotIn("host_links", inspector.get_table_names())
        self.assertIn("sc_max_buffered_posts", {column["name"] for column in inspector.get_columns("hosts")})

    def test_mysql_and_mariadb_tables_compile(self):
        for name in ("hosts", "subscription_templates"):
            self.assertIn("CREATE TABLE", str(CreateTable(Base.metadata.tables[name]).compile(dialect=mysql.dialect())))
