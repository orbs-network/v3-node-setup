#!/bin/bash
#set -x

export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source $SCRIPT_DIR/base.sh

echo -e "${BLUE}
      ██████╗ ██████╗ ██████╗ ███████╗
      ██╔═══██╗██╔══██╗██╔══██╗██╔════╝
      ██║   ██║██████╔╝██████╔╝███████╗
      ██║   ██║██╔══██╗██╔══██╗╚════██║
      ╚██████╔╝██║  ██║██████╔╝███████║
       ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝
                                       ${NC}"

# Check minimum machine specs are met
source $ORBS_ROOT/setup/scripts/validate-min-specs.sh "$@"
# Install necessary dependencies
source $ORBS_ROOT/setup/scripts/install-dependencies.sh "$@"
# Download required node repositories
source $ORBS_ROOT/setup/scripts/clone-repos.sh "$@"
# Generate node address keys
source $ORBS_ROOT/setup/scripts/handle-node-address.sh "$@"
# Collect Guardian details
source $ORBS_ROOT/setup/scripts/handle-guardian-info.sh "$@"
# Generate env files needed for manager
source $ORBS_ROOT/setup/scripts/generate-env-files.sh "$@"

set -a  # Automatically export all variables
source $ORBS_ROOT/deployment/.env
set +a

# Setup manager
source $ORBS_ROOT/setup/scripts/setup-manager.sh "$@"
# Perform final health check
source $ORBS_ROOT/setup/scripts/health-check.sh "$@"


