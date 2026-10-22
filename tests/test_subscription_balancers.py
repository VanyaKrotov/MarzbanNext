"""Legacy native strategy conversion is covered independently of the removed host API."""

from unittest import TestCase
from app.db.migrations.template_composition_v1 import xray_overlay


class SubscriptionBalancerMigrationTests(TestCase):
    def test_native_balancer_and_observer_share_only_endpoint_prefixes(self):
        document = xray_overlay({"id": 17,
                                 "strategy": "least_ping", "probe_url": "https://example.com/204", "probe_interval": 300,
                                 }, [1, 2])
        self.assertEqual(document["routing"]["balancers"][0]["selector"], ["mb-auto-17-host-"])
        self.assertEqual(document["observatory"]["subjectSelector"], ["mb-auto-17-host-"])
        self.assertEqual(document["observatory"]["probeInterval"], "300s")
