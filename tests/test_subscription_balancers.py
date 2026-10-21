"""The old balancer API was replaced by host composition; regressions live in test_unified_hosts."""

import json
from unittest import TestCase
from app.subscription.generators.xray_json import XrayBalancerBuilder
from types import SimpleNamespace


class SubscriptionBalancerBuilderTests(TestCase):
    def test_balancer_rule_matches_tcp_and_udp(self):
        profile = SimpleNamespace(owner=SimpleNamespace(id=17), balancer={
            "strategy": "least_ping", "probe_url": "https://example.com/204", "probe_interval": 300,
        })
        document = {"outbounds": [], "routing": {"rules": []}}
        XrayBalancerBuilder().apply(document, profile, {1: "mb-auto-17-host-1"})
        rule = document["routing"]["rules"][-1]
        self.assertEqual(rule["network"], "tcp,udp")
        self.assertEqual(rule["balancerTag"], "mb-auto-17")
        self.assertEqual(document["observatory"]["probeInterval"], "300s")
