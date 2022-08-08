#!/bin/bash
echo "============================="
echo "== ORBS V3 Node Setup - START"
echo "============================="

#check node.json exists here


# installing 
echo "======================================"
echo "== ORBS V3 Node Setup - INSTALL DOCKER"
echo "======================================"
wget -O - https://gist.githubusercontent.com/fredhsu/f3d927d765727181767b3b13a3a23704/raw/3c2c55f185e23268f7fce399539cb6f1f3c45146/ubuntudocker.sh | bash

# init swarm mode
docker swarm init

echo "============================================="
echo "== ORBS V3 Node Setup - INSTALL NODE EXPORTER"
echo "============================================="
# install prometheus node exporter
apt-get -y install prometheus-node-exporter

# download binary
#mkdir /opt/orbs

echo "==============================================="
echo "== ORBS V3 Node Setup - INSTALL v3-node-manager"
echo "==============================================="
MANAGER_URL="https://github.com/orbs-network/v3-node-manager/releases/download/v0.0.2/v3-node-manager-x64-v0.0.2-e625edc2"
MANAGER_PATH="/usr/bin/v3-node-manager-x64"
wget -O $MANAGER_PATH $MANAGER_URL
chmod +x $MANAGER_PATH

echo "==============================================="
echo "== TODO: make alias for manager /opt/orbs"
echo "==============================================="

echo "==============================================="
echo "== TODO: ORBS V3 Node Setup - Install recovery"
echo "==============================================="


# create watchdog to start 
echo "==============================================="
echo "== ORBS V3 Node Setup - INSTALL Supervisor"
echo "==============================================="

apt install supervisor -y

CONF_FILE="/etc/supervisor/conf.d/manager.conf"
touch $CONF_FILE

echo "[program:manager]" > $CONF_FILE
echo "command=$MANAGER_PATH" >> $CONF_FILE
echo "autostart=true" >> $CONF_FILE
echo "autorestart=true" >> $CONF_FILE
echo "stderr_logfile=/var/log/v3-node-manager.err.log" >> $CONF_FILE
echo "stdout_logfile=/var/log/v3-node-manager.out.log" >> $CONF_FILE

# echo "==============================================="
# echo "== ORBS V3 Node Setup - create ssh keys if needed"
# echo "==============================================="
# FILE=~/.ssh/id_rsa
# if test -f "$FILE"; then
#     ssh-keygen -q -t rsa -N '' -f ~/.ssh/id_rsa <<<y >/dev/null 2>&1
# fi

echo "================================================"
echo "== ORBS V3 Node Setup - clone setup to /opt/orbs"
echo "================================================"
#wget --no-parent -r https://github.com/orbs-network/v3-node-setup/tree/main/ingress/nginx
mkdir -p /opt/orbs
cd /opt/orbs
git clone https://github.com/orbs-network/v3-node-setup.git

# run manager with supervisor
echo "==============================================="
echo "== ORBS V3 Node Setup - INSTALL Supervisor"
echo "==============================================="
supervisorctl reread
supervisorctl update

#tail /var/log/v3-node-manager.err.log
#tail /var/log/v3-node-manager.out.log