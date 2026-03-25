#!/usr/bin/env bash
set -euo pipefail

# ══════════════════════════════════════════════════════════
#  Ome Server — One-Command Deploy
#
#  Usage:
#    1. SSH into your server
#    2. git clone https://github.com/wyonliu/Omnity.git && cd Omnity/deploy
#    3. cp .env.example .env && nano .env   (fill in API key + domain)
#    4. bash deploy.sh
#
#  That's it. Script handles: Docker install, SSL cert, build, launch.
# ══════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
GOLD='\033[0;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[Ome]${NC} $1"; }
warn()  { echo -e "${GOLD}[Ome]${NC} $1"; }
error() { echo -e "${RED}[Ome]${NC} $1"; exit 1; }

# ── Step 0: Check .env ──
if [ ! -f .env ]; then
    error ".env not found. Run: cp .env.example .env && nano .env"
fi

source .env

if [ -z "${DEEPSEEK_API_KEY:-}" ] && [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    error "At least one LLM API key is required in .env"
fi

DOMAIN="${OME_DOMAIN:-api.ome.ai}"
info "Deploying Ome Server to ${DOMAIN}"

# ── Step 1: Install Docker (if needed) ──
if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker && systemctl start docker
    info "Docker installed."
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
    info "Installing docker-compose..."
    apt-get update && apt-get install -y docker-compose-plugin
fi

# Prefer 'docker compose' (v2) over 'docker-compose' (v1)
if docker compose version &>/dev/null 2>&1; then
    DC="docker compose"
else
    DC="docker-compose"
fi

# ── Step 2: Generate JWT secret (if not set) ──
if [ -z "${JWT_SECRET:-}" ]; then
    JWT_SECRET=$(openssl rand -hex 32)
    echo "JWT_SECRET=${JWT_SECRET}" >> .env
    info "Generated JWT secret."
fi

# ── Step 3: Replace domain in nginx config ──
sed -i "s/OME_DOMAIN/${DOMAIN}/g" nginx.conf
info "Nginx configured for ${DOMAIN}."

# ── Step 4: Get SSL certificate (first time only) ──
if [ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
    info "Obtaining SSL certificate for ${DOMAIN}..."

    # Start nginx temporarily with self-signed cert for ACME challenge
    mkdir -p /tmp/ome-certbot
    $DC up -d nginx 2>/dev/null || true

    docker run --rm \
        -v ome_certbot-etc:/etc/letsencrypt \
        -v ome_certbot-var:/var/lib/letsencrypt \
        -v ome_certbot-webroot:/var/www/certbot \
        certbot/certbot certonly \
        --webroot --webroot-path=/var/www/certbot \
        --email admin@${DOMAIN} \
        --agree-tos --no-eff-email \
        -d ${DOMAIN} \
    || {
        warn "SSL cert failed. Starting HTTP-only mode."
        warn "Make sure DNS for ${DOMAIN} points to this server's IP."
        warn "Then re-run: bash deploy.sh"
    }

    $DC down 2>/dev/null || true
fi

# ── Step 5: Build and launch ──
info "Building Ome Server..."
$DC build --no-cache

info "Starting Ome Server..."
$DC up -d

# ── Step 6: Health check ──
info "Waiting for server to start..."
sleep 5

if curl -sf "http://localhost:8765/docs" > /dev/null 2>&1; then
    echo ""
    info "════════════════════════════════════════"
    info "  ✦ Ome Server is live! ✦"
    info "  https://${DOMAIN}"
    info "  API docs: https://${DOMAIN}/docs"
    info "════════════════════════════════════════"
    echo ""
else
    warn "Server may still be starting. Check: $DC logs ome-server"
fi

# ── Step 7: Show next steps ──
echo ""
info "Next steps:"
info "  1. Verify: curl https://${DOMAIN}/docs"
info "  2. Update iOS app server URL to: https://${DOMAIN}"
info "  3. Upload iOS to TestFlight: cd packages/ome-ios && fastlane beta"
echo ""
info "Useful commands:"
info "  $DC logs -f ome-server  # View logs"
info "  $DC restart ome-server  # Restart"
info "  $DC down                # Stop all"
info "  git pull && $DC build --no-cache && $DC up -d  # Update"
