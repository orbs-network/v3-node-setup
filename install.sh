#!/bin/bash
echo "ORBS V3 Node Setup"
echo "=================="

#check node.json exists here


# installing 
echo "installing docker..."
wget -O - https://gist.githubusercontent.com/fredhsu/f3d927d765727181767b3b13a3a23704/raw/3c2c55f185e23268f7fce399539cb6f1f3c45146/ubuntudocker.sh | bash

# install prometheus node exporter
apt-get -y install prometheus-node-exporter

# download binary
mkdir /opt/orbs

wget https://github.com/orbs-network/v3-node-manager/releases/download/v0.0.1/v3-node-manager-linux-x64 -P /usr/bin/
chmod +x /usr/bin/v3-node-manager-linux-x64

# create watchdog to start 
apt install supervisor -y

CONF_FILE= '/etc/supervisor/conf.d/manager-supervisor.conf'
touch $CONF_FILE

echo 'command=/usr/bin/v3-node-manager-linux-x64' > $CONF_FILE
echo 'autostart=true' >> $CONF_FILE
echo 'autorestart=true' >> $CONF_FILE
echo 'stderr_logfile=/var/log/v3-node-manager.err.log' >> $CONF_FILE
echo 'stdout_logfile=/var/log/v3-node-manager.out.log' >> $CONF_FILE
supervisorctl reread
supervisorctl update

#tail /var/log/idle.out.log