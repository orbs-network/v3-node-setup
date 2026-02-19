#!/usr/bin/env python3
"""
Prompt for node key, guardian details, and Ethereum RPC; write keys and .env.
Run from project root; .env and keys are written to project root.
"""
import os
import re
import sys

GREEN = "\033[0;32m"
BLUE = "\033[0;34m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
RST = "\033[0m"

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
            f"{BLUE}Press [Enter] to create a new wallet, or paste your private key (64 hex chars, optional 0x):{RST} "
        ).strip()
        if not inp:
            print(f"{GREEN}Creating new wallet...{RST}")
            generate_keys(KEYS_PATH)
            break
        if re.match(r"^(0x)?[0-9a-fA-F]{64}$", inp):
            print(f"{GREEN}Importing wallet...{RST}")
            import_key(KEYS_PATH, inp)
            break
        print(f"{RED}Invalid key. Use 64 hex characters (optionally prefixed with 0x). Try again.{RST}")


def prompt_guardian():
    while True:
        name = input(f"{BLUE}Guardian name:{RST} ").strip()
        if name:
            break
        print(f"{RED}Name cannot be empty.{RST}")
    while True:
        website = input(f"{BLUE}Guardian website:{RST} ").strip()
        if website:
            break
        print(f"{RED}Website cannot be empty.{RST}")
    return name, website


def prompt_ethereum_rpc():
    default = "https://rpcman.orbs.network/rpc?chain=ethereum&appId=jordanl3test"
    while True:
        inp = input(f"{BLUE}Ethereum RPC URL{RST} [{default}]: ").strip() or default
        if re.match(r"https?://.*\..*", inp):
            return inp
        print(f"{RED}Invalid URL. Example: https://.... Try again.{RST}")


def main():
    if not sys.stdin.isatty():
        print(f"{YELLOW}Non-interactive run (no TTY). Skipping prompts. Run this script interactively later to set node key and guardian.{RST}")
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
            print(f"{GREEN}.env already had NODE_PRIVATE_KEY; updated NODE_ADDRESS to match.{RST}")
        else:
            print(f"{GREEN}.env already has NODE_PRIVATE_KEY. Skipping setup prompts.{RST}")
        return 0

    print(f"{BLUE}Setup: node key, guardian details, and Ethereum RPC.{RST}\n")

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
    print(f"\n{GREEN}Wrote {ENV_PATH}{RST}")
    try:
        myip = __import__("urllib.request").request.urlopen("https://ifconfig.me", timeout=5).read().decode().strip()
    except Exception:
        myip = "<your-ip>"
    node_addr = keys["node-address"]
    if not node_addr.startswith("0x"):
        node_addr = "0x" + node_addr
    print(f"\n{GREEN}Guardian registration:{RST}")
    print(f"  https://guardians.orbs.network?name={name}&website={website}&ip={myip}&node_address={node_addr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
