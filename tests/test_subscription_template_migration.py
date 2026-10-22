import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import TestCase

import sqlalchemy as sa

from app.utils.subscription_template_defaults import (
    FULL_TEMPLATE_SOURCES,
    GENERATOR_TEMPLATE_SOURCES,
)


class SubscriptionTemplateMigrationTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='subscription-template-migration-')
        self.url = f'sqlite:///{Path(self.directory.name) / "database.sqlite"}'
        self.root = Path(__file__).resolve().parents[1]
        self.engine = sa.create_engine(self.url)

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def migrate(self, command, revision):
        result = subprocess.run(
            [sys.executable, '-m', 'alembic', command, revision], cwd=self.root,
            env={**os.environ, 'MARZBAN_CLI': '1', 'SQLALCHEMY_DATABASE_URL': self.url},
            capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def table(self, name):
        return sa.Table(name, sa.MetaData(), autoload_with=self.engine)

    def test_existing_content_assignments_and_downgrade_round_trip(self):
        self.migrate('upgrade', 'e2f7a3c9b4d1')
        legacy = self.table('subscription_templates')
        saved_at = datetime(2024, 1, 2, 3, 4, 5)
        with self.engine.begin() as connection:
            old = {row['key']: row['content'] + '\n \n' for row in connection.execute(sa.select(legacy)).mappings()}
            for key, content in old.items():
                connection.execute(legacy.update().where(legacy.c.key == key).values(
                    content=content, updated_at=saved_at))
            inbounds = self.table('inbounds')
            inbound_id = connection.execute(inbounds.insert().values(
                tag='SS', content={'tag': 'SS'}, enabled=True, readonly=False,
            )).inserted_primary_key[0]
            hosts = self.table('hosts')
            connection.execute(hosts.insert().values(
                inbound_id=inbound_id, remark='Existing', address='example.com', security='inbound_default',
                mux_enable=False, random_user_agent=False, use_sni_as_host=False,
            ))
        self.migrate('upgrade', 'f6a82c1d5e90')
        templates = self.table('subscription_templates')
        bindings = self.table('host_subscription_templates')
        settings = self.table('runtime_settings')
        with self.engine.connect() as connection:
            current = {row['format']: row for row in connection.execute(sa.select(templates)).mappings()}
            self.assertEqual(len(current), 5)
            self.assertTrue(all(row['name'] == 'default' and row['default_marker'] == 1 for row in current.values()))
            for format, (key, _) in FULL_TEMPLATE_SOURCES.items():
                self.assertEqual(current[format]['content'], old[key])
                self.assertEqual(current[format]['updated_at'], saved_at)
            runtime = connection.execute(sa.select(settings)).mappings().one()
            for key in GENERATOR_TEMPLATE_SOURCES:
                self.assertEqual(runtime[key], old[key])
            assignments = connection.execute(sa.select(bindings)).mappings().all()
            self.assertEqual(len(assignments), 5)
            for assignment in assignments:
                self.assertEqual(assignment['template_id'], current[assignment['format']]['id'])
        self.migrate('downgrade', 'e2f7a3c9b4d1')
        legacy = self.table('subscription_templates')
        with self.engine.connect() as connection:
            restored = {row['key']: row['content'] for row in connection.execute(sa.select(legacy)).mappings()}
            self.assertEqual(restored, old)
        self.assertNotIn('mux', self.table('runtime_settings').c)
        self.migrate('upgrade', 'head')
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(sa.select(sa.func.count()).select_from(
                self.table('host_subscription_templates'))), 5)

    def test_fresh_install_has_all_defaults_and_no_host_assignments(self):
        self.migrate('upgrade', 'head')
        with self.engine.connect() as connection:
            formats = connection.execute(sa.select(self.table('subscription_templates').c.format)).scalars().all()
            self.assertEqual(set(formats), {'v2ray', 'v2ray-json', 'clash', 'sing-box', 'outline'})
            self.assertEqual(connection.scalar(sa.select(sa.func.count()).select_from(
                self.table('host_subscription_templates'))), 0)
