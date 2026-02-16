#!/usr/bin/env python3
"""
Prompt for node key, guardian details, and Ethereum RPC; write keys and .env.
Run from project root; .env and keys are written to project root.
"""
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
ENV_PATH = os.path.join(ROOT, ".env")
KEYS_PATH = os.path.join(ROOT, "scripts", "keys.json")


def load_env():
    out = {}
    if os.path.isfile(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
    return out


def save_env(env):
    with open(ENV_PATH, "w") as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")


def prompt_private_key():
    sys.path.insert(0, SCRIPT_DIR)
    from generate_wallet import generate_keys, import_key

    while True:
        inp = input(
            "Press [Enter] to create a new wallet, or paste your private key (64 hex chars, optional 0x): "
        ).strip()
        if not inp:
            print("Creating new wallet...")
            generate_keys(KEYS_PATH)
            break
        if re.match(r"^(0x)?[0-9a-fA-F]{64}$", inp):
            print("Importing wallet...")
            import_key(KEYS_PATH, inp)
            break
        print("Invalid key. Use 64 hex characters (optionally prefixed with 0x). Try again.")


def prompt_guardian():
    while True:
        name = input("Guardian name: ").strip()
        if name:
            break
        print("Name cannot be empty.")
    while True:
        website = input("Guardian website: ").strip()
        if website:
            break
        print("Website cannot be empty.")
    return name, website


def prompt_ethereum_rpc():
    default = "https://rpcman.orbs.network/rpc?chain=ethereum&appId=jordanl3test"
    while True:
        inp = input(f"Ethereum RPC URL [{default}]: ").strip() or default
        if re.match(r"https?://.*\..*", inp):
            return inp
        print("Invalid URL. Example: https://.... Try again.")


def main():
    if not sys.stdin.isatty():
        print("Non-interactive run (no TTY). Skipping prompts. Run this script interactively later to set node key and guardian.")
        return 0

    env = load_env()
    if env.get("NODE_PRIVATE_KEY"):
        sys.path.insert(0, SCRIPT_DIR)
        from generate_wallet import node_address_from_private_key
        derived = node_address_from_private_key(env["NODE_PRIVATE_KEY"]).lower()
        current = (env.get("NODE_ADDRESS") or "").replace("0x", "").replace("0X", "").lower()
        if current != derived:
            env["NODE_ADDRESS"] = derived
            save_env(env)
            print(".env already had NODE_PRIVATE_KEY; updated NODE_ADDRESS to match.")
        else:
            print(".env already has NODE_PRIVATE_KEY. Skipping setup prompts.")
        return 0

    print("Setup: node key, guardian details, and Ethereum RPC.\n")

    prompt_private_key()
    import json
    with open(KEYS_PATH) as f:
        keys = json.load(f)

    name, website = prompt_guardian()
    eth_endpoint = prompt_ethereum_rpc()

    env["NODE_PRIVATE_KEY"] = keys["node-private-key"]
    env["NODE_ADDRESS"] = keys["node-address"]
    env["ETHEREUM_ENDPOINT"] = eth_endpoint
    env.setdefault("SIGNER_ENDPOINT", "http://signer:7777")
    env.setdefault("MATIC_ENDPOINT", "https://rpcman.orbs.network/rpc?chain=polygon&appId=jordanl3test")
    env["DOCKER_COMPOSE_FILE"] = os.path.join(ROOT, "docker-compose.yml")
    env["BASE_DIR"] = ROOT

    save_env(env)
    print(f"\nWrote {ENV_PATH}")
    try:
        myip = __import__("urllib.request").request.urlopen("https://ifconfig.me", timeout=5).read().decode().strip()
    except Exception:
        myip = "<your-ip>"
    node_addr = keys["node-address"]
    if not node_addr.startswith("0x"):
        node_addr = "0x" + node_addr
    print("\nGuardian registration:")
    print(f"  https://guardians.orbs.network?name={name}&website={website}&ip={myip}&node_address={node_addr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
