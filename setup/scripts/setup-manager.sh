#!/bin/bash

echo -e "${BLUE}Starting manager...${NC}"

# Activate Python virtual environment (only temporarily needed for Manager until published as package)
source $ORBS_ROOT/manager/.venv/bin/activate

cp $ORBS_ROOT/setup/node-version.json /opt/orbs

python3 $ORBS_ROOT/manager/src/manager.py

echo -e "${GREEN}Manager started!${NC}"
echo "------------------------------------"

# ----- SETUP MANAGER CRON -----
echo -e "${BLUE}Adding scheduled manager run...${NC}"

sudo crontab $ORBS_ROOT/deployment/.env -u $username
(env ; cat $ORBS_ROOT/setup/deployment-poll.cron) | crontab - -u $username
sudo service cron restart

echo -e "${GREEN}Manager schedule set!${NC}"
echo "------------------------------------"