#!/bin/bash

echo -e "${BLUE}Populating required env files...${NC}"

chmod +x $HOME/setup/generate_env_files.py
env_dir=$HOME/deployment
shared_name=shared.env
env_file=.env

if [[ ! -f "$env_dir/$env_file" || $* == *--new-keys* ]]; then
  $HOME/setup/generate_env_files.py --keys $keys_path --env_dir $env_dir --env_file $env_file --shared $shared_name

  if [ $? -eq 0 ]; then
    echo -e "${GREEN}Env files were successfully stored under $env_dir ${NC}"
  else
    echo "${RED}Generation of env files failed ${NC}"
    exit 1
  fi
fi

echo "------------------------------------"