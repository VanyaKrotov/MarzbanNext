"""FinalMask contract shared by host validation and the Monaco capabilities schema.

The registry follows Xray's TCP/UDP loaders, rather than the less complete docs table.
Native file access, Lua execution and peer handshakes remain the client core's responsibility.
"""

from typing import Annotated, Literal, Union

from pydantic import ConfigDict, Field, create_model

from .common import MaskOptions, XRAY_REVISION, XRAY_SOURCE
from .masks import Filter, Fragment, MkcpLegacy, Realm, Salamander, Sudoku, UDPHop, XDNS, XICMP, XMC
from .packets import Noise, TCPHeader, UDPHeader
from .quic import QuicParams


def mask_variant(name: str, mask_type: str, settings: type[MaskOptions], *, required=False):
    """Give each loader its own settings definition so completion follows the type discriminator."""
    return create_model(
        name,
        __base__=MaskOptions,
        __doc__=settings.__doc__,
        type=(Literal[mask_type], Field(description=f"Xray mask loader: {mask_type}.")),
        settings=(settings if required else settings | None, Field(
            ... if required else None, description=f"{mask_type} settings. {settings.__doc__}")),
    )


FilterMask = mask_variant("FilterMask", "filter", Filter)
TCPHeaderMask = mask_variant("TCPHeaderMask", "header-custom", TCPHeader)
UDPHeaderMask = mask_variant("UDPHeaderMask", "header-custom", UDPHeader)
FragmentMask = mask_variant("FragmentMask", "fragment", Fragment, required=True)
SudokuMask = mask_variant("SudokuMask", "sudoku", Sudoku)
XMCMask = mask_variant("XMCMask", "xmc", XMC, required=True)
MkcpLegacyMask = mask_variant("MkcpLegacyMask", "mkcp-legacy", MkcpLegacy)
NoiseMask = mask_variant("NoiseMask", "noise", Noise)
SalamanderMask = mask_variant("SalamanderMask", "salamander", Salamander)
XDNSMask = mask_variant("XDNSMask", "xdns", XDNS)
XICMPMask = mask_variant("XICMPMask", "xicmp", XICMP)
RealmMask = mask_variant("RealmMask", "realm", Realm, required=True)
UDPHopMask = mask_variant("UDPHopMask", "udphop", UDPHop, required=True)

TCPMask = Annotated[Union[FilterMask, TCPHeaderMask, FragmentMask, SudokuMask, XMCMask], Field(discriminator="type")]
UDPMask = Annotated[Union[
    FilterMask, UDPHeaderMask, MkcpLegacyMask, NoiseMask, SalamanderMask, SudokuMask,
    XDNSMask, XICMPMask, RealmMask, UDPHopMask,
], Field(discriminator="type")]


class FinalMask(MaskOptions):
    """Xray final stream masking. Arrays run from the innermost layer to the outermost layer."""

    model_config = ConfigDict(json_schema_extra={
        "$comment": f"Xray loader definitions at {XRAY_SOURCE} (revision {XRAY_REVISION}).",
        "defaultSnippets": [{
            "label": "TCP: TLS ClientHello fragmentation",
            "description": "Fragment the TLS ClientHello into chunks of 100-200 bytes.",
            "body": {"tcp": [{"type": "fragment", "settings": {
                "packets": "tlshello", "lengths": ["100-200"], "delays": ["10-20"],
            }}]},
        }, {
            "label": "UDP: Salamander",
            "description": "Requires a matching Salamander password on the peer.",
            "body": {"udp": [{"type": "salamander", "settings": {"password": "change-me"}}]},
        }, {
            "label": "UDP: noise expressions",
            "description": "A fixed prefix, random bytes and timestamp, sent by a compatible Xray core.",
            "body": {"udp": [{"type": "noise", "settings": {"noise": [{
                "type": "exp", "packet": "<b 0001><r 8-16><t>", "delay": "10-20",
            }]}}]},
        }],
    })
    tcp: list[TCPMask] | None = Field(None, description=(
        "TCP masks, innermost first: filter, header-custom, fragment, sudoku, xmc. "
        "Requires a client core supporting each selected mask."))
    udp: list[UDPMask] | None = Field(None, description=(
        "UDP masks, innermost first: filter, header-custom, mkcp-legacy, noise, salamander, sudoku, "
        "xdns, xicmp, realm, udphop. Peer settings must match where required."))
    quicParams: QuicParams | None = Field(
        None, description="QUIC tuning for compatible Xray transports; no effect on ordinary TCP.")


__all__ = ["FinalMask"]
