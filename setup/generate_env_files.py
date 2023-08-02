#!/usr/bin/python3
"""
Get public.env as input, enrich it, and create private.env
"""

import argparse
import json
import os
import re

from dotenv import dotenv_values


def generate_env_files(keys_path, env_dir, public_env, private_env):
    with open(keys_path) as k:
        keys = json.loads(k.read())

    while True:
        print(
            "Please enter a valid http(s) RPC provider URL for Ethereum (e.g. Infura URL)"
        )
        eth_endpoint = input()
        if re.match(r"https?://.*?\..*?/.*", eth_endpoint):
            break
        print("Invalid URL input. Please try again.")

    public_conf = dotenv_values(os.path.join(env_dir, "public.env"))
    matic_endpoint = public_conf["MATIC_ENDPOINT"]

    with open(os.path.join(env_dir, public_env), "a+") as pub:
        text = pub.read()
        if not text.endswith("\n"):
            pub.write("\n")
        pub.write(f"NODE_ADDRESS={keys['node-address']}")

    # TODO: don't hardcode. Sort into public/private env vars
    private_env_vars = [
        # MANAGEMENT_SERVICE
        f"ETHEREUM_ENDPOINT={eth_endpoint}\n",
        # ETHEREUM_WRITER
        "MANAGEMENT_SERVICE_ENDPOINT=management-service",
        "SIGNER_ENDPOINT=signer",
        "ETHEREUM_ELECTIONS_CONTRACT=0x02Ca9F2c5dD0635516241efD480091870277865b",
        f"NODE_ORBS_ADDRESS={keys['node-address']}",  # TODO: rename this to NODE_ADDRESS
        "MANAGEMENT_SERVICE_ENDPOINT_SCHEMA=nginx/service/management-service/status"
        # SIGNER
        f"NODE_PRIVATE_KEY={keys['node-private-key']}",
        "HTTP_ADDRESS=:80",
    ]

    with open(os.path.join(env_dir, private_env), "w") as priv:
        for env_var in private_env_vars:
            priv.write(env_var + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys")
    parser.add_argument("--env_dir")
    parser.add_argument("--public")
    parser.add_argument("--private")
    args = parser.parse_args()

    generate_env_files(args.keys, args.env_dir, args.public, args.private)
