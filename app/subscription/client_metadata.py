"""Optional client metadata shared by subscription formats."""

import re

from app.subscription.contracts import ResolvedConnection


# Match Remnawave's extended-client list; ordinary Clash and FlClash do not support this extension.
# The pinned source and wire formats are documented in docs/hosts.md.
SERVER_DESCRIPTION_CLIENTS = re.compile(r"^(?:FlClash ?X|Flowvy|prizrak-box|koala-clash|Happ|INCY)/")


def supports_server_description(user_agent: str) -> bool:
    return SERVER_DESCRIPTION_CLIENTS.match(user_agent) is not None


def get_server_description(connection: ResolvedConnection, enabled: bool) -> str | None:
    if not enabled:
        return None
    return connection.client_options.get("server_description") or None
