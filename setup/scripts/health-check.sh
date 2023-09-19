#!/bin/bash

check_services() {
  compose_file="$HOME/deployment/docker-compose.yml"
  # Get the number of services defined in docker-compose file
  num_services=$(docker-compose -f $compose_file config --services | wc -l)

  for i in {1..5}
  do
    # Get the number of services that are up
    num_up=$(docker-compose -f $compose_file ps | grep "Up" | wc -l)
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
  mgmt_svs_status_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/service/ethereum-reader/status)
  if [ $mgmt_svs_status_code -eq 200 ]; then
      echo -e "${GREEN}Installation complete! 🚀🚀🚀${NC}"
      echo "------------------------------------"
      echo -e "\n👉👉👉 ${YELLOW}Please register your Guardian using the following website: https://guardians.orbs.network?name=$name&website=$website&ip=$myip&node_address=$public_add ${NC} 👈👈👈\n" # TODO: only show once - during first installation
  else
      echo -e "${RED}Installation incomplete!${NC}"
  fi
else
  echo -e "${RED}Installation incomplete!${NC}"
fi
