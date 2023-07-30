#!/usr/bin/python3
"""
Get public.env as input, enrich it, and create private.env
Also creates config.json for backward compatibility - will be deprecated
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
        print("Please enter a valid http(s) RPC provider URL for Ethereum (e.g. Infura URL)")
        eth_endpoint = input()
        if re.match(r'https?://.*?\..*?/.*', eth_endpoint):
            break
        print("Invalid URL input. Please try again.")

    public_conf = dotenv_values(os.path.join(env_dir, "public.env"))
    matic_endpoint = public_conf["MATIC_ENDPOINT"]

    with open(os.path.join(env_dir, public_env), "a+") as pub:
        text = pub.read()
        if not text.endswith("\n"):
            pub.write("\n")
        pub.write(f"NODE_ADDRESS={keys['node-address']}")

    with open(os.path.join(env_dir, private_env), "w") as priv:
        priv.write(f"ETH_ENDPOINT={eth_endpoint}\n")
        priv.write(f"PRIVATE_KEY={keys['node-private-key']}")


    ####################################### TODO: deprecate
    config = {
        "BootstrapMode": False,
        "DeploymentDescriptorUrl": "https://amihaz.github.io/staging-deployment/staging.json",
        "ElectionsAuditOnly": True,
        "EthereumEndpoint": eth_endpoint,
        "MaticEndpoint": matic_endpoint,
        "node-address": keys["node-address"]
    }

    with open(os.path.join(os.environ.get("HOME", "/home/ubuntu"), "setup/config.json"), "w") as f:
        f.write(json.dumps(config, indent=4))
    print("Successfully stored configuration file in config.json")
    #######################################


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--keys')
    parser.add_argument('--env_dir')
    parser.add_argument('--public')
    parser.add_argument('--private')
    args = parser.parse_args()

    generate_env_files(args.keys, args.env_dir, args.public, args.private)
