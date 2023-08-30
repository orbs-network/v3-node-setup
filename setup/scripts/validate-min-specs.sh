#!/bin/bash

if [[ ! $* == *--skip-req* ]]; then
    echo -e "${BLUE}Checking machine meets minimum hardware requirements...${NC}"
    
    # Min specs
    MIN_CPU=4   # in cores
    MIN_MEMORY=8   # in GB
    MIN_DISK=20 # in GB

    # Get current machine specs
    CPU=$(nproc --all)
    RAM=$(free -g | awk '/^Mem:/{print $2}')
    DISK=$(df -BG / | awk 'NR==2{print substr($4, 1, length($4)-1)}')

    # Check CPU
    if [ $CPU -lt $MIN_CPU ]; then
        echo -e "${RED}Insufficient CPU cores. Required: $MIN_CPU, Available: $CPU.${NC}"
        exit 1
    fi

    # Check RAM
    if [ $RAM -lt $MIN_MEMORY ]; then
        echo -e "${RED}Insufficient memory. Required: $MIN_MEMORY GB, Available: $RAM GB.${NC}"
        exit 1
    fi

    # Check Disk
    if [ $DISK -lt $MIN_DISK ]; then
        echo -e "${RED}Insufficient Disk space. Required: $MIN_DISK GB, Available: $DISK GB.${NC}"
        exit 1
    fi

    echo -e "${GREEN}System meets minimum requirements!${NC}"
    echo "------------------------------------"
fi 