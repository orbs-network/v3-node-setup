#!/bin/bash

echo -e "${BLUE}Starting manager...${NC}"

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