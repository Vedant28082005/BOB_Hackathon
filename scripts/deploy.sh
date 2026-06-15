#!/bin/bash
# Pull latest code and restart changed services
set -euo pipefail

APP_DIR="/opt/trustlayer"
COMPOSE="docker compose -f docker-compose.prod.yml"

cd "$APP_DIR"

echo "► Pulling latest code..."
git pull

echo "► Rebuilding changed images..."
$COMPOSE build --parallel

echo "► Rolling restart..."
$COMPOSE up -d --remove-orphans

echo "► Waiting for backend health..."
for i in $(seq 1 30); do
  if $COMPOSE exec -T backend curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Backend healthy"
    break
  fi
  sleep 3
done

echo "► Running migrations..."
$COMPOSE exec -T backend alembic upgrade head

echo ""
echo "✓ Deploy complete. Services running:"
$COMPOSE ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
