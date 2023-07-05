#!/bin/bash

# TODO
# - Do we need sudo?
# - Finalise minimum machine specs
# - Double check cron job gets persisted between reboots

# Color variables
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ----- ENSURE CONFIG VARS FILE IS PRESENT -----
# if [ ! -f ".env" ]; then
#     echo -e "${RED}Please create a config.json file${NC}"
#     echo -e "${RED}Exiting...${NC}"
#     exit 1
# fi

export DEBIAN_FRONTEND=noninteractive

# ----- CHECK MINIMUM MACHINE SPECS -----
echo -e "${BLUE}Checking machine meets minimum hardware requirements...${NC}"
# Min specs
MIN_CPU=4   # in cores
MIN_MEMORY=8   # in GB
MIN_DISK=20 # in GB

# Get current machine specs
CPU=$(nproc --all)
RAM=$(free -g | awk '/^Mem:/{print $2}')
DISK=$(df -BG / | awk 'NR==2{print substr($4, 1, length($4)-1)}')

# Check CPU
if [ $CPU -lt $MIN_CPU ]; then
    echo -e "${RED}Insufficient CPU cores. Required: $MIN_CPU, Available: $CPU.${NC}"
    exit 1
fi

# Check RAM
if [ $RAM -lt $MIN_MEMORY ]; then
    echo -e "${RED}Insufficient memory. Required: $MIN_MEMORY GB, Available: $RAM GB."
    exit 1
fi

# Check Disk
if [ $DISK -lt $MIN_DISK ]; then
    echo -e "${RED}Insufficient Disk space. Required: $MIN_DISK GB, Available: $DISK GB.${NC}"
    exit 1
fi

echo -e "${GREEN}System meets minimum requirements!${NC}"
echo "------------------------------------"

mkdir -p /opt/orbs

#  ----- INSTALL DEPENDENCIES -----
echo -e "${BLUE}Installing dependencies...${NC}"
# TODO: I suspect it is dangerous to run upgrade each time installer script is run
apt-get update -qq && apt-get -y upgrade -qq 
echo -e "${YELLOW}This may take a few minutes. Please wait...${NC}"
apt-get install -qq -y software-properties-common podman docker-compose git cron > /dev/null

# Check if Python is installed
echo -e "${BLUE}Checking if Python is installed...${NC}"
which python3 &> /dev/null

if [ $? -ne 0 ]; then
    echo "${YELLOW}Python is not installed. Installing now...${NC}"
    apt-get install -y software-properties-common python3 python3-pip
else
    echo -e "${GREEN}Python is already installed!${NC}"
fi

echo -e "${BLUE}Checking if Pip is installed...${NC}"
which pip3 &> /dev/null

if [ $? -ne 0 ]; then
    echo "${YELLOW}Pip is not installed. Installing now...${NC}"
    apt-get install -y python3-pip
else
    echo -e "${GREEN}Pip is already installed!${NC}"
fi

pip install -r /home/setup/requirements.txt

systemctl enable cron

# Need to explicitly add docker.io registry
echo "[registries.search]" > /etc/containers/registries.conf && echo "registries = ['docker.io']" >> /etc/containers/registries.conf

# This is needed so Docker Compose can interact with Podman instead of the default Docker daemon
mkdir -p /run/podman
podman system service -t 0 unix:///run/podman/podman.sock &
export DOCKER_HOST=unix:///run/podman/podman.sock

echo -e "${GREEN}Finished installing dependencies!${NC}"
echo "------------------------------------"

# TODO: renable this when we are using 3 seperate repos
# # ----- CLONE DEPLOYMENT (MANIFEST) FILES -----
# echo -e "${BLUE}Downloading node deployment files...${NC}"
# # TODO: this is the wrong repo
# git clone https://github.com/orbs-network/v3-deployment.git deployment
# # Disable detached head warning. This is fine as we are checking out tags
# cd /home/deployment && git config advice.detachedHead false && cd ..

# echo -e "${GREEN}Node deployment files downloaded!${NC}"
# echo "------------------------------------"

# # ----- CLONE MANAGER -----
# echo -e "${BLUE}Downloading node manager...${NC}"
# git clone https://github.com/orbs-network/v3-node-manager.git manager
# cd /home/manager && git config advice.detachedHead false && cd ..

# echo -e "${GREEN}Node manager downloaded!${NC}"
# echo "------------------------------------"

# ----- CREATE ETHEREUM PRIVATE KEYS -----
echo -e "${BLUE}Generating a new Ethereum wallet... ${NC}"
chmod +x /home/setup/generate_new_wallet.py
/home/setup/generate_new_wallet.py /opt/orbs

if [ $? -eq 0 ]; then
  echo -e "${GREEN}Keys were successfully generated and stored under /opt/orbs/keys.json!${NC}"
else
  echo "${RED}generate_new_wallet script failed ${NC}"
fi

echo -e "${GREEN}Ethereum wallet generated!${NC}"
echo "------------------------------------"

# ----- START MANAGER -----
echo -e "${BLUE}Starting manager...${NC}"
cp /home/setup/node-version.json /opt/orbs
python3 /home/manager/manager.py

echo -e "${GREEN}Manager started!${NC}"
echo "------------------------------------"

# ----- SETUP MANAGER CRON -----
echo -e "${BLUE}Adding scheduled manager run...${NC}"

chmod +x /home/manager/manager.py
crontab /home/setup/deployment-poll.cron
service cron restart

echo -e "${GREEN}Manager schedule set!${NC}"
echo "------------------------------------"

echo -e "${GREEN}Installation complete! 🚀🚀🚀${NC}"


