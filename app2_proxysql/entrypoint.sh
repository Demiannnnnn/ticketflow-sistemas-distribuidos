#!/bin/sh
set -e

CONFIG_FILE="/etc/proxysql.cnf"
TEMPLATE_FILE="/etc/proxysql.cnf.template"

if [ -f "$TEMPLATE_FILE" ]; then
    sed \
      -e "s|\${APP2_PROXY_ADMIN_USER}|${APP2_PROXY_ADMIN_USER:-admin}|g" \
      -e "s|\${APP2_PROXY_ADMIN_PASSWORD}|${APP2_PROXY_ADMIN_PASSWORD}|g" \
      -e "s|\${APP2_MONITOR_USER}|${APP2_MONITOR_USER:-monitor_user}|g" \
      -e "s|\${APP2_MONITOR_PASSWORD}|${APP2_MONITOR_PASSWORD}|g" \
      -e "s|\${APP2_DB_USER}|${APP2_DB_USER:-user}|g" \
      -e "s|\${APP2_DB_PASSWORD}|${APP2_DB_PASSWORD}|g" \
      -e "s|\${APP2_DB_ROOT_PASSWORD}|${APP2_DB_ROOT_PASSWORD}|g" \
      "$TEMPLATE_FILE" > "$CONFIG_FILE"
fi

exec proxysql -f --idle-threads -c "$CONFIG_FILE"
