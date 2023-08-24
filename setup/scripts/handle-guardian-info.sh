#!/bin/bash

echo -e "${BLUE}Prompting for Guardian details...${NC}"

if [ -f /.dockerenv ]; then
    name="test"
    website="test.com"
else
    while true; do
        read -rp "Please enter your Guardian name: " name
        if [[ -n "$name" ]]; then
            break
        fi
    done

    while true; do
        read -rp "Please enter Guardian website: " website
        if [[ -n "$website" ]]; then
            break
        fi
    done
fi

myip="$(curl ifconfig.me)"

public_add=$(jq -r '."node-address"' $keys_path)

echo -e "${GREEN}Guardian details saved!${NC}"
echo "------------------------------------"