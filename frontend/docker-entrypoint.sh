#!/bin/sh
set -e

# Default backend URL for local Docker Compose
BACKEND_URL="${BACKEND_URL:-http://backend:8000}"
NGINX_PORT="${PORT:-80}"

export BACKEND_URL NGINX_PORT

# Substitute env vars into nginx config
envsubst '${BACKEND_URL} ${NGINX_PORT}' < /etc/nginx/conf.d/nginx.conf.template > /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
