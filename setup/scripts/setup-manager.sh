#!/bin/bash

echo -e "${BLUE}Starting manager...${NC}"

# Activate Python virtual environment (only temporarily needed for Manager until published as package)
source $HOME/manager/.venv/bin/activate

cp $HOME/setup/node-version.json /opt/orbs

python3 $HOME/manager/src/manager.py

echo -e "${GREEN}Manager started!${NC}"
echo "------------------------------------"

# ----- SETUP MANAGER CRON -----
echo -e "${BLUE}Adding scheduled manager run...${NC}"

sudo crontab $HOME/setup/deployment-poll.cron -u $username
sudo service cron restart

echo -e "${GREEN}Manager schedule set!${NC}"
echo "------------------------------------"