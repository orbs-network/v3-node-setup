"""identity tests"""

import json
from pathlib import Path

import pytest

import identity

TOPOLOGY = {
    "Payload": {
        "CurrentTopology": [
            {"EthAddress": "0874bc1383958e2475df73dc68c4f09658e23777", "OrbsAddress": "067a8afdc6d7bafa0ccaa5bb2da867f454a34dfa", "Name": "Wings"},
            {"EthAddress": "0c56b39184e22249e35efcb9394872f0d025256b", "OrbsAddress": "255c1f6c4da768dfd31f27057d38b84de41bcd4d", "Name": "AngelSong"},
        ]
    }
}


@pytest.fixture(autouse=True)
def topology_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points the resolver at a topology this test controls"""

    path = tmp_path / "status.json"
    path.write_text(json.dumps(TOPOLOGY), encoding="utf8")
    monkeypatch.setattr(identity, "topology_status_file", str(path))

    return path


def test_node_address_gets_the_missing_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the address stored without 0x is reported with it"""

    # generate_wallet.py strips the prefix before storing, but consumers expect one.
    monkeypatch.setenv("NODE_ADDRESS", "481029997EFfD67A74b48C98D763e2a2147e68A6")

    assert identity.get_node_address() == "0x481029997EFfD67A74b48C98D763e2a2147e68A6"


def test_node_address_keeps_an_existing_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an address already carrying 0x is not given a second one"""

    monkeypatch.setenv("NODE_ADDRESS", "0xabc123")

    assert identity.get_node_address() == "0xabc123"


def test_node_address_preserves_checksum_casing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the EIP-55 mixed case survives"""

    monkeypatch.setenv("NODE_ADDRESS", "481029997EFfD67A74b48C98D763e2a2147e68A6")

    assert identity.get_node_address().endswith("EFfD67A74b48C98D763e2a2147e68A6")


def test_a_missing_node_address_reports_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an unconfigured node reports an empty address rather than raising"""

    monkeypatch.delenv("NODE_ADDRESS", raising=False)

    assert identity.get_node_address() == ""


def test_a_registered_node_resolves_its_eth_address() -> None:
    """Test that a node present in the topology reports the paired eth address"""

    # The topology holds OrbsAddress lowercase and unprefixed; NODE_ADDRESS is EIP-55
    # mixed case, so the match has to survive both differences.
    eth, registration = identity.resolve_eth_address("0x067A8AFDC6D7BAFA0CCAA5BB2DA867F454A34DFA")

    assert eth == "0x0874bc1383958e2475df73dc68c4f09658e23777"
    assert registration == identity.REGISTERED


def test_a_node_absent_from_the_topology_is_unregistered() -> None:
    """Test that a node not on chain is reported as unregistered rather than unknown"""

    eth, registration = identity.resolve_eth_address("0x481029997EFfD67A74b48C98D763e2a2147e68A6")

    assert eth == ""
    assert registration == identity.UNREGISTERED


def test_an_unreadable_topology_is_unknown_not_unregistered(topology_file: Path) -> None:
    """Test that failing to read the network is not reported as being absent from it"""

    # These mean different things to an operator: one is "you are not registered", the
    # other is "we could not tell".
    topology_file.unlink()

    eth, registration = identity.resolve_eth_address("0x481029997EFfD67A74b48C98D763e2a2147e68A6")

    assert eth == ""
    assert registration == identity.UNKNOWN


def test_a_malformed_topology_is_unknown(topology_file: Path) -> None:
    """Test that unparseable network data is reported as unknown"""

    topology_file.write_text("not json", encoding="utf8")

    assert identity.resolve_eth_address("0xabc")[1] == identity.UNKNOWN


def test_an_unconfigured_node_cannot_be_resolved() -> None:
    """Test that having no node address yields unknown rather than unregistered"""

    assert identity.resolve_eth_address("") == ("", identity.UNKNOWN)
