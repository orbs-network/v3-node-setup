#!/bin/bash

source $HOME/setup/scripts/base.sh

echo -e "${BLUE}
      ██████╗ ██████╗ ██████╗ ███████╗
      ██╔═══██╗██╔══██╗██╔══██╗██╔════╝
      ██║   ██║██████╔╝██████╔╝███████╗
      ██║   ██║██╔══██╗██╔══██╗╚════██║
      ╚██████╔╝██║  ██║██████╔╝███████║
       ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝
                                       ${NC}"

# Check minimum machine specs are met
source $HOME/setup/scripts/validate-min-specs.sh "$@"
# Install necessary dependencies
source $HOME/setup/scripts/install-dependencies.sh "$@"
# Download required node repositories
source $HOME/setup/scripts/clone-repos.sh "$@"
# Generate node address keys
source $HOME/setup/scripts/handle-node-address.sh "$@"
# Collect Guardian details
source $HOME/setup/scripts/handle-guardian-info.sh "$@"
# Generate env files needed for manager
source $HOME/setup/scripts/generate-env-files.sh "$@"
# Setup manager
source $HOME/setup/scripts/setup-manager.sh "$@"
# Perform final health check
source $HOME/setup/scripts/health-check.sh "$@"
