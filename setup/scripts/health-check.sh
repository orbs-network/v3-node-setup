#!/bin/bash

check_services() {
  # Get the number of services defined in docker-compose file
  num_services=$(docker-compose -f $DOCKER_COMPOSE_FILE config --services | wc -l)

  for i in {1..5}
  do
    # Get the number of services that are up
    num_up=$(docker-compose -f $DOCKER_COMPOSE_FILE ps | grep "Up" | wc -l)
    if [ $num_up -eq $num_services ]; then
      echo "All services are up and running."
      return 0
    else
      echo "Waiting for services to start..."
      sleep 5
    fi
  done
  return 1
}

if check_services; then
  sleep 10
  mgmt_svs_status_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/service/ethereum-reader/status)
  if [ $mgmt_svs_status_code -eq 200 ]; then
      echo -e "${GREEN}Installation complete! 🚀🚀🚀${NC}"
      echo "------------------------------------"
      echo -e "👉👉👉 ${YELLOW}Please register your Guardian using:"
      echo -e "website: https://guardians.orbs.network?name=$name&website=$website&ip=$myip&node_address=$public_add=${NC}" 
      echo -e "👈👈👈"
      echo -e "name: $name"
      echo -e "node_address: $public_add"
      echo -e "website: $website"
      echo -e "ip: $myip"                
      echo -e "------------------------------------"      
  else
      echo -e "${RED}Installation incomplete!${NC}"
      #
      echo -e "Please check the logs for more information."
      # todo: add logs path
      echo -e "------------------------------------"
  fi
else
  echo -e "${RED}Installation incomplete!${NC}"
fi
