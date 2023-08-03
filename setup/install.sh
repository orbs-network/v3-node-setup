#!/bin/bash

# TODO
# - Finalise minimum machine specs
# - Double check cron job gets persisted between reboots

# Color variables
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}
      ██████╗ ██████╗ ██████╗ ███████╗
      ██╔═══██╗██╔══██╗██╔══██╗██╔════╝
      ██║   ██║██████╔╝██████╔╝███████╗
      ██║   ██║██╔══██╗██╔══██╗╚════██║
      ╚██████╔╝██║  ██║██████╔╝███████║
       ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝
                                       ${NC}"

current_user=$(whoami)

export DEBIAN_FRONTEND=noninteractive

# HANDLE VERBOSE FLAG
redirect="/dev/null"
if [[ $* == *--verbose* || $* == *-v* ]]; then
  redirect="/dev/stdout"
fi

# ----- CHECK MINIMUM MACHINE SPECS -----

if [[ ! $* == *--skip-req* ]]; then
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
        echo -e "${RED}Insufficient memory. Required: $MIN_MEMORY GB, Available: $RAM GB.${NC}"
        exit 1
    fi

    # Check Disk
    if [ $DISK -lt $MIN_DISK ]; then
        echo -e "${RED}Insufficient Disk space. Required: $MIN_DISK GB, Available: $DISK GB.${NC}"
        exit 1
    fi

    echo -e "${GREEN}System meets minimum requirements!${NC}"
    echo "------------------------------------"
fi # end reqs

sudo mkdir -p /opt/orbs
sudo chown -R $current_user:$current_user /opt/orbs/
sudo chmod -R 755 /opt/orbs/

#  ----- INSTALL DEPENDENCIES -----
echo -e "${BLUE}Installing dependencies...${NC}"
# TODO: I suspect it is dangerous to run upgrade each time installer script is run
if [ -f /etc/needrestart/needrestart.conf ]; then
  sudo sed -i "s/#\$nrconf{restart} = 'i';/\$nrconf{restart} = 'a';/" /etc/needrestart/needrestart.conf # disables the restart modal
fi
sudo apt-get update -qq && sudo apt-get -y upgrade -qq > "$redirect" 2>&1
echo -e "${YELLOW}This may take a few minutes. Please wait...${NC}"
sudo apt-get install -qq -y software-properties-common podman curl git cron > "$redirect" 2>&1
echo -e "${BLUE}$(podman --version)${NC}"
# https://docs.docker.com/compose/install/standalone/
sudo curl -SL https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
echo -e "${BLUE}$(docker-compose --version)${NC}"

# TODO: remove this conditional. This is only here as systemctl is not available in Docker containers
if [ -f /.dockerenv ]; then
    echo -e "${YELLOW}Running in Docker container${NC}"
    mkdir -p ~/.local/run/podman
    # Start Podman service as current user, not root
    podman system service -t 0 unix://$HOME/.local/run/podman/podman.sock &> /dev/null &
    echo 'export DOCKER_HOST=unix://'$HOME'/.local/run/podman/podman.sock' >> ~/.bashrc
    echo 'export PODMAN_SOCKET_PATH='$HOME'/.local/run/podman/podman.sock' >> ~/.bashrc
else
    echo -e "${YELLOW}Not running in Docker container${NC}"
    # https://bugs.launchpad.net/ubuntu/+source/libpod/+bug/2024394/comments/4
    curl -O http://archive.ubuntu.com/ubuntu/pool/universe/g/golang-github-containernetworking-plugins/containernetworking-plugins_1.1.1+ds1-1_amd64.deb
    sudo dpkg -i containernetworking-plugins_1.1.1+ds1-1_amd64.deb
    systemctl --user start podman.socket
    echo 'export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock' >> ~/.bashrc
    echo 'export PODMAN_SOCKET_PATH=$XDG_RUNTIME_DIR/podman/podman.sock' >> ~/.bashrc
    echo 'net.ipv4.ip_unprivileged_port_start=80' | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
fi

echo "alias docker=podman" >> ~/.bashrc
source ~/.bashrc

# Update Podman log settings
podman_conf_path="/usr/share/containers/containers.conf"
sudo sed -i 's/#log_driver = "k8s-file"/log_driver = "k8s-file"/' "$podman_conf_path"
sudo sed -i 's/#log_size_max = -1/log_size_max = 10485760/' "$podman_conf_path"
echo "Updated Podman container.conf settings"

# Check if Python is installed
echo -e "${BLUE}Checking if Python is installed...${NC}"
which python3 &> /dev/null

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Python is not installed. Installing now...${NC}"
    sudo apt-get install -y software-properties-common python3 python3-pip > "$redirect" 2>&1
else
    echo -e "${GREEN}Python is already installed!${NC}"
fi

echo -e "${BLUE}Checking if Pip is installed...${NC}"
which pip3 &> /dev/null

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Pip is not installed. Installing now...${NC}"
    sudo apt-get install -y python3-pip > "$redirect" 2>&1
else
    echo -e "${GREEN}Pip is already installed!${NC}"
fi

sudo pip install -r $HOME/setup/requirements.txt --root-user-action=ignore

sudo systemctl enable cron

# Need to explicitly add docker.io registry
echo "[registries.search]" | sudo tee /etc/containers/registries.conf
echo "registries = ['docker.io']" | sudo tee -a /etc/containers/registries.conf

echo -e "${GREEN}Finished installing dependencies!${NC}"
echo "------------------------------------"

# TODO: renable this when we are using 3 seperate repos
# # ----- CLONE DEPLOYMENT (MANIFEST) FILES -----
# echo -e "${BLUE}Downloading node deployment files...${NC}"
# # TODO: this is the wrong repo
# git clone https://github.com/orbs-network/v3-deployment.git deployment
# # Disable detached head warning. This is fine as we are checking out tags
# cd $HOMEdeployment && git config advice.detachedHead false && cd ..

# echo -e "${GREEN}Node deployment files downloaded!${NC}"
# echo "------------------------------------"

# # ----- CLONE MANAGER -----
# echo -e "${BLUE}Downloading node manager...${NC}"
# git clone https://github.com/orbs-network/v3-node-manager.git manager
# cd $HOMEmanager && git config advice.detachedHead false && cd ..

# echo -e "${GREEN}Node manager downloaded!${NC}"
# echo "------------------------------------"

# ----- NODE ADDRESS GENERATION -----
keys_path=/opt/orbs/keys.json

if [[ ! -f $keys_path || $* == *--new-keys* ]]; then

  chmod +x $HOME/setup/generate_wallet.py
  echo -e "${BLUE}* Node address generation *${NC}"
  while true; do
      read -sp "Press [Enter] to create a new wallet or provide a private key you wish to import: " input

      if [[ -z "$input" ]]; then
          echo -e ${YELLOW}"\nYou chose to create a new wallet${NC}"
          $HOME/setup/generate_wallet.py --path $keys_path --new_key
          break
      elif [[ $input =~ ^(0x)?[0-9a-fA-F]{64}$ ]]; then
          echo -e "${YELLOW}\nThe private key is valid. Importing the wallet...${NC}"
          $HOME/setup/generate_wallet.py --path $keys_path --import_key $input
          break
      else
          echo -e "${YELLOW}\nInvalid input. A valid private key should be a 64-character hexadecimal string (optionally prefixed with '0x'). Please try again.${NC}"
      fi
  done

  if [ $? -eq 0 ]; then
    echo -e "${GREEN}Keys were successfully stored under ${keys_path}!${NC}"
  else
    echo "${RED}generation of keys failed ${NC}"
    exit 1
  fi

  echo "------------------------------------"

fi

# ----- GENERATE ENV FILES -----
chmod +x $HOME/setup/generate_env_files.py
env_dir=$HOME/deployment
shared_name=shared.env
env_file=.env

if [[ ! -f "$env_dir/$env_file" || $* == *--new-keys* ]]; then
  $HOME/setup/generate_env_files.py --keys $keys_path --env_dir $env_dir --env_file $env_file --shared $shared_name

  if [ $? -eq 0 ]; then
    echo -e "${GREEN}env files were successfully stored under $env_dir ${NC}"
  else
    echo "${RED}generation of env files failed ${NC}"
    exit 1
  fi
fi

# ----- START MANAGER -----
echo -e "${BLUE}Starting manager...${NC}"
# TODO: this should be taken from env vars / provided by user
cp $HOME/setup/node-version.json /opt/orbs

python3 $HOME/manager/manager.py

echo -e "${GREEN}Manager started!${NC}"
echo "------------------------------------"

# ----- SETUP MANAGER CRON -----
echo -e "${BLUE}Adding scheduled manager run...${NC}"

chmod +x $HOME/manager/manager.py
sudo crontab $HOME/setup/deployment-poll.cron
sudo service cron restart

echo -e "${GREEN}Manager schedule set!${NC}"
echo "------------------------------------"

# ----- SANITY CHECK -----
echo -e "${BLUE}Performing a health check...${NC}"
sleep 3 # Wait for management service to start
mgmt_svs_status_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/service/management-service/status)
if [ $mgmt_svs_status_code -eq 200 ]; then
    echo -e "${GREEN}Installation complete! 🚀🚀🚀${NC}"
else
    echo -e "${RED}Installation incomplete!${NC}"
    # exit 1
fi
