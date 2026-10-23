"""Ordered mapper operations over copied client nodes, with literal query-key support."""

from copy import deepcopy
import re

MISSING = object()


def _parts(path):
    return [part for part in re.split(r"\.|\[|\]", path) if part]


def _get(source, parts):
    value = source
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part, MISSING)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return MISSING
    return value


def _array_position(part):
    if not part.isdigit():
        return None
    position = int(part)
    if position >= 1024:
        raise ValueError("Mapper array index must be smaller than 1024")
    return position


def _child_container(parent, part, next_part, create):
    """Walk one path segment, creating objects/arrays only for set and copy operations."""
    empty = [] if next_part.isdigit() else {}
    if isinstance(parent, dict):
        if part not in parent and create:
            parent[part] = empty
        return parent.get(part)
    if not isinstance(parent, list):
        return None
    position = _array_position(part)
    if position is None:
        return None
    if position >= len(parent) and create:
        parent.extend([None] * (position + 1 - len(parent)))
    if position >= len(parent):
        return None
    if parent[position] is None and create:
        parent[position] = empty
    return parent[position]


def _assign(parent, part, value, remove):
    if isinstance(parent, dict):
        if remove:
            parent.pop(part, None)
        else:
            parent[part] = deepcopy(value)
        return
    if not isinstance(parent, list):
        return
    position = _array_position(part)
    if position is None:
        return
    if position >= len(parent) and not remove:
        parent.extend([None] * (position + 1 - len(parent)))
    if position < len(parent):
        if remove:
            parent.pop(position)
        else:
            parent[position] = deepcopy(value)


class HostMapper:
    def apply(self, node, operations, connection, flat=False):
        result = deepcopy(node)
        source = {
            "address": connection.address, "port": connection.port, "finalRemark": connection.remark,
            "protocol": connection.inbound["protocol"], "protocolOptions": connection.credentials,
            "transport": connection.inbound["network"], "security": connection.inbound["tls"],
            "metadata": {"remark": connection.remark},
        }
        for operation in operations:
            parts = [operation["to"]] if flat else _parts(operation["to"])
            if not parts or any(part in {"__proto__", "constructor", "__class__"} for part in parts):
                raise ValueError("Invalid mapper path")
            value = operation.get("value")
            if operation["op"] == "copy":
                path = operation["from"]
                value = _get(source, _parts(path[6:])) if path.startswith("$host.") else _get(
                    connection.raw_inbound, _parts(path))
                if value is MISSING:
                    continue
            parent = result
            remove = operation["op"] == "unset"
            for index, part in enumerate(parts[:-1]):
                parent = _child_container(parent, part, parts[index + 1], create=not remove)
                if parent is None:
                    break
            _assign(parent, parts[-1], value, remove)
        return result
