#!/bin/bash

# TODO: renable this when we are using 3 seperate repos
# # ----- CLONE DEPLOYMENT (MANIFEST) FILES -----
# echo -e "${BLUE}Downloading node deployment files...${NC}"
# # TODO: this is the wrong repo
# git clone https://github.com/orbs-network/v3-deployment.git deployment
# # Disable detached head warning. This is fine as we are checking out tags
# cd $HOMEdeployment && git config advice.detachedHead false && cd ..

# echo -e "${GREEN}Node deployment files downloaded!${NC}"
# echo "------------------------------------"

## ---- DEPRECATED ---- ALL In One Repo

# # ----- CLONE CONTROL -----
# echo -e "${BLUE}Downloading node control...${NC}"
# git clone https://github.com/orbs-network/v3-node-control.git control
# cd $HOME/control && git config advice.detachedHead false && cd ..

# echo -e "${GREEN}Node control downloaded!${NC}"
# echo "------------------------------------"