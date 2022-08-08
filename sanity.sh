#!/bin/bash

echo "make sure the manager is running"
systemctl status

echo "list /opt orbs"
ll /opt/orbs
