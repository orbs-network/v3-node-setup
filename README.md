# v3-node-setup

## One-liner installation (with prompts)

Use this when you want to run the installer interactively so you can enter your node key, guardian details, and Ethereum RPC when prompted.

Download the script, then run it with sudo (so your terminal is used for input):

```bash
curl -sSL https://github.com/orbs-network/v3-node-setup/raw/main/install.sh -o /tmp/install.sh && sudo bash /tmp/install.sh
```

During setup you will be prompted for:

- **Node key**: press Enter to create a new wallet, or paste an existing private key (64 hex chars, optional `0x` prefix).
- **Guardian name** and **Guardian website**.
- **Ethereum RPC URL** (a default is suggested).

The installer clones the repo to `/opt/orbs/v3-node-setup`, installs dependencies (Docker, Docker Compose, Python, build tools), creates a `.env` and keys, and starts the stack with Docker Compose.

### Using a different branch

```bash
curl -sSL https://github.com/orbs-network/v3-node-setup/raw/BRANCH/install.sh -o /tmp/install.sh && sudo BRANCH=BRANCH bash /tmp/install.sh
```

Example for branch `feature/v5-ready`:

```bash
curl -sSL https://github.com/orbs-network/v3-node-setup/raw/feature/v5-ready/install.sh -o /tmp/install.sh && sudo BRANCH=feature/v5-ready bash /tmp/install.sh
```

### Custom install directory

```bash
sudo INSTALL_DIR=/opt/my-node bash /tmp/install.sh
```

### Non-interactive (no prompts)

If you run the installer with a pipe (e.g. `curl ... | sudo bash`), there is no TTY for prompts. The installer will skip the key/guardian prompts. After the install finishes, SSH in and run the setup script interactively to configure:

```bash
sudo /opt/orbs/v3-node-setup/scripts/venv/bin/python3 /opt/orbs/v3-node-setup/scripts/prompt_and_env.py
```
