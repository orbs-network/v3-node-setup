#!/bin/bash

echo -e "${BLUE}Starting control...${NC}"

# Activate Python virtual environment (only temporarily needed for control until published as package)
source $HOME/control/.venv/bin/activate

cp $HOME/setup/node-version.json /opt/orbs

python3 $HOME/control/src/main.py

echo -e "${GREEN}Control started!${NC}"
echo "------------------------------------"

# ----- SETUP control CRON -----
echo -e "${BLUE}Adding scheduled control run...${NC}"

sudo crontab $HOME/setup/deployment-poll.cron -u $username
sudo service cron restart

echo -e "${GREEN}control schedule set!${NC}"
echo "------------------------------------"