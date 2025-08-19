#!/bin/bash
#set -x

export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"



echo -e "${BLUE}
      ██████╗ ██████╗ ██████╗ ███████╗
      ██╔═══██╗██╔══██╗██╔══██╗██╔════╝
      ██║   ██║██████╔╝██████╔╝███████╗
      ██║   ██║██╔══██╗██╔══██╗╚════██║
      ╚██████╔╝██║  ██║██████╔╝███████║
       ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝
                                       ${NC}"

# env vars (deployment/.env)
# script directories
source $SCRIPT_DIR/scripts/base.sh
# Check minimum machine specs are met
source $ORBS_ROOT/setup/scripts/validate-min-specs.sh "$@"
# Install necessary dependencies
source $ORBS_ROOT/setup/scripts/install-dependencies.sh "$@"
# Download required node repositories
source $ORBS_ROOT/setup/scripts/clone-repos.sh "$@"
# Generate node address keys
source $ORBS_ROOT/setup/scripts/handle-node-address.sh "$@"
# Collect Guardian details
source $HOME/setup/scripts/handle-guardian-info.sh "$@"
# Generate env files needed for control
source $HOME/setup/scripts/generate-env-files.sh "$@"

# Generate env files needed for control
source $ORBS_ROOT/setup/scripts/generate-env-files.sh "$@"

set -a  # Automatically export all variables
source $ORBS_ROOT/deployment/.env
set +a

# Setup control
source $ORBS_ROOT/setup/scripts/setup-control.sh "$@"

# Perform final health check
source $ORBS_ROOT/setup/scripts/health-check.sh "$@"


