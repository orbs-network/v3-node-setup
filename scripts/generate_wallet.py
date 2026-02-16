#!/usr/bin/env python3
import argparse
import json
import hashlib
from secrets import token_bytes

from coincurve import PublicKey
from eth_hash.auto import keccak


def to_checksum_address(addr):
    if isinstance(addr, bytes):
        addr = addr.hex()
    addr = addr.lower().replace("0x", "")
    if len(addr) != 40:
        raise ValueError("Address must be 40 hex chars")
    hash_bytes = keccak(addr.encode())
    out = []
    for i, c in enumerate(addr):
        if c in "0123456789":
            out.append(c)
        else:
            nibble = (hash_bytes[i // 2] >> (4 if i % 2 == 0 else 0)) & 0xF
            out.append(c.upper() if nibble >= 8 else c.lower())
    return "0x" + "".join(out)


def _address_from_public_key_64(public_key_64_bytes):
    return keccak(public_key_64_bytes)[-20:].hex()


def node_address_from_private_key(private_key_hex):
    if isinstance(private_key_hex, str):
        private_key_hex = private_key_hex.strip()
        if private_key_hex.startswith("0x"):
            private_key_hex = private_key_hex[2:]
        private_key = bytes.fromhex(private_key_hex)
    else:
        private_key = private_key_hex
    public_key = PublicKey.from_valid_secret(private_key).format(compressed=False)[1:]
    return _address_from_public_key_64(public_key)


def store_keys(dest_path, addr, private_key):
    private_key = private_key[2:] if private_key.startswith("0x") else private_key
    addr = addr[2:] if addr.startswith("0x") else addr
    print("Public address: 0x" + addr)

    with open(dest_path, "w") as f:
        f.write(json.dumps({"node-address": addr, "node-private-key": private_key}))


def generate_keys(dest_path):
    private_key = hashlib.sha3_256(token_bytes(32)).digest()
    public_key = PublicKey.from_valid_secret(private_key).format(compressed=False)[1:]
    addr = _address_from_public_key_64(public_key)
    store_keys(dest_path, to_checksum_address(addr), private_key.hex())


def import_key(dest_path, private_key):
    if isinstance(private_key, str):
        private_key = bytes.fromhex(
            private_key[2:] if private_key.startswith("0x") else private_key
        )
    public_key = PublicKey.from_valid_secret(private_key).format(compressed=False)[1:]
    addr = _address_from_public_key_64(public_key)
    store_keys(dest_path, to_checksum_address(addr), private_key.hex())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--new_key", action="store_true")
    group.add_argument("--import_key")
    args = parser.parse_args()

    if args.new_key:
        generate_keys(args.path)
    else:
        import_key(args.path, args.import_key)
