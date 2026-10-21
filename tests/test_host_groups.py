from unittest import TestCase

from sqlalchemy import create_engine, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


from app.db.base import Base
from app.db.models.associations import host_group_hosts_association
from app.db.models.proxies import ProxyInbound
from app.models.proxy import HostGroupCreate, HostGroupModify
from app.models.host import HostCreate as ProxyHostCreate, HostPatch, HostResponse as ProxyHostV2
from app.subscription.share import build_subscription_hosts_by_inbound
from app.db.crud import proxy_hosts as host_crud


class HostGroupTests(TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add_all([
            ProxyInbound(tag="VLESS TCP", content={"tag": "VLESS TCP"}),
            ProxyInbound(tag="VLESS WS", content={"tag": "VLESS WS"}),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def create_group(self, group_id="eu", name="Europe"):
        return host_crud.create_host_group(
            self.db,
            HostGroupCreate(id=group_id, name=name, description=None, tags=["premium"]),
        )

    def create_host(self, remark="Germany", group_ids=None, address="example.com", port=None):
        return host_crud.create_host(
            self.db,
            ProxyHostCreate(
                inbound_id=1,
                remark=remark,
                address=address,
                port=port,
                group_ids=group_ids or [],
            ),
        )

    def association_count(self):
        return self.db.query(func.count()).select_from(host_group_hosts_association).scalar()

    def test_create_update_delete_host_group(self):
        group = self.create_group()
        self.assertEqual(group.id, "eu")
        self.assertEqual(group.tags, ["premium"])

        updated = host_crud.update_host_group(
            self.db,
            group,
            HostGroupModify(name="Europe Premium", description="EU pool", tags=["eu"]),
        )
        self.assertEqual(updated.name, "Europe Premium")
        self.assertEqual(updated.description, "EU pool")
        self.assertEqual(updated.tags, ["eu"])

        host_crud.delete_host_group(self.db, updated)
        self.assertIsNone(host_crud.get_host_group(self.db, "eu"))

    def test_duplicate_group_id_raises_integrity_error(self):
        self.create_group()
        with self.assertRaises(IntegrityError):
            self.create_group(name="Duplicate")
        self.db.rollback()

    def test_host_round_trip_includes_groups_and_filters_by_group(self):
        self.create_group("eu", "Europe")
        self.create_group("us", "United States")
        host = self.create_host(group_ids=["eu", "us"], address="berlin.example.com", port=1080)
        self.create_host("Chicago", group_ids=["us"], address="chicago.example.com", port=8443)

        response = ProxyHostV2.model_validate(host)
        self.assertEqual([group.id for group in response.groups], ["eu", "us"])
        self.assertEqual([row.id for row in host_crud.list_hosts(self.db, group_id="eu")], [host.id])
        self.assertEqual([row.id for row in host_crud.list_hosts(self.db, inbound_id=1, group_id="eu")], [host.id])
        self.assertEqual(
            [row.remark for row in host_crud.list_hosts(self.db, group_ids=["eu", "us"])],
            ["Germany", "Chicago"],
        )
        self.assertEqual(
            [row.remark for row in host_crud.list_hosts(self.db, inbound_id=1, group_ids=["eu", "us"])],
            ["Germany", "Chicago"],
        )
        self.assertEqual([row.id for row in host_crud.list_hosts(self.db, search="germany")], [host.id])
        self.assertEqual([row.id for row in host_crud.list_hosts(self.db, search="berlin")], [host.id])
        self.assertEqual([row.id for row in host_crud.list_hosts(self.db, search="1080")], [host.id])

    def test_subscription_hosts_are_built_from_filtered_hosts(self):
        self.create_group("eu", "Europe")
        self.create_host(group_ids=["eu"], address="berlin.example.com")
        disabled_host = self.create_host("Disabled", group_ids=["eu"], address="disabled.example.com")
        disabled_host.enabled = False
        self.db.commit()

        hosts = host_crud.list_hosts(self.db, group_ids=["eu"])
        hosts_by_inbound = build_subscription_hosts_by_inbound(hosts)
        self.assertEqual(list(hosts_by_inbound), ["VLESS TCP"])
        self.assertEqual([host.remark for host in hosts_by_inbound["VLESS TCP"]], ["Germany"])


    def test_attach_detach_and_missing_group(self):
        host = self.create_host()
        self.create_group("eu", "Europe")
        self.create_group("us", "United States")

        attached = host_crud.update_host(self.db, host, HostPatch(group_ids=["eu", "us"]))
        self.assertEqual([group.id for group in attached.groups], ["eu", "us"])

        detached = host_crud.update_host(self.db, attached, HostPatch(group_ids=["us"]))
        self.assertEqual([group.id for group in detached.groups], ["us"])

        with self.assertRaises(ValueError):
            host_crud.update_host(self.db, detached, HostPatch(group_ids=["missing"]))

    def test_delete_group_or_host_cleans_associations(self):
        group = self.create_group()
        host = self.create_host(group_ids=[group.id])
        self.assertEqual(self.association_count(), 1)

        host_crud.delete_host_group(self.db, group)
        self.assertEqual(self.association_count(), 0)

        group = self.create_group()
        host = host_crud.update_host(self.db, host, HostPatch(group_ids=[group.id]))
        self.assertEqual(self.association_count(), 1)

        host_crud.remove_host(self.db, host)
        self.assertEqual(self.association_count(), 0)
