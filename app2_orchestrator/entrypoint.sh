#!/bin/sh
set -e

CONFIG_FILE="/etc/orchestrator.conf.json"
TEMPLATE_FILE="/etc/orchestrator.conf.json.template"

if [ -f "$TEMPLATE_FILE" ]; then
    sed \
      -e "s|\${APP2_ORCH_USER}|${APP2_ORCH_USER:-orch_user}|g" \
      -e "s|\${APP2_ORCH_PASSWORD}|${APP2_ORCH_PASSWORD}|g" \
      "$TEMPLATE_FILE" > "$CONFIG_FILE"
fi

if [ $# -gt 0 ]; then
    exec "$@"
fi

exec /usr/local/orchestrator/orchestrator --config="$CONFIG_FILE" http
