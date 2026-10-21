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
            for index, part in enumerate(parts[:-1]):
                if isinstance(parent, dict):
                    if part not in parent and operation["op"] != "unset":
                        parent[part] = [] if parts[index + 1].isdigit() else {}
                    parent = parent.get(part)
                elif isinstance(parent, list) and part.isdigit():
                    position = int(part)
                    if position >= 1024:
                        raise ValueError("Mapper array index must be smaller than 1024")
                    if position >= len(parent) and operation["op"] != "unset":
                        parent.extend([None] * (position + 1 - len(parent)))
                    if position < len(parent):
                        if parent[position] is None and operation["op"] != "unset":
                            parent[position] = [] if parts[index + 1].isdigit() else {}
                        parent = parent[position]
                    else:
                        parent = None
                else:
                    parent = None
                    break
            last = parts[-1]
            if isinstance(parent, dict):
                if operation["op"] == "unset":
                    parent.pop(last, None)
                else:
                    parent[last] = deepcopy(value)
            elif isinstance(parent, list) and last.isdigit():
                position = int(last)
                if position >= 1024:
                    raise ValueError("Mapper array index must be smaller than 1024")
                if position >= len(parent) and operation["op"] != "unset":
                    parent.extend([None] * (position + 1 - len(parent)))
                if position < len(parent):
                    if operation["op"] == "unset":
                        parent.pop(position)
                    else:
                        parent[position] = deepcopy(value)
        return result
