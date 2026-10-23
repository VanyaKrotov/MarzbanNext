"""Translate shared Xray XHTTP options to the native Clash/Mihomo representation."""

from copy import deepcopy
import re


CLASH_NAMES = {
    "noGRPCHeader": "no-grpc-header", "uplinkHTTPMethod": "uplink-http-method",
    "sessionIDPlacement": "session-placement", "sessionIDKey": "session-key",
    "sessionIDTable": "session-table", "sessionIDLength": "session-length",
}
CLASH_RANGES = {"xPaddingBytes", "sessionIDLength", "uplinkChunkSize", "scMaxEachPostBytes", "scMinPostsIntervalMs"}


def _kebab_case(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def clash_reuse(options):
    return {_kebab_case(name): value if name == "hKeepAlivePeriod" else str(value)
            for name, value in options.items()}


def clash_download(download):
    settings = download.get("xhttpSettings", download.get("splithttpSettings", {}))
    extra = settings.get("extra", settings)
    security = download.get("security")
    tls = download.get("tlsSettings", {}) if security == "tls" else {}
    reality = download.get("realitySettings", {}) if security == "reality" else {}
    security_options = {}
    if security == "tls":
        security_options = tls
    elif security == "reality":
        security_options = reality
    result = {
        "server": download["address"], "port": download["port"], "tls": security in {"tls", "reality"},
        "path": settings.get("path", ""), "host": settings.get("host", ""),
        "headers": deepcopy(extra.get("headers", {})), "reuse-settings": clash_reuse(extra.get("xmux", {})),
        "servername": security_options.get("serverName", ""),
        "client-fingerprint": security_options.get("fingerprint", "chrome"),
        # Clash inherits omitted security options from uplink; Xray uses an independent stream.
        "alpn": [], "skip-cert-verify": False, "name-cert-verify": "", "fingerprint": "",
        "certificate": "", "private-key": "", "reality-opts": {}, "ech-opts": {},
    }
    for source, target in (("allowInsecure", "skip-cert-verify"), ("verifyPeerCertByName", "name-cert-verify")):
        if source in tls:
            result[target] = tls[source]
    if "alpn" in tls:
        result["alpn"] = tls["alpn"].split(",") if isinstance(tls["alpn"], str) else deepcopy(tls["alpn"])
    if security == "reality":
        result["reality-opts"] = {
            "public-key": reality.get("password") or reality.get("publicKey", ""),
            "short-id": reality.get("shortId", ""),
        }
    return result


def clash_xhttp(connection):
    inbound = connection.inbound
    result = {key: inbound[key] for key in ("path", "host", "mode") if key in inbound}
    for key, value in inbound.get("_xhttp_extra", {}).items():
        if key == "xmux":
            result["reuse-settings"] = clash_reuse(value)
        elif key == "downloadSettings":
            result["download-settings"] = clash_download(value)
        else:
            name = CLASH_NAMES.get(key, re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", key).lower())
            result[name] = str(value) if key in CLASH_RANGES else deepcopy(value)
    return result
