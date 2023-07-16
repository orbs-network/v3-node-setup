#!/usr/bin/python3
import argparse
import json
import os
from secrets import token_bytes

from coincurve import PublicKey
from eth_keys import keys
from eth_utils import to_checksum_address
from sha3 import keccak_256


def store_keys(dest_dir, addr, private_key):
    private_key = private_key[2:] if private_key.startswith('0x') else private_key
    addr = addr[2:] if addr.startswith('0x') else addr
    print('Public address: 0x' + addr)

    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    with open(f"{dest_dir}/keys.json", "w") as f:
        f.write(json.dumps({"node-address": addr, "node-private-key": private_key}))


def generate_keys(dest_dir):
    # https://github.com/pcaversaccio/ethereum-key-generation-python
    private_key = keccak_256(token_bytes(32)).digest()
    public_key = PublicKey.from_valid_secret(private_key).format(compressed=False)[1:]
    addr = keccak_256(public_key).digest()[-20:].hex()

    store_keys(dest_dir, to_checksum_address(addr), private_key.hex())


def import_key(dest_dir, private_key):
    # Convert to bytes if it's a hex string
    if isinstance(private_key, str):
        private_key = bytes.fromhex(private_key[2:] if private_key.startswith('0x') else private_key)

    private_key = keys.PrivateKey(private_key)
    store_keys(dest_dir, private_key.public_key.to_checksum_address(), str(private_key))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--path')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--new_key', action='store_true')
    group.add_argument('--import_key')

    args = parser.parse_args()

    if args.new_key:
        generate_keys(args.path)
    elif args.import_key:
        import_key(args.path, args.import_key)
