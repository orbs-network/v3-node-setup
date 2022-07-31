#!/bin/bash
echo "ORBS V3 Node Setup"
echo "=================="

#check node.json exists here


# installing 
echo "installing docker..."
wget -O - https://gist.githubusercontent.com/fredhsu/f3d927d765727181767b3b13a3a23704/raw/3c2c55f185e23268f7fce399539cb6f1f3c45146/ubuntudocker.sh | bash

# 
echo "installing Node & Npm..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
apt-get install nodejs

# install and run npm v3-manager

# install prometheus node exporter
sudo apt-get -y install prometheus-node-exporter

#open relevant ports