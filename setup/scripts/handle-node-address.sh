#!/bin/bash

keys_path=/opt/orbs/keys.json

if [[ ! -f $keys_path || $* == *--new-keys* ]]; then

  echo -e "${BLUE}Node address generation${NC}"
  chmod +x $HOME/setup/generate_wallet.py
  while true; do
      read -sp "Press [Enter] to create a new wallet or provide a private key you wish to import: " input

      if [[ -z "$input" ]]; then
          echo -e ${YELLOW}"\nYou chose to create a new wallet${NC}"
          $HOME/setup/generate_wallet.py --path $keys_path --new_key
          break
      elif [[ $input =~ ^(0x)?[0-9a-fA-F]{64}$ ]]; then
          echo -e "${YELLOW}\nThe private key is valid. Importing the wallet...${NC}"
          $HOME/setup/generate_wallet.py --path $keys_path --import_key $input
          break
      else
          echo -e "${YELLOW}\nInvalid input. A valid private key should be a 64-character hexadecimal string (optionally prefixed with '0x'). Please try again.${NC}"
      fi
  done

  if [ $? -eq 0 ]; then
    echo -e "${GREEN}Keys were successfully stored under ${keys_path}!${NC}"
  else
    echo "${RED}Generation of keys failed ${NC}"
    exit 1
  fi

  echo "------------------------------------"

fi