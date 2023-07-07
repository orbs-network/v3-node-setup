# v3-node-setup repo

WIP

## What's this?

This repo is temporarily being used to hold all the Orbs v3 node validator install, manager and deployment files. In the future, they will be split into different repos

## Folders

- `deployment` - Manifest files. These will eventually live at https://github.com/orbs-network/v3-deployment
- `manager` - Python manager. These will eventually live at https://github.com/orbs-network/v3-node-manager
- `setup` - Install scripts. These files will eventually live by themselves in this current repo (https://github.com/orbs-network/v3-node-setup)

## Developing

1. `docker build -t test-ubuntu .`
2. `docker run -p 80:80 --rm -it --privileged test-ubuntu`
3. `source ./setup/install.sh`

### Exposed URLs

#### Management service

1. **status**: http://localhost/services/management-service/status
