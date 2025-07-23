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

if [ "$RUNNING_IN_DOCKER" = "true" ]; then
  DOCKER_COMPOSE_FAKE_HEALTHCHECKS=$(printf '\n#\n# Emulate docker-compose health checks that are not really running in the container when podman runs docker-compose.\n# because of no systemd in the container, we need to run this as a cron job\n* * * * * cd $ORBS_ROOT/deployment && $ORBS_ROOT/manager/.venv/bin/python3 $ORBS_ROOT/manager/src/docker-compose-healthchecks.py >> /tmp/manager.out 2>&1')
else
  DOCKER_COMPOSE_FAKE_HEALTHCHECKS=""
fi

sudo crontab $ORBS_ROOT/deployment/.env -u $username
(env ; cat $ORBS_ROOT/setup/deployment-poll.cron ; echo "$DOCKER_COMPOSE_FAKE_HEALTHCHECKS") | crontab - -u $username
sudo service cron restart

echo -e "${GREEN}Manager schedule set!${NC}"
echo "------------------------------------"