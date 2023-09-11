#!/bin/bash

echo -e "${BLUE}Performing a health check...${NC}\n"

sleep 10 # Wait for management service to start

mgmt_svs_status_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/service/ethereum-reader/status)
if [ $mgmt_svs_status_code -eq 200 ]; then
    echo -e "${GREEN}Installation complete! 🚀🚀🚀${NC}"
    echo "------------------------------------"
    echo -e "\n👉👉👉 ${YELLOW}Please register your Guardian using the following website: https://guardians.orbs.network?name=$name&website=$website&ip=$myip&node_address=$public_add ${NC} 👈👈👈\n" # TODO: only show once - during first installation
else
    echo -e "${RED}Installation incomplete!${NC}"
fi
