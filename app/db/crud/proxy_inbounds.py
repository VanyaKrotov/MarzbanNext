"""Domain CRUD helpers extracted from the former app.db.crud module."""

from typing import Dict, List, Optional

from sqlalchemy import and_, delete, func
from sqlalchemy.orm import Session, joinedload

from app.db.models.associations import excluded_inbounds_association, template_inbounds_association
from app.db.models.nodes import Node
from app.db.models.proxies import Proxy, ProxyHost, ProxyInbound
from app.db.models.users import User
from app.models.proxy import InboundCreate, InboundModify, ProxyTypes
from config import XRAY_EXCLUDE_INBOUND_TAGS


def add_default_host(db: Session, inbound: ProxyInbound):
    """
    Adds a default host to a proxy inbound.

    Args:
        db (Session): Database session.
        inbound (ProxyInbound): Proxy inbound to add the default host to.
    """
    host = ProxyHost(
        remark="🚀 Marz ({USERNAME}) [{PROTOCOL} - {TRANSPORT}]",
        address="{SERVER_IP}",
        inbound=inbound,
        position=get_next_host_position(db),
    )
    from app.db.crud.subscription_templates import build_default_host_bindings

    host.subscription_templates = build_default_host_bindings(db)
    db.add(host)
    db.commit()


def get_next_host_position(db: Session) -> int:
    max_position = db.query(func.max(ProxyHost.position)).scalar()
    return (max_position if max_position is not None else -1) + 1


def get_inbound_or_raise(db: Session, inbound_tag: str) -> ProxyInbound:
    inbound = db.query(ProxyInbound).filter(ProxyInbound.tag == inbound_tag).first()
    if not inbound:
        raise ValueError(f"Inbound {inbound_tag} doesn't exist")
    return inbound


def get_inbounds(db: Session, node_id: int | None = None) -> List[ProxyInbound]:
    query = db.query(ProxyInbound).options(joinedload(ProxyInbound.nodes))
    if node_id is not None:
        query = query.join(ProxyInbound.nodes).filter(Node.id == node_id)
    return query.order_by(ProxyInbound.tag).all()


def get_inbound(db: Session, inbound_tag: str) -> Optional[ProxyInbound]:
    return (
        db.query(ProxyInbound)
        .options(joinedload(ProxyInbound.nodes))
        .filter(ProxyInbound.tag == inbound_tag)
        .first()
    )


def ensure_protocol_inbounds_for_users(
    db: Session,
    protocol: str,
    included_tags: List[str],
    protocol_inbound_tags: List[str],
) -> List[User]:
    if not included_tags:
        return []
    try:
        proxy_type = ProxyTypes(protocol)
    except ValueError:
        return []

    included_tags = [
        tag
        for tag in dict.fromkeys(included_tags)
        if tag and tag not in XRAY_EXCLUDE_INBOUND_TAGS
    ]
    if not included_tags:
        return []

    excluded_tags = [
        tag
        for tag in dict.fromkeys(protocol_inbound_tags)
        if tag not in included_tags and tag not in XRAY_EXCLUDE_INBOUND_TAGS
    ]
    excluded_inbounds = (
        db.query(ProxyInbound)
        .filter(ProxyInbound.tag.in_(excluded_tags))
        .all()
        if excluded_tags
        else []
    )
    users = (
        db.query(User)
        .outerjoin(
            Proxy,
            and_(Proxy.user_id == User.id, Proxy.type == proxy_type),
        )
        .filter(Proxy.id.is_(None))
        .all()
    )
    for user in users:
        user.proxies.append(
            Proxy(
                type=proxy_type,
                settings=proxy_type.settings_model().dict(no_obj=True),
                excluded_inbounds=list(excluded_inbounds),
            )
        )
    return users


def exclude_protocol_inbounds_for_users(
    db: Session,
    protocol: str,
    excluded_tags: List[str],
) -> List[Proxy]:
    if not excluded_tags:
        return []
    try:
        proxy_type = ProxyTypes(protocol)
    except ValueError:
        return []

    excluded_tags = [
        tag
        for tag in dict.fromkeys(excluded_tags)
        if tag and tag not in XRAY_EXCLUDE_INBOUND_TAGS
    ]
    if not excluded_tags:
        return []

    excluded_inbounds = (
        db.query(ProxyInbound)
        .filter(ProxyInbound.tag.in_(excluded_tags))
        .all()
    )
    if not excluded_inbounds:
        return []

    proxies = (
        db.query(Proxy)
        .options(joinedload(Proxy.excluded_inbounds))
        .filter(Proxy.type == proxy_type)
        .all()
    )
    for proxy in proxies:
        current_tags = {inbound.tag for inbound in proxy.excluded_inbounds}
        proxy.excluded_inbounds.extend(
            inbound
            for inbound in excluded_inbounds
            if inbound.tag not in current_tags
        )
    return proxies


def create_inbound(db: Session, inbound: InboundCreate) -> ProxyInbound:
    content = dict(inbound.content)
    content["tag"] = inbound.tag
    nodes = {
        node.id: node
        for node in db.query(Node).filter(Node.id.in_(inbound.node_ids)).all()
    } if inbound.node_ids else {}
    missing_node_ids = set(inbound.node_ids) - nodes.keys()
    if missing_node_ids:
        raise ValueError(f"Nodes {sorted(missing_node_ids)} don't exist")
    dbinbound = ProxyInbound(
        tag=inbound.tag,
        content=content,
        enabled=inbound.enabled,
        nodes=[nodes[node_id] for node_id in dict.fromkeys(inbound.node_ids)],
    )
    db.add(dbinbound)
    db.commit()
    # add_default_host(db, dbinbound)
    db.refresh(dbinbound)
    return get_inbound(db, dbinbound.tag)


def update_inbound(
    db: Session,
    dbinbound: ProxyInbound,
    modified: InboundModify,
) -> ProxyInbound:
    if modified.content is not None:
        if dbinbound.readonly:
            raise ValueError("Content of read-only inbounds cannot be changed")
        content = dict(modified.content)
        content["tag"] = dbinbound.tag
        dbinbound.content = content
    if modified.enabled is not None:
        dbinbound.enabled = True if dbinbound.readonly else modified.enabled
    if modified.node_ids is not None:
        nodes = {
            node.id: node
            for node in db.query(Node)
            .filter(Node.id.in_(modified.node_ids))
            .all()
        } if modified.node_ids else {}
        missing_node_ids = set(modified.node_ids) - nodes.keys()
        if missing_node_ids:
            raise ValueError(f"Nodes {sorted(missing_node_ids)} don't exist")
        dbinbound.nodes = [
            nodes[node_id] for node_id in dict.fromkeys(modified.node_ids)
        ]
    db.commit()
    db.refresh(dbinbound)
    return get_inbound(db, dbinbound.tag)


def remove_inbound(db: Session, dbinbound: ProxyInbound) -> None:
    if dbinbound.readonly:
        raise ValueError("Read-only inbounds cannot be deleted")
    tag = dbinbound.tag
    dbinbound.nodes = []
    dbinbound.node_certificates = []
    db.flush()
    for association in (
        excluded_inbounds_association,
        template_inbounds_association,
    ):
        db.execute(
            delete(association).where(association.c.inbound_tag == tag)
        )
    db.delete(dbinbound)
    db.commit()


def get_inbound_nodes(db: Session, inbound_tags: List[str]) -> Dict[str, List[int]]:
    inbounds = (
        db.query(ProxyInbound)
        .options(joinedload(ProxyInbound.nodes))
        .filter(ProxyInbound.tag.in_(inbound_tags))
        .all()
        if inbound_tags
        else []
    )
    nodes_by_tag = {
        inbound.tag: [node.id for node in inbound.nodes]
        for inbound in inbounds
    }
    return {
        inbound_tag: nodes_by_tag.get(inbound_tag, [])
        for inbound_tag in inbound_tags
    }


def update_inbound_nodes(
        db: Session, inbound_nodes: Dict[str, List[int]]
) -> Dict[str, List[int]]:
    node_ids = {node_id for ids in inbound_nodes.values() for node_id in ids}
    nodes = {
        node.id: node
        for node in db.query(Node).filter(Node.id.in_(node_ids)).all()
    } if node_ids else {}

    missing_node_ids = node_ids - nodes.keys()
    if missing_node_ids:
        raise ValueError(f"Nodes {sorted(missing_node_ids)} don't exist")

    for inbound_tag, assigned_node_ids in inbound_nodes.items():
        inbound = get_inbound_or_raise(db, inbound_tag)
        inbound.nodes = [
            nodes[node_id] for node_id in dict.fromkeys(assigned_node_ids)
        ]

    db.commit()
    return get_inbound_nodes(db, list(inbound_nodes))


def get_inbound_node_ids_map(db: Session, inbound_tags: List[str]) -> Dict[str, set]:
    inbounds = (
        db.query(ProxyInbound)
        .options(joinedload(ProxyInbound.nodes))
        .filter(ProxyInbound.tag.in_(inbound_tags))
        .all()
        if inbound_tags
        else []
    )
    nodes_by_tag = {
        inbound.tag: {node.id for node in inbound.nodes}
        for inbound in inbounds
    }
    return {
        inbound_tag: nodes_by_tag.get(inbound_tag, set())
        for inbound_tag in inbound_tags
    }
