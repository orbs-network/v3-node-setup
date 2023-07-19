# v3-node-setup repo

**⚠️ WIP ⚠️**

## What's this?

This repo is temporarily being used to hold all the Orbs v3 node validator install, manager and deployment files. In the future, they will be split into different repos

## Folders

- `deployment` - Manifest files. These will eventually live at https://github.com/orbs-network/v3-deployment
- `manager` - Validator Python manager. These files will eventually live at https://github.com/orbs-network/v3-node-manager
- `setup` - Install scripts. These files will eventually live by themselves in this current repo (https://github.com/orbs-network/v3-node-setup)
- `logging` - A service to expose container logs. These files will also live elsewhere in the future TBD

## Developing

**❗ For current backwards compatibility, ensure you have created a `config.json` inside the `setup` folder. See `config_example.json` for more details.**

1. `docker build -t test-ubuntu .`
2. `docker run -p 80:80 --rm -it --privileged test-ubuntu`
3. `source ./setup/install.sh --skip-req`

### Install flags for dev

- `--skip-req`: Skip minimum machine spec requirement checks
- `--verbose`: Display detailed logging output

### Sanity

From Mac host, run `curl http://localhost/service/management-service/status`

### Exposed URLs

#### Management service

- **status**: http://localhost/service/management-service/status
- **logs**: http://localhost/service/management-service/logs
