#!/bin/sh
set -e

# Default backend URL for local Docker Compose
BACKEND_URL="${BACKEND_URL:-http://backend:8000}"
NGINX_PORT="${PORT:-80}"

export BACKEND_URL NGINX_PORT

# Shared location blocks (included by both HTTP and HTTPS server blocks).
envsubst '${BACKEND_URL}' < /etc/nginx/conf.d/app-locations.conf.template > /etc/nginx/app_locations.inc

# HTTP server (always).
envsubst '${BACKEND_URL} ${NGINX_PORT}' < /etc/nginx/conf.d/nginx.conf.template > /etc/nginx/conf.d/default.conf

# HTTPS server — only when a Cloudflare Origin Certificate is mounted.
# This keeps the container from crash-looping before the cert is pasted.
if [ -f /etc/nginx/certs/origin.pem ] && [ -f /etc/nginx/certs/origin.key ]; then
    envsubst '${BACKEND_URL}' < /etc/nginx/conf.d/nginx-ssl.conf.template > /etc/nginx/conf.d/ssl.conf
    echo "[entrypoint] Origin certificate found — HTTPS (443) enabled."
else
    echo "[entrypoint] No origin certificate at /etc/nginx/certs — serving HTTP only."
fi

# The template files live in conf.d but must not be loaded as configs.
rm -f /etc/nginx/conf.d/*.template

exec nginx -g "daemon off;"
