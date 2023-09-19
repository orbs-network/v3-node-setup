#!/bin/bash

COMPOSE_FILE="$HOME/deployment/docker-compose.yml"

echo -e "${BLUE}Performing a health check...${NC}\n"

# Wait for services to be up
while [ "$(docker-compose -f $COMPOSE_FILE ps | awk '/_/{if($3 ~ "Up") print "Up"}')" != "Up" ]
do
  echo "Waiting for services to start..."
  docker ps -a
  sleep 5
done

mgmt_svs_status_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/service/ethereum-reader/status)
if [ $mgmt_svs_status_code -eq 200 ]; then
    echo -e "${GREEN}Installation complete! 🚀🚀🚀${NC}"
    echo "------------------------------------"
    echo -e "\n👉👉👉 ${YELLOW}Please register your Guardian using the following website: https://guardians.orbs.network?name=$name&website=$website&ip=$myip&node_address=$public_add ${NC} 👈👈👈\n" # TODO: only show once - during first installation
else
    echo -e "${RED}Installation incomplete!${NC}"
fi
