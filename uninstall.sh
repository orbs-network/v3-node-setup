#!/bin/bash
echo "======================================================="
echo "== ORBS V3 Node Setup - UNINSTALL"
echo "======================================================="
echo "stop remove supervisorctl"
supervisorctl stop manager
supervisorctl remove manager

MANAGER_PATH="/usr/bin/v3-node-manager-x64"
echo "delete $MANAGER_PATH"
rm $MANAGER_PATH

CONF_FILE="/etc/supervisor/conf.d/manager.conf"
echo "delete conf file: $CONF_FILE"
rm $CONF_FILE

echo "reread and update"
supervisorctl reread
supervisorctl update

echo "remove /opt/orbs"
ORBS_PATH="/opt/orbs"
rm -r $ORBS_PATH