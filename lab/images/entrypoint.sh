#!/bin/sh
# Serve on 8080 and on $PORT (if set), log a heartbeat so `kubectl logs` has something to capture.
httpd -f -p 8080 -h /www &
[ -n "$PORT" ] && [ "$PORT" != 8080 ] && httpd -f -p "$PORT" -h /www &
echo "$(date -u +%FT%TZ) started $(hostname) image=${IMAGE_NAME:-lab} port=${PORT:-8080}"
while true; do sleep 30; echo "$(date -u +%FT%TZ) heartbeat"; done
