#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# TrustLayer — EC2 first-time setup script
# Run as: curl -fsSL <raw-url>/scripts/ec2-setup.sh | sudo bash
# Tested on: Amazon Linux 2023, Ubuntu 22.04/24.04
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/Vedant28082005/BOB_Hackathon.git"
APP_DIR="/opt/trustlayer"
COMPOSE_FILE="docker-compose.prod.yml"

echo "════════════════════════════════════════"
echo "  TrustLayer — EC2 Setup"
echo "════════════════════════════════════════"

# ── Detect OS ────────────────────────────────────────────
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS=$ID
else
  OS="unknown"
fi

# ── Install Docker ───────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "► Installing Docker..."
  if [[ "$OS" == "amzn" ]]; then
    dnf update -y
    dnf install -y docker git
    systemctl enable --now docker
    usermod -aG docker ec2-user
  elif [[ "$OS" == "ubuntu" ]]; then
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg git
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker
    usermod -aG docker ubuntu
  fi
  echo "✓ Docker installed"
else
  echo "✓ Docker already installed"
fi

# ── Install Docker Compose plugin ───────────────────────
if ! docker compose version &>/dev/null; then
  echo "► Installing Docker Compose plugin..."
  COMPOSE_VERSION="v2.27.0"
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  echo "✓ Docker Compose installed"
fi

# ── Clone repo ───────────────────────────────────────────
echo "► Cloning repository..."
if [ -d "$APP_DIR" ]; then
  cd "$APP_DIR" && git pull
else
  git clone "$REPO_URL" "$APP_DIR"
  cd "$APP_DIR"
fi
echo "✓ Repository ready at $APP_DIR"

# ── Create .env ──────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
  echo ""
  echo "════════════════════════════════════════"
  echo "  ACTION REQUIRED: Configure secrets"
  echo "════════════════════════════════════════"
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"

  # Auto-generate secrets
  JWT_SECRET=$(openssl rand -hex 32)
  AES_KEY=$(openssl rand -hex 32)
  INTERNAL_KEY=$(openssl rand -hex 16)
  PG_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)
  REDIS_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)
  NEO4J_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)
  MINIO_USER="trustlayer$(openssl rand -hex 4)"
  MINIO_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)

  sed -i \
    -e "s|CHANGE_ME_strong_pg_password|$PG_PASS|g" \
    -e "s|CHANGE_ME_redis_password|$REDIS_PASS|g" \
    -e "s|CHANGE_ME_neo4j_password|$NEO4J_PASS|g" \
    -e "s|CHANGE_ME_minio_user|$MINIO_USER|g" \
    -e "s|CHANGE_ME_minio_password_min12chars|$MINIO_PASS|g" \
    -e "s|CHANGE_ME_generate_with_openssl_rand_hex_32|PLACEHOLDER|g" \
    -e "s|CHANGE_ME_internal_api_key|$INTERNAL_KEY|g" \
    "$APP_DIR/.env"

  # Set the two hex keys individually
  sed -i "0,/PLACEHOLDER/s/PLACEHOLDER/$JWT_SECRET/" "$APP_DIR/.env"
  sed -i "0,/PLACEHOLDER/s/PLACEHOLDER/$AES_KEY/" "$APP_DIR/.env"

  echo ""
  echo "  ✓ Secrets auto-generated and written to .env"
  echo "  ✎ Edit /opt/trustlayer/.env to add your GEMINI_API_KEY"
  echo "    nano /opt/trustlayer/.env"
  echo ""
else
  echo "✓ .env already exists — skipping"
fi

# ── Create required directories ──────────────────────────
mkdir -p "$APP_DIR/infra/geoip"
mkdir -p "$APP_DIR/ml-service/model_weights"

# ── Open firewall ports ──────────────────────────────────
echo "► Configuring firewall..."
if command -v ufw &>/dev/null; then
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
fi
echo "✓ Firewall configured (ports 22, 80, 443)"

echo ""
echo "════════════════════════════════════════"
echo "  Setup complete!"
echo "  Next steps:"
echo ""
echo "  1. Add GEMINI_API_KEY to .env:"
echo "     nano /opt/trustlayer/.env"
echo ""
echo "  2. Start TrustLayer:"
echo "     cd /opt/trustlayer && make up"
echo "     (or: docker compose -f docker-compose.prod.yml up -d)"
echo ""
echo "  3. Seed initial users:"
echo "     cd /opt/trustlayer && make seed"
echo ""
echo "  4. Access the app at http://<your-ec2-public-ip>"
echo "════════════════════════════════════════"
