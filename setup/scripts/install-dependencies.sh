#!/bin/bash

echo -e "${BLUE}Installing dependencies...${NC}"

# TODO: I suspect it is dangerous to run upgrade each time installer script is run
if [ -f /etc/needrestart/needrestart.conf ]; then
  sudo sed -i "s/#\$nrconf{restart} = 'i';/\$nrconf{restart} = 'a';/" /etc/needrestart/needrestart.conf # disables the restart modal
fi
sudo apt-get update -qq && sudo apt-get -y upgrade -qq > "$redirect" 2>&1
echo -e "${YELLOW}This may take a few minutes. Please wait...${NC}"
sudo apt-get install -qq -y software-properties-common podman curl git cron jq > "$redirect" 2>&1
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
    export DOCKER_HOST=unix:///home/ubuntu/.local/run/podman/podman.sock
    export PODMAN_SOCKET_PATH=/home/ubuntu/.local/run/podman/podman.sock
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
    rm containernetworking-plugins_1.1.1+ds1-1_amd64.deb

    # INSTALL NODE EXPORTER
    cd $HOME
    NODE_EXPORTER_VERSION="0.18.1"
    curl -L https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz -o node_exporter.tar.gz
    tar xvfz node_exporter.tar.gz && mv node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter .
    chmod +x node_exporter
    rm -f node_exporter.tar.gz

    cat <<EOF | sudo tee /etc/systemd/system/node_exporter.service
[Unit]
Description=Node Exporter

[Service]
User=$(whoami)
ExecStart=$HOME/node_exporter --collector.tcpstat
Restart=always
StandardOutput=file:/var/log/node_exporter.log
StandardError=file:/var/log/node_exporter.err.log

[Install]
WantedBy=multi-user.target
EOF
    # Reload systemd, enable and start the service
    sudo systemctl daemon-reload
    sudo systemctl enable node_exporter
    sudo systemctl start node_exporter

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

sudo pip install -r $HOME/setup/requirements.txt

sudo systemctl enable cron

# Need to explicitly add docker.io registry
echo "[registries.search]" | sudo tee /etc/containers/registries.conf
echo "registries = ['docker.io']" | sudo tee -a /etc/containers/registries.conf

echo -e "${GREEN}Finished installing dependencies!${NC}"
echo "------------------------------------"