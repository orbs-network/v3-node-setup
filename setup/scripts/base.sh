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