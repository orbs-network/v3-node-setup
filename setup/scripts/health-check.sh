#!/bin/bash

COMPOSE_FILE="$HOME/deployment/docker-compose.yml"

echo -e "${BLUE}Performing a health check...${NC}\n"

# Get the number of services defined in docker-compose file
num_services=$(docker-compose -f $COMPOSE_FILE config --services | wc -l)
# Wait for services to be up
while true
do
  # Get the number of services that are up
  num_up=$(docker-compose -f $COMPOSE_FILE ps | grep "Up" | wc -l)

  if [ $num_up -eq $num_services ]; then
    echo -e "${GREEN}Installation complete! 🚀🚀🚀${NC}"
    break
  else
    echo "Waiting for services to start..."
    podman ps -a
    echo "------------------------------------"
    podman logs logger
    podman inspect logger
    echo "------------------------------------"
    podman logs nginx
    podman inspect nginx
    echo "------------------------------------"
    podman logs ethereum-writer
    podman inspect ethereum-writer
    sleep 5
  fi
done
echo "------------------------------------"
echo -e "\n👉👉👉 ${YELLOW}Please register your Guardian using the following website: https://guardians.orbs.network?name=$name&website=$website&ip=$myip&node_address=$public_add ${NC} 👈👈👈\n" # TODO: only show once - during first installation

podman ps -a

#mgmt_svs_status_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/service/ethereum-reader/status)
#if [ $mgmt_svs_status_code -eq 200 ]; then
#    echo -e "${GREEN}Installation complete! 🚀🚀🚀${NC}"
#    echo "------------------------------------"
#    echo -e "\n👉👉👉 ${YELLOW}Please register your Guardian using the following website: https://guardians.orbs.network?name=$name&website=$website&ip=$myip&node_address=$public_add ${NC} 👈👈👈\n" # TODO: only show once - during first installation
#else
#    echo -e "${RED}Installation incomplete!${NC}"
#fi
