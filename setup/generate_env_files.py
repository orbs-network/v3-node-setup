#!/usr/bin/python3
"""
Get shared.env as input, enrich it, and create .env
"""

import argparse
import json
import os
import re

from dotenv import dotenv_values


def generate_env_files(keys_path, env_dir, shared_env, env_file):
    with open(keys_path) as k:
        keys = json.loads(k.read())

    while True:
        print("Please enter a valid http(s) RPC provider URL for Ethereum (e.g. Infura URL)")
        eth_endpoint = input()
        if re.match(r"https?://.*?\..*?/.*", eth_endpoint):
            break
        print("Invalid URL input. Please try again.")

    conf = dotenv_values(os.path.join(env_dir, shared_env))
    conf["ETHEREUM_ENDPOINT"] = eth_endpoint
    conf["NODE_PRIVATE_KEY"] = keys['node-private-key']

    with open(os.path.join(env_dir, env_file), "w") as env:
        for k, v in conf.items():
            env.write(f"{k}={v}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys")
    parser.add_argument("--env_dir")
    parser.add_argument("--shared")
    parser.add_argument("--env_file")
    args = parser.parse_args()

    generate_env_files(args.keys, args.env_dir, args.shared, args.env_file)
