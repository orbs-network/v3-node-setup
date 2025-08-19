# v3-node-setup repo

**⚠️ WIP ⚠️**

[![smoke-test](https://github.com/orbs-network/v3-node-setup/actions/workflows/smoke-test.yml/badge.svg)](https://github.com/orbs-network/v3-node-setup/actions/workflows/smoke-test.yml)

## What's this?

This repo is temporarily being used to hold all the Orbs v3 node validator install, control and deployment files. In the future, they will be split into different repos

## Folders

- `deployment` - Manifest files. 
- `control` - Validator Python control (manager) which replaced boyar. 
- `setup` - Install scripts. 
- `logging` - A service to expose container logs. These files will also live elsewhere in the future TBD

## Developing

### Running interactively

1. `docker build -t test-ubuntu .`
2. ```
      docker run \
         -v $(pwd)/deployment:/home/ubuntu/deployment \
         -v $(pwd)/logging:/home/ubuntu/logging \
         -v $(pwd)/control:/home/ubuntu/control \
         -v $(pwd)/setup:/home/ubuntu/setup \
         -p 80:80 --rm -it --privileged test-ubuntu
   ```
   (Use volumes to allow us to make changes outside the container)
3. `source ./setup/install.sh`

### Running non-interactively

1. `docker build -t test-ubuntu .`
2. `docker run -p 80:80 -e ETH_ENDPOINT=YOUR-INFURA-ENDPOINT --rm --privileged test-ubuntu /bin/bash -c "source ./setup/install.sh"` (this will immediately exit the container after completion)

### Install flags for dev

- `--skip-req`: Skip minimum machine spec requirement checks
- `--verbose`: Display detailed logging output
- `--new-keys`: Reprompt for wallet keys

### Sanity

From Mac host, run `curl http://localhost/service/ethereum-reader/status`

### Exposed URLs

#### Management service

- **status**: http://localhost/service/ethereum-reader/status
- **logs**: http://localhost/service/ethereum-reader/logs

### Troubleshooting

#### Healthcheck always shows "starting"

[Podman uses systemd timers to run healtchecks periodically](https://github.com/containers/podman/issues/19326), which do not work in our dev Docker-in-Docker setup. As a workaround, you can run the command [`podman healthcheck run SERVICE`](https://docs.podman.io/en/v4.4/markdown/podman-healthcheck-run.1.html) to manually run a specific container healthcheck.


# New version - jordan notes: -

Run locally on MacOS:  

Build the dev guardian image:

```make build_docker_dev```

Run the dev guardian image:

```make run_docker_dev```

Run the installation script after getting docker container prompt:

```source ./orbs-node-on-host/setup/install.sh --skip-req```

Inside the container, playing with docker-compose, make sure to run the dc command, not docker-compose, it's
an alias to docker-compose with mapping to the right docker-compose-dev.yml if any.

```dc up -d``` for example.

To synchronize changes made by local host to the container (e.g. after modifying a file in the host), run:

```sync```



