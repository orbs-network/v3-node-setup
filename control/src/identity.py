"""Resolves the addresses this node runs as.

A node installation establishes only a node address. Its coupling to an eth address - the
guardian identity - happens on chain, so it can only be read back from the network view
the management service maintains. Nothing local knows it.
"""

import json
import os

from config import BASE_DIR
from logger import logger

# The ethereum-reader (management service) writes the network view here. CurrentTopology
# is the active network, each entry pairing an OrbsAddress with its EthAddress.
topology_status_file = os.path.join(BASE_DIR, ".data", "ethereum-reader", "status.json")

REGISTERED = "registered"
UNREGISTERED = "unregistered"
UNKNOWN = "unknown"


def _with_prefix(address: str) -> str:
    """Returns the address with a 0x prefix, leaving EIP-55 casing untouched"""

    return address if not address or address.startswith("0x") else f"0x{address}"


def bare_address(address: str) -> str:
    """Returns the address lowercased and unprefixed, for comparing two spellings of one address"""

    return address.lower().removeprefix("0x")


def get_node_address() -> str:
    """Returns the address this node runs as, or an empty string when it is not configured"""

    address = os.getenv("NODE_ADDRESS", "").strip()

    if not address:
        logger.error("NODE_ADDRESS is not set, reporting an empty node address")
        return ""

    # scripts/generate_wallet.py stores the address without the prefix, while everything
    # that consumes one expects it. The mixed case is an EIP-55 checksum, left as it is.
    return _with_prefix(address)


def resolve_eth_address(node_address: str) -> tuple[str, str]:
    """Returns this node's eth address and whether it is registered on chain.

    Args:
        node_address: The address this node runs as.

    Returns:
        The eth address (empty unless registered), and one of `registered`,
        `unregistered` or `unknown`.
    """

    if not node_address:
        return "", UNKNOWN

    try:
        with open(topology_status_file, encoding="utf8") as file:
            topology = json.load(file)["Payload"]["CurrentTopology"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Being unable to read the network is not the same as being absent from it, and
        # must not be reported as though the node were definitely unregistered.
        logger.error("Could not read the network topology: %s", error)
        return "", UNKNOWN

    # The topology carries neither address with a 0x prefix and holds OrbsAddress in
    # lowercase, while NODE_ADDRESS is EIP-55 mixed case, so both have to be normalised.
    wanted = bare_address(node_address)

    for entry in topology:
        if bare_address(entry.get("OrbsAddress", "")) == wanted:
            return _with_prefix(entry.get("EthAddress", "")), REGISTERED

    return "", UNREGISTERED
