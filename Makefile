COMPOSE = docker compose -f docker-compose.prod.yml
COMPOSE_DEV = docker compose -f infra/docker-compose.yml

.PHONY: up down restart logs build seed ps shell-backend shell-worker

## ── Production (EC2) ─────────────────────────────────────────────────────────
up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

rebuild:
	$(COMPOSE) build --parallel
	$(COMPOSE) up -d --remove-orphans

logs:
	$(COMPOSE) logs -f --tail=100

logs-backend:
	$(COMPOSE) logs -f backend worker

logs-ml:
	$(COMPOSE) logs -f ml-service

ps:
	$(COMPOSE) ps

seed:
	$(COMPOSE) exec backend python seed.py

migrate:
	$(COMPOSE) exec backend alembic upgrade head

shell-backend:
	$(COMPOSE) exec backend bash

shell-worker:
	$(COMPOSE) exec worker bash

## ── Local dev ────────────────────────────────────────────────────────────────
dev-up:
	$(COMPOSE_DEV) up -d

dev-down:
	$(COMPOSE_DEV) down

dev-logs:
	$(COMPOSE_DEV) logs -f --tail=50

## ── Secrets generator (run once locally, paste into .env) ───────────────────
gen-secrets:
	@echo "JWT_SECRET_KEY=$$(openssl rand -hex 32)"
	@echo "AES_KEY_HEX=$$(openssl rand -hex 32)"
	@echo "INTERNAL_API_KEY=$$(openssl rand -hex 16)"
	@echo "POSTGRES_PASSWORD=$$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)"
	@echo "REDIS_PASSWORD=$$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)"
	@echo "NEO4J_PASSWORD=$$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)"
	@echo "MINIO_SECRET_KEY=$$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)"
