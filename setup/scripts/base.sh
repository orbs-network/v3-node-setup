#!/bin/bash

# Color variables
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

export DEBIAN_FRONTEND=noninteractive
export PIP_ROOT_USER_ACTION=ignore

# Handle verbose flag
redirect="/dev/null"
if [[ $* == *--verbose* || $* == *-v* ]]; then
  redirect="/dev/stdout"
fi

username=$(whoami)

# Prevent system from killing user's processes on logout
loginctl enable-linger $username # This errors when running in Docker container - ignore

sudo mkdir -p /opt/orbs
sudo chown -R $username:$username /opt/orbs/
sudo chmod -R 755 /opt/orbs/

if [ -f /.dockerenv ]; then
  export RUNNING_IN_DOCKER=true
fi

if [ "$RUNNING_IN_DOCKER" = "true" ]; then
 echo -e "${YELLOW} Running in Docker container ! ${NC}"

 export ORBS_ROOT=$HOME/orbs-node
 git clone $HOME/orbs-node-on-host $ORBS_ROOT
 rsync -aq --progress --exclude='.venv' --exclude='.git' $HOME/orbs-node-on-host/ $ORBS_ROOT
else
  echo -e "${YELLOW} Running on host ! ${NC}"

  export ORBS_ROOT=`git rev-parse --show-toplevel`
fi

echo -e "${BLUE} ORBS_ROOT: $ORBS_ROOT ${NC}"

export DOCKER_COMPOSE_FILE=$ORBS_ROOT/deployment/docker-compose.yml

set -a  # Automatically export all variables
if [ -f $ORBS_ROOT/deployment/.env ]; then
  . $ORBS_ROOT/deployment/.env
fi
set +a







